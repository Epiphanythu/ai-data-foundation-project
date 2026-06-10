"""modeling/automl_cash.py CASH AutoML 引擎

CASH = Combined Algorithm Selection and Hyperparameter optimization。
本模块在一个 Optuna study 内同时搜索：
  1. 模型族选择（LR / XGBoost / LightGBM / RandomForest / ExtraTrees）；
  2. 数值预处理（imputer × scaler 组合）；
  3. 类别编码（OneHot / Ordinal）；
  4. 自动特征交互（无 / Poly2）；
  5. 不平衡处理（none / class_weight / SMOTE）；
  6. 各模型自身超参；
  7. 优化目标（auc / pr_auc / 阈值利润）。

全程使用 TimeSeriesSplit 做 CV，避免未来信息泄露。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    MinMaxScaler,
    OneHotEncoder,
    OrdinalEncoder,
    PolynomialFeatures,
    RobustScaler,
    StandardScaler,
)
from xgboost import XGBClassifier

from constant.model import (
    ASSUMED_INTEREST_MARGIN,
    ASSUMED_LGD,
    AUTOML_CASH_CV_FOLDS,
    AUTOML_CASH_N_TRIALS,
    AUTOML_CASH_OPTIMIZE_METRIC,
    AUTOML_CASH_SAMPLE_FOR_SEARCH,
    AUTOML_CASH_TIMEOUT_SEC,
    AUTOML_CASH_TOPK_REFIT,
    AUTOML_CAT_ENCODER_CHOICES,
    AUTOML_FEATURE_INTERACTION_CHOICES,
    AUTOML_IMBALANCE_CHOICES,
    AUTOML_MODEL_CANDIDATES,
    AUTOML_NUM_IMPUTER_CHOICES,
    AUTOML_NUM_SCALER_CHOICES,
    MODEL_EXTRA_TREES,
    MODEL_LGB,
    MODEL_LR,
    MODEL_RF,
    MODEL_XGB,
    RANDOM_SEED,
    STRATEGY_THRESHOLDS,
)

logger = logging.getLogger(__name__)


# CashConfig 单次 trial 的完整配置
@dataclass
class CashConfig:
    model_type: str
    num_imputer: str
    num_scaler: str
    cat_encoder: str
    feature_interaction: str
    imbalance: str
    model_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# _build_numeric_pipe 构造可配置的数值预处理 pipeline
def _build_numeric_pipe(imputer: str, scaler: str, interaction: str) -> Pipeline:
    # 1. imputer
    if imputer == "median":
        imp = SimpleImputer(strategy="median")
    elif imputer == "mean":
        imp = SimpleImputer(strategy="mean")
    else:
        imp = SimpleImputer(strategy="constant", fill_value=0.0)
    # 2. scaler
    if scaler == "standard":
        sc = StandardScaler()
    elif scaler == "minmax":
        sc = MinMaxScaler()
    elif scaler == "robust":
        sc = RobustScaler()
    else:
        sc = "passthrough"
    steps = [("imputer", imp)]
    if sc != "passthrough":
        steps.append(("scaler", sc))
    # 3. 自动特征交互（仅在 interaction=poly2 时启用，且控制度数防爆炸）
    if interaction == "poly2":
        steps.append(
            (
                "poly",
                PolynomialFeatures(degree=2, interaction_only=True, include_bias=False),
            )
        )
    return Pipeline(steps)


# _build_categorical_pipe 构造可配置的类别编码 pipeline
def _build_categorical_pipe(encoder: str) -> Pipeline:
    imp = SimpleImputer(strategy="constant", fill_value="Unknown")
    if encoder == "ordinal":
        enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    else:
        enc = OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False)
    return Pipeline([("imputer", imp), ("encoder", enc)])


# _build_preprocessor 根据 CashConfig 拼装 ColumnTransformer
def _build_preprocessor(cfg: CashConfig, num_cols: list[str], cat_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", _build_numeric_pipe(cfg.num_imputer, cfg.num_scaler, cfg.feature_interaction), num_cols),
            ("cat", _build_categorical_pipe(cfg.cat_encoder), cat_cols),
        ],
        remainder="drop",
    )


# _build_model 根据 CashConfig 构造分类器（含 class_weight 处理）
def _build_model(cfg: CashConfig):
    use_class_weight = cfg.imbalance == "class_weight"
    params = dict(cfg.model_params)
    if cfg.model_type == MODEL_LR:
        if use_class_weight:
            params["class_weight"] = "balanced"
        return LogisticRegression(max_iter=500, solver="lbfgs", random_state=RANDOM_SEED, **params)
    if cfg.model_type == MODEL_XGB:
        if use_class_weight:
            params["scale_pos_weight"] = params.pop("scale_pos_weight", 3.7)
        return XGBClassifier(
            eval_metric="auc",
            random_state=RANDOM_SEED,
            tree_method="hist",
            n_jobs=4,
            **params,
        )
    if cfg.model_type == MODEL_LGB:
        from lightgbm import LGBMClassifier

        if use_class_weight:
            params["class_weight"] = "balanced"
        return LGBMClassifier(random_state=RANDOM_SEED, verbose=-1, n_jobs=4, **params)
    if cfg.model_type == MODEL_RF:
        if use_class_weight:
            params["class_weight"] = "balanced"
        return RandomForestClassifier(random_state=RANDOM_SEED, n_jobs=4, **params)
    if cfg.model_type == MODEL_EXTRA_TREES:
        if use_class_weight:
            params["class_weight"] = "balanced"
        return ExtraTreesClassifier(random_state=RANDOM_SEED, n_jobs=4, **params)
    raise ValueError(f"未知模型族: {cfg.model_type}")


# _suggest_model_params 由 Optuna 在搜索空间中建议各模型族超参
def _suggest_model_params(trial, model_type: str) -> dict:
    if model_type == MODEL_LR:
        return {
            "C": trial.suggest_float("lr_C", 1e-3, 1e2, log=True),
            "penalty": "l2",
        }
    if model_type == MODEL_XGB:
        return {
            "n_estimators": trial.suggest_int("xgb_n_estimators", 100, 500, step=50),
            "max_depth": trial.suggest_int("xgb_max_depth", 3, 9),
            "learning_rate": trial.suggest_float("xgb_lr", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("xgb_subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("xgb_colsample", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("xgb_alpha", 1e-4, 10, log=True),
            "reg_lambda": trial.suggest_float("xgb_lambda", 1e-4, 10, log=True),
        }
    if model_type == MODEL_LGB:
        return {
            "n_estimators": trial.suggest_int("lgb_n_estimators", 100, 500, step=50),
            "num_leaves": trial.suggest_int("lgb_num_leaves", 15, 127),
            "learning_rate": trial.suggest_float("lgb_lr", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("lgb_subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("lgb_colsample", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("lgb_alpha", 1e-4, 10, log=True),
            "reg_lambda": trial.suggest_float("lgb_lambda", 1e-4, 10, log=True),
        }
    if model_type == MODEL_RF:
        return {
            "n_estimators": trial.suggest_int("rf_n_estimators", 100, 400, step=50),
            "max_depth": trial.suggest_int("rf_max_depth", 4, 16),
            "min_samples_split": trial.suggest_int("rf_min_split", 2, 20),
            "min_samples_leaf": trial.suggest_int("rf_min_leaf", 1, 10),
            "max_features": trial.suggest_categorical("rf_max_features", ["sqrt", "log2", 0.5]),
        }
    if model_type == MODEL_EXTRA_TREES:
        return {
            "n_estimators": trial.suggest_int("et_n_estimators", 100, 400, step=50),
            "max_depth": trial.suggest_int("et_max_depth", 4, 16),
            "min_samples_split": trial.suggest_int("et_min_split", 2, 20),
            "min_samples_leaf": trial.suggest_int("et_min_leaf", 1, 10),
            "max_features": trial.suggest_categorical("et_max_features", ["sqrt", "log2", 0.5]),
        }
    return {}


# _profit_at_best_threshold 扫阈值找单笔利润最大值
def _profit_at_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    n = max(len(y_true), 1)
    best = -np.inf
    for threshold in STRATEGY_THRESHOLDS:
        approved = y_proba < threshold
        bad = float(y_true[approved].sum())
        good = float(approved.sum() - bad)
        profit = (good * ASSUMED_INTEREST_MARGIN - bad * ASSUMED_LGD) / n
        if profit > best:
            best = profit
    return float(best)


# _score 根据 metric 名称返回 CV 评分
def _score(y_true: np.ndarray, y_proba: np.ndarray, metric: str) -> float:
    if metric == "auc":
        return float(roc_auc_score(y_true, y_proba))
    if metric == "pr_auc":
        return float(average_precision_score(y_true, y_proba))
    if metric == "profit":
        return _profit_at_best_threshold(y_true, y_proba)
    raise ValueError(f"未知 metric: {metric}")


# _maybe_smote 仅在 imbalance=smote 时对训练折应用 SMOTE
def _maybe_smote(X_train: np.ndarray, y_train: np.ndarray, imbalance: str):
    if imbalance != "smote":
        return X_train, y_train
    try:
        from imblearn.over_sampling import SMOTE
    except ImportError:
        return X_train, y_train
    minority = int((y_train == 1).sum())
    if minority < 6:
        return X_train, y_train
    sm = SMOTE(random_state=RANDOM_SEED, k_neighbors=min(5, max(minority - 1, 1)))
    return sm.fit_resample(X_train, y_train)


# _cv_evaluate TimeSeriesSplit 评估单个 CashConfig 在搜索集上的得分
def _cv_evaluate(
    cfg: CashConfig,
    X: pd.DataFrame,
    y: np.ndarray,
    num_cols: list[str],
    cat_cols: list[str],
    metric: str,
    cv_folds: int,
) -> float:
    tscv = TimeSeriesSplit(n_splits=cv_folds)
    scores: list[float] = []
    for ti, vi in tscv.split(X):
        X_tr, X_va = X.iloc[ti], X.iloc[vi]
        y_tr, y_va = y[ti], y[vi]
        pre = _build_preprocessor(cfg, num_cols, cat_cols)
        X_tr_t = pre.fit_transform(X_tr)
        X_va_t = pre.transform(X_va)
        # 仅训练折应用 SMOTE，验证折保持原分布
        X_tr_t, y_tr_b = _maybe_smote(X_tr_t, y_tr, cfg.imbalance)
        model = _build_model(cfg)
        model.fit(X_tr_t, y_tr_b)
        proba = model.predict_proba(X_va_t)[:, 1]
        scores.append(_score(y_va, proba, metric))
    return float(np.mean(scores))


# CashSearchResult 搜索结果
@dataclass
class CashSearchResult:
    best_config: CashConfig
    best_score: float
    best_metric: str
    trials_df: pd.DataFrame
    topk_configs: list[CashConfig]


# run_cash_search CASH 主搜索：联合搜索模型族 + 预处理 + 特征工程 + 不平衡处理 + 超参
def run_cash_search(
    X: pd.DataFrame,
    y: np.ndarray,
    num_cols: list[str],
    cat_cols: list[str],
    *,
    n_trials: int = AUTOML_CASH_N_TRIALS,
    cv_folds: int = AUTOML_CASH_CV_FOLDS,
    metric: str = AUTOML_CASH_OPTIMIZE_METRIC,
    timeout_sec: int = AUTOML_CASH_TIMEOUT_SEC,
    sample_for_search: int | None = AUTOML_CASH_SAMPLE_FOR_SEARCH,
    topk: int = AUTOML_CASH_TOPK_REFIT,
) -> CashSearchResult:
    """run_cash_search 在统一搜索空间内联合搜索模型族 / 预处理 / 特征工程 / 不平衡处理 / 超参

    1. 子采样训练集以加速搜索（保持时序）；
    2. Optuna TPESampler 联合采样模型族 + 预处理选项 + 模型超参；
    3. 每个 trial 用 TimeSeriesSplit 做 CV，目标为指定 metric；
    4. 返回最优配置 + 全量 trials 表 + Top-K 配置列表。
    """
    import optuna

    # 1. 搜索集子采样（按时间顺序保留尾部，逼近真实在线时间分布）
    if sample_for_search is not None and len(X) > sample_for_search:
        idx = np.linspace(0, len(X) - 1, sample_for_search, dtype=int)
        X_search = X.iloc[idx].reset_index(drop=True)
        y_search = y[idx]
        logger.info("CASH search: 子采样 %d / %d 行参与搜索", sample_for_search, len(X))
    else:
        X_search, y_search = X.reset_index(drop=True), y

    # 2. 定义 Optuna objective
    def objective(trial):
        # 2.1 联合采样模型族 + 预处理 + 特征工程 + 不平衡
        model_type = trial.suggest_categorical("model_type", AUTOML_MODEL_CANDIDATES)
        cfg = CashConfig(
            model_type=model_type,
            num_imputer=trial.suggest_categorical("num_imputer", AUTOML_NUM_IMPUTER_CHOICES),
            num_scaler=trial.suggest_categorical("num_scaler", AUTOML_NUM_SCALER_CHOICES),
            cat_encoder=trial.suggest_categorical("cat_encoder", AUTOML_CAT_ENCODER_CHOICES),
            feature_interaction=trial.suggest_categorical(
                "feature_interaction", AUTOML_FEATURE_INTERACTION_CHOICES
            ),
            imbalance=trial.suggest_categorical("imbalance", AUTOML_IMBALANCE_CHOICES),
            model_params=_suggest_model_params(trial, model_type),
        )
        # 2.2 LR 不需要缩放 robust 之外的 poly 交互（容易爆维）
        if cfg.model_type == MODEL_LR and cfg.feature_interaction == "poly2" and len(num_cols) > 20:
            return float("-inf")
        try:
            return _cv_evaluate(cfg, X_search, y_search, num_cols, cat_cols, metric, cv_folds)
        except Exception as exc:
            logger.warning("trial 失败: %s", exc)
            return float("-inf")

    # 3. 启动 study
    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED, multivariate=True)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    start = time.time()
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_sec,
        show_progress_bar=False,
        catch=(Exception,),
    )
    elapsed = time.time() - start
    logger.info(
        "CASH search 完成：耗时 %.1fs, trials=%d, best %s=%.4f",
        elapsed,
        len(study.trials),
        metric,
        study.best_value,
    )

    # 4. 整理 trials 表
    rows = []
    for t in study.trials:
        rows.append(
            {
                "number": t.number,
                "value": t.value,
                "state": t.state.name,
                **{f"param_{k}": v for k, v in t.params.items()},
            }
        )
    trials_df = pd.DataFrame(rows).sort_values("value", ascending=False)

    # 5. Top-K 配置（剔除失败 trial）
    completed = [t for t in study.trials if t.value is not None and t.value > float("-inf")]
    completed.sort(key=lambda t: t.value, reverse=True)
    topk_configs: list[CashConfig] = []
    for t in completed[:topk]:
        mt = t.params["model_type"]
        topk_configs.append(
            CashConfig(
                model_type=mt,
                num_imputer=t.params["num_imputer"],
                num_scaler=t.params["num_scaler"],
                cat_encoder=t.params["cat_encoder"],
                feature_interaction=t.params["feature_interaction"],
                imbalance=t.params["imbalance"],
                model_params=_extract_model_params(t.params, mt),
            )
        )

    best_cfg = topk_configs[0] if topk_configs else CashConfig(
        model_type=MODEL_XGB,
        num_imputer="median",
        num_scaler="standard",
        cat_encoder="onehot",
        feature_interaction="none",
        imbalance="none",
    )

    return CashSearchResult(
        best_config=best_cfg,
        best_score=float(study.best_value) if completed else 0.0,
        best_metric=metric,
        trials_df=trials_df,
        topk_configs=topk_configs,
    )


# _extract_model_params 从 trial.params 中提取属于该模型族的超参
def _extract_model_params(params: dict, model_type: str) -> dict:
    prefix_map = {
        MODEL_LR: "lr_",
        MODEL_XGB: "xgb_",
        MODEL_LGB: "lgb_",
        MODEL_RF: "rf_",
        MODEL_EXTRA_TREES: "et_",
    }
    prefix = prefix_map.get(model_type, "")
    rename = {
        "xgb_lr": "learning_rate",
        "xgb_alpha": "reg_alpha",
        "xgb_lambda": "reg_lambda",
        "xgb_colsample": "colsample_bytree",
        "lgb_lr": "learning_rate",
        "lgb_alpha": "reg_alpha",
        "lgb_lambda": "reg_lambda",
        "lgb_colsample": "colsample_bytree",
        "lr_C": "C",
        "rf_n_estimators": "n_estimators",
        "rf_max_depth": "max_depth",
        "rf_min_split": "min_samples_split",
        "rf_min_leaf": "min_samples_leaf",
        "rf_max_features": "max_features",
        "et_n_estimators": "n_estimators",
        "et_max_depth": "max_depth",
        "et_min_split": "min_samples_split",
        "et_min_leaf": "min_samples_leaf",
        "et_max_features": "max_features",
    }
    out = {}
    for k, v in params.items():
        if not k.startswith(prefix):
            continue
        target = rename.get(k, k[len(prefix):])
        out[target] = v
    return out


# fit_final_pipeline 用 CashConfig 在全量训练集上 refit 最终 pipeline
def fit_final_pipeline(
    cfg: CashConfig,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    num_cols: list[str],
    cat_cols: list[str],
) -> Pipeline:
    """fit_final_pipeline 在全量训练数据上重训练 pipeline，便于落盘和后续推理"""
    pre = _build_preprocessor(cfg, num_cols, cat_cols)
    X_t = pre.fit_transform(X_train)
    X_t, y_b = _maybe_smote(X_t, y_train, cfg.imbalance)
    model = _build_model(cfg)
    model.fit(X_t, y_b)
    # 1. 简单包装为透明 pipeline（便于 predict 时复用 pre.transform）
    return Pipeline([("pre", pre), ("clf", model)])


# save_search_artifacts 落盘 CASH 搜索过程产物
def save_search_artifacts(result: CashSearchResult, out_dir: Path) -> dict[str, Path]:
    """save_search_artifacts 把 CASH 搜索结果落盘为 csv + json，便于讲稿/Dashboard 引用"""
    out_dir.mkdir(parents=True, exist_ok=True)
    # 1. 全量 trials 表
    trials_path = out_dir / "cash_trials.csv"
    result.trials_df.to_csv(trials_path, index=False)
    # 2. 最优配置 + Top-K
    best_path = out_dir / "cash_best_config.json"
    payload = {
        "metric": result.best_metric,
        "best_score": result.best_score,
        "best_config": result.best_config.to_dict(),
        "topk": [cfg.to_dict() for cfg in result.topk_configs],
    }
    best_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"trials": trials_path, "best": best_path}
