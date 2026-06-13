"""modeling/run_automl.py 状态感知 AutoML 自动化建模模块

1. 特征组消融：Base / Temporal / Cross-source / All；
2. RFE 特征选择 + 时序稳定性分析；
3. CASH 联合搜索：模型族 × 预处理 × 特征工程 × 不平衡处理 × 超参；
4. Optuna TPE 单模型贝叶斯优化（兼容旧逻辑）；
5. Stacking Ensemble + 多指标评估（AUC / KS / PR-AUC / Brier / Top Decile / 利润阈值）；
6. 自动输出 AutoML 证据表和 Markdown 结论报告。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import StackingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import COL_ISSUE_YEAR, LABEL_COL  # noqa: E402
from constant.model import (  # noqa: E402
    AUTOML_CV_FOLDS,
    AUTOML_N_TRIALS,
    AUTOML_RFE_MIN_FEATURES,
    AUTOML_RFE_STEP,
    ASSUMED_INTEREST_MARGIN,
    ASSUMED_LGD,
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    DEFAULT_THRESHOLD,
    FEATURE_SET_BASE,
    FEATURE_SET_WITH_MACRO,
    FEATURE_SET_WITH_REGION,
    MODEL_LGB,
    MODEL_LR,
    MODEL_STACKING,
    MODEL_XGB,
    NUMERIC_FEATURES,
    RANDOM_SEED,
    STRATEGY_THRESHOLDS,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODELS_DIR,
    TABLES_DIR,
)
from common.model_data import build_training_sample, split_by_time  # noqa: E402
from modeling.automl_cash import (  # noqa: E402
    fit_final_pipeline as cash_fit_final_pipeline,
    run_cash_search,
    save_search_artifacts as cash_save_artifacts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ALL_NUMERIC = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES


def _filter_existing(columns: list[str], df: pd.DataFrame) -> list[str]:
    """只保留当前样本中真实存在的字段，避免跨源特征缺失时中断 AutoML。"""
    return [col for col in columns if col in df.columns]


def _feature_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    """构造 AutoML 消融用特征组，体现状态/宏观/地区特征是否带来增益。"""
    base_num = _filter_existing(
        [
            "loan_amnt",
            "int_rate",
            "annual_inc",
            "dti",
            "fico_avg",
            "term_months",
            "installment",
            "revol_util",
            "open_acc",
            "delinq_2yrs",
        ],
        df,
    )
    temporal_num = _filter_existing(NUMERIC_FEATURES, df)
    cross_num = _filter_existing(CROSS_SOURCE_NUMERIC_FEATURES, df)
    cat = _filter_existing(CATEGORICAL_FEATURES, df)
    return {
        FEATURE_SET_BASE: base_num + cat,
        "with_temporal": temporal_num + cat,
        FEATURE_SET_WITH_MACRO: base_num + cross_num + cat,
        FEATURE_SET_WITH_REGION: base_num + cross_num + cat,
        "all_state_aware": temporal_num + cross_num + cat,
    }

# 输出路径
AUTOML_DIR = TABLES_DIR / "automl"
AUTOML_DIR.mkdir(parents=True, exist_ok=True)
BEST_PARAMS_JSON = AUTOML_DIR / "best_params.json"
TRIALS_CSV = AUTOML_DIR / "trials.csv"
OPT_HISTORY_PNG = FIGURES_DIR / "optimization_history.png"
HYPERPARAM_IMPORTANCE_PNG = FIGURES_DIR / "hyperparameter_importance.png"
MODEL_COMPARISON_CSV = AUTOML_DIR / "model_comparison.csv"
FEATURE_SET_COMPARISON_CSV = AUTOML_DIR / "feature_set_comparison.csv"
BUSINESS_METRICS_CSV = AUTOML_DIR / "business_metrics.csv"
AUTOML_SUMMARY_MD = AUTOML_DIR / "automl_summary.md"
FEATURE_SELECTION_PNG = FIGURES_DIR / "feature_selection_curve.png"
TEMPORAL_IMPORTANCE_PNG = FIGURES_DIR / "temporal_importance_heatmap.png"
BEST_MODEL_PATH = MODELS_DIR / "best_model.joblib"
BEST_MODEL_METRICS_CSV = MODELS_DIR / "best_model_metrics.csv"


def _build_preprocessor(available_columns: list[str] | None = None) -> ColumnTransformer:
    avail = set(available_columns) if available_columns is not None else None
    num_cols = [c for c in ALL_NUMERIC if avail is None or c in avail]
    cat_cols = [c for c in CATEGORICAL_FEATURES if avail is None or c in avail]
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    cat_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, num_cols),
        ("cat", cat_pipe, cat_cols),
    ])


def _get_feature_names(pre: ColumnTransformer, X: pd.DataFrame) -> np.ndarray:
    pre.fit(X)
    return pre.get_feature_names_out()


# =====================
# 1. Feature Selection (RFE + Temporal Stability)
# =====================

def run_feature_selection(X_train, y_train, feature_cols):
    """RFE 特征选择 + 时序稳定性分析"""
    logger.info("Running RFE feature selection...")
    pre = _build_preprocessor(feature_cols)
    X_t = pre.fit_transform(X_train)
    feat_names = pre.get_feature_names_out()

    # 初始 XGBoost 计算全局重要性
    xgb = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                        random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    xgb.fit(X_t, y_train)
    importance = xgb.feature_importances_

    # RFE 逐步删除
    n_total = len(feat_names)
    rfe_auc: list[tuple[int, float]] = []
    kept_indices = list(range(n_total))

    while len(kept_indices) > AUTOML_RFE_MIN_FEATURES:
        X_sub = X_t[:, kept_indices]
        tscv = TimeSeriesSplit(n_splits=min(3, AUTOML_CV_FOLDS))
        aucs = []
        for ti, vi in tscv.split(X_sub):
            m = XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.05,
                              random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
            m.fit(X_sub[ti], y_train[ti])
            aucs.append(roc_auc_score(y_train[vi], m.predict_proba(X_sub[vi])[:, 1]))
        rfe_auc.append((len(kept_indices), np.mean(aucs)))

        # 删除重要性最低的特征
        sub_importance = importance[kept_indices]
        worst = kept_indices[int(np.argmin(sub_importance))]
        kept_indices.remove(worst)

        if len(kept_indices) % 5 == 0:
            logger.info("  RFE: %d features, AUC=%.4f", len(kept_indices), rfe_auc[-1][1])

    # 绘制 RFE 曲线
    counts, aucs_rfe = zip(*rfe_auc)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(counts, aucs_rfe, "b-o", markersize=4)
    ax.set_xlabel("Number of features")
    ax.set_ylabel("AUC (CV mean)")
    ax.set_title("RFE Feature Selection: AUC vs Number of Features")
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FEATURE_SELECTION_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Feature selection curve saved: %s", FEATURE_SELECTION_PNG)

    # 时序特征重要性热力图
    # 按年份分组计算 XGBoost 特征重要性
    years = sorted(X_train[COL_ISSUE_YEAR].dropna().unique())
    if len(years) >= 3:
        temporal_imp = {}
        for year in years:
            mask = X_train[COL_ISSUE_YEAR] == year
            if mask.sum() < 100:
                continue
            yr_x = pre.transform(X_train[mask])
            yr_y = y_train[mask]
            m = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.05,
                              random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
            m.fit(yr_x, yr_y)
            temporal_imp[int(year)] = m.feature_importances_

        if len(temporal_imp) > 1:
            imp_df = pd.DataFrame(temporal_imp, index=feat_names).fillna(0)
            # 只显示 top-15 重要特征
            top15 = imp_df.mean(axis=1).sort_values(ascending=False).head(15).index
            imp_top = imp_df.loc[top15]

            fig, ax = plt.subplots(figsize=(12, 6))
            im = ax.imshow(imp_top.values, cmap="YlOrRd", aspect="auto")
            ax.set_xticks(range(len(imp_top.columns)))
            ax.set_xticklabels([str(int(y)) for y in imp_top.columns], rotation=45)
            ax.set_yticks(range(len(imp_top.index)))
            ax.set_yticklabels(imp_top.index, fontsize=7)
            plt.colorbar(im, ax=ax, label="Feature importance")
            ax.set_title("Temporal Feature Importance (XGBoost per year)")
            plt.tight_layout()
            fig.savefig(TEMPORAL_IMPORTANCE_PNG, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Temporal importance heatmap saved: %s", TEMPORAL_IMPORTANCE_PNG)

    return list(feat_names)


# =====================
# 2. Optuna 贝叶斯优化
# =====================

def _run_optuna(X_train, y_train, model_type: str, feature_cols: list[str], n_trials: int = AUTOML_N_TRIALS):
    """对指定模型类型运行 Optuna TPE 优化"""
    try:
        import optuna
    except ImportError:
        logger.warning("optuna not installed, using default params")
        return _default_params(model_type), []

    pre = _build_preprocessor(feature_cols)
    X_t = pre.fit_transform(X_train)

    tscv = TimeSeriesSplit(n_splits=AUTOML_CV_FOLDS)

    def objective(trial):
        if model_type == MODEL_XGB:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10, log=True),
            }
            model = XGBClassifier(**params, eval_metric="auc", random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
        elif model_type == MODEL_LGB:
            try:
                from lightgbm import LGBMClassifier
            except ImportError:
                return 0.5
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10, log=True),
            }
            model = LGBMClassifier(**params, random_state=RANDOM_SEED, verbose=-1)
        elif model_type == MODEL_LR:
            params = {
                "C": trial.suggest_float("C", 0.001, 100, log=True),
            }
            model = LogisticRegression(**params, max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)
        else:
            return 0.5

        aucs = []
        for ti, vi in tscv.split(X_t):
            model.fit(X_t[ti], y_train[ti])
            aucs.append(roc_auc_score(y_train[vi], model.predict_proba(X_t[vi])[:, 1]))
        return np.mean(aucs)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, n_trials=min(n_trials, AUTOML_N_TRIALS), show_progress_bar=False)

    logger.info("  %s best AUC=%.4f, params=%s", model_type, study.best_value, study.best_params)
    return study.best_params, study.trials


def _default_params(model_type: str) -> dict:
    if model_type == MODEL_XGB:
        return {"n_estimators": 400, "max_depth": 6, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.8}
    elif model_type == MODEL_LGB:
        return {"n_estimators": 400, "num_leaves": 31, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.8}
    elif model_type == MODEL_LR:
        return {"C": 1.0}
    return {}


def _ks_stat(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """计算 KS 统计量。"""
    order = np.argsort(-y_proba)
    y_sorted = y_true[order]
    cum_pos = np.cumsum(y_sorted) / max(y_sorted.sum(), 1)
    cum_neg = np.cumsum(1 - y_sorted) / max((1 - y_sorted).sum(), 1)
    return float(np.max(cum_pos - cum_neg))


def _top_decile_capture(y_true: np.ndarray, y_proba: np.ndarray) -> tuple[float, float]:
    """返回 Top Decile 坏账率和坏账捕获率。"""
    top_n = max(1, int(len(y_true) * 0.10))
    order = np.argsort(-y_proba)[:top_n]
    top_bad = y_true[order].sum()
    return float(top_bad / top_n), float(top_bad / max(y_true.sum(), 1))


def _business_threshold_metrics(y_true: np.ndarray, y_proba: np.ndarray) -> dict:
    """扫描审批阈值，输出利润最优点和对应业务指标。"""
    total_bad = y_true.sum()
    best_row: dict | None = None
    for threshold in STRATEGY_THRESHOLDS:
        approved = y_proba < threshold
        bad_in_approved = y_true[approved].sum()
        good_count = approved.sum() - bad_in_approved
        profit_per_loan = (
            good_count * ASSUMED_INTEREST_MARGIN - bad_in_approved * ASSUMED_LGD
        ) / max(len(y_true), 1)
        row = {
            "best_profit_threshold": round(float(threshold), 2),
            "approve_rate_at_best_profit": round(float(approved.mean()), 4),
            "bad_rate_at_best_profit": round(float(bad_in_approved / max(approved.sum(), 1)), 4),
            "bad_recall_at_best_profit": round(float((total_bad - bad_in_approved) / max(total_bad, 1)), 4),
            "profit_per_loan_at_best_profit": round(float(profit_per_loan), 4),
        }
        if best_row is None or row["profit_per_loan_at_best_profit"] > best_row["profit_per_loan_at_best_profit"]:
            best_row = row
    return best_row or {}


def _evaluate_proba(y_true: np.ndarray, y_proba: np.ndarray) -> dict:
    """统一输出模型统计指标和业务指标。"""
    top_bad_rate, top_bad_capture = _top_decile_capture(y_true, y_proba)
    return {
        "auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "ks": round(_ks_stat(y_true, y_proba), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_proba)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_proba)), 4),
        "top_decile_bad_rate": round(top_bad_rate, 4),
        "top_decile_bad_capture": round(top_bad_capture, 4),
        **_business_threshold_metrics(y_true, y_proba),
    }


def run_feature_set_ablation(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    """用轻量 XGBoost 验证不同特征组是否提升状态感知建模效果。"""
    rows = []
    y_train = train_df[LABEL_COL].to_numpy()
    y_test = test_df[LABEL_COL].to_numpy()
    for feature_set, cols in _feature_sets(train_df).items():
        cols = [col for col in cols if col in train_df.columns and col in test_df.columns]
        if not cols:
            continue
        pre = _build_preprocessor(cols)
        X_train_t = pre.fit_transform(train_df[cols])
        X_test_t = pre.transform(test_df[cols])
        model = XGBClassifier(
            n_estimators=250,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.8,
            eval_metric="auc",
            random_state=RANDOM_SEED,
            tree_method="hist",
            n_jobs=4,
        )
        model.fit(X_train_t, y_train)
        y_proba = model.predict_proba(X_test_t)[:, 1]
        rows.append(
            {
                "feature_set": feature_set,
                "feature_count": len(cols),
                **_evaluate_proba(y_test, y_proba),
            }
        )
    result = pd.DataFrame(rows).sort_values("auc", ascending=False)
    result.to_csv(FEATURE_SET_COMPARISON_CSV, index=False)
    logger.info("Feature-set ablation saved: %s", FEATURE_SET_COMPARISON_CSV)
    return result


# =====================
# 3. Stacking Ensemble
# =====================

def _build_stacking(params_xgb: dict, params_lgb: dict, params_lr: dict, feature_cols: list[str]) -> Pipeline:
    """构建 Stacking Ensemble: LR + XGBoost + LightGBM 基学习器, LR 元学习器"""
    pre = _build_preprocessor(feature_cols)

    estimators = [
        ("lr", LogisticRegression(
            C=params_lr.get("C", 1.0), max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)),
        ("xgb", XGBClassifier(
            **(params_xgb or _default_params(MODEL_XGB)),
            eval_metric="auc", random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)),
    ]

    try:
        from lightgbm import LGBMClassifier
        estimators.append(("lgb", LGBMClassifier(
            **(params_lgb or _default_params(MODEL_LGB)),
            random_state=RANDOM_SEED, verbose=-1)))
    except ImportError:
        pass

    meta = LogisticRegression(C=1.0, max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)
    stack = StackingClassifier(estimators=estimators, final_estimator=meta, cv=3, passthrough=True)
    return Pipeline([("pre", pre), ("clf", stack)])


# =====================
# 4. 主流程
# =====================

def run():
    logger.info("=" * 60)
    logger.info("AutoML Pipeline Start")
    logger.info("=" * 60)

    # 加载数据（时序划分）
    df = build_training_sample(sample_size=None)
    feature_cols = [c for c in ALL_NUMERIC + CATEGORICAL_FEATURES if c in df.columns]
    train_df, test_df = split_by_time(df)
    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train = train_df[LABEL_COL].values
    y_test = test_df[LABEL_COL].values

    logger.info("Train: %d x %d, Test: %d x %d", len(X_train), len(feature_cols), len(X_test), len(feature_cols))

    # --- 状态/宏观/时序特征组消融 ---
    feature_set_comparison = run_feature_set_ablation(train_df, test_df)

    # --- 特征选择 ---
    run_feature_selection(train_df, y_train, feature_cols)

    # --- Optuna 优化 ---
    logger.info("Optuna optimization for XGBoost...")
    best_xgb, trials_xgb = _run_optuna(X_train, y_train, MODEL_XGB, feature_cols)
    logger.info("Optuna optimization for LightGBM...")
    best_lgb, trials_lgb = _run_optuna(X_train, y_train, MODEL_LGB, feature_cols)
    logger.info("Optuna optimization for LR...")
    best_lr, trials_lr = _run_optuna(X_train, y_train, MODEL_LR, feature_cols)

    # 保存 best_params
    best_all = {MODEL_XGB: best_xgb, MODEL_LGB: best_lgb, MODEL_LR: best_lr}
    with BEST_PARAMS_JSON.open("w") as f:
        json.dump(best_all, f, indent=2, default=str)
    logger.info("Best params saved: %s", BEST_PARAMS_JSON)

    # 保存 trials
    all_trials = []
    for name, trials in [(MODEL_XGB, trials_xgb), (MODEL_LGB, trials_lgb), (MODEL_LR, trials_lr)]:
        if not hasattr(trials, "__iter__"):
            continue
        for t in trials:
            all_trials.append({
                "model": name, "number": t.number, "value": t.value,
                "params": json.dumps(t.params, default=str),
            })
    pd.DataFrame(all_trials).to_csv(TRIALS_CSV, index=False)

    # --- Optuna 可视化 ---
    _plot_optimization_history(trials_xgb, MODEL_XGB)
    _plot_hyperparam_importance(trials_xgb, MODEL_XGB)

    # --- 训练所有模型 + 对比 ---
    pre = _build_preprocessor(feature_cols)
    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)
    comparison, business_metrics = _train_all_models(
        X_train,
        X_test,
        X_train_t,
        y_train,
        X_test_t,
        y_test,
        best_xgb,
        best_lgb,
        best_lr,
        pre,
        feature_cols,
    )

    # --- CASH 联合搜索（真正的 AutoML：模型族 × 预处理 × 特征工程 × 不平衡 × 超参） ---
    cash_metrics_row = _run_cash_stage(
        X_train,
        y_train,
        X_test,
        y_test,
        feature_cols,
    )
    cash_result = None
    if cash_metrics_row is not None:
        comparison = pd.concat([comparison, pd.DataFrame([cash_metrics_row["model_metrics"]])], ignore_index=True)
        business_metrics = pd.concat(
            [business_metrics, pd.DataFrame([cash_metrics_row["business_metrics"]])], ignore_index=True
        )
        cash_result = cash_metrics_row.get("cash_result")

    # 保存模型对比
    comparison.to_csv(MODEL_COMPARISON_CSV, index=False)
    business_metrics.to_csv(BUSINESS_METRICS_CSV, index=False)
    logger.info("Model comparison:\n%s", comparison.to_string(index=False))

    # --- 最佳模型落地 ---
    best_row = comparison.sort_values("auc", ascending=False).iloc[0]
    logger.info("Best model: %s (AUC=%.4f)", best_row["model"], best_row["auc"])
    comparison.to_csv(BEST_MODEL_METRICS_CSV, index=False)
    _write_automl_summary(feature_set_comparison, comparison, business_metrics, best_all, cash_result)

    logger.info("AutoML pipeline complete.")


def _train_all_models(
    X_train,
    X_test,
    X_train_t,
    y_train,
    X_test_t,
    y_test,
    best_xgb,
    best_lgb,
    best_lr,
    pre,
    feature_cols,
):
    """训练四模型并返回对比表"""
    rows = []
    business_rows = []

    # LR
    lr = LogisticRegression(C=best_lr.get("C", 1.0), max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)
    lr.fit(X_train_t, y_train)
    model_metrics, business_metrics = _eval_model(MODEL_LR, lr, X_test_t, y_test)
    rows.append(model_metrics)
    business_rows.append(business_metrics)

    # XGBoost (AutoML-tuned, saved separately from baseline)
    xgb = XGBClassifier(**(best_xgb or {}), eval_metric="auc", random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    xgb.fit(X_train_t, y_train)
    model_metrics, business_metrics = _eval_model(MODEL_XGB, xgb, X_test_t, y_test)
    rows.append(model_metrics)
    business_rows.append(business_metrics)
    joblib.dump(Pipeline([("pre", pre), ("clf", xgb)]), MODELS_DIR / "automl_xgboost_model.joblib")

    # LightGBM
    try:
        from lightgbm import LGBMClassifier
        lgb = LGBMClassifier(**(best_lgb or {}), random_state=RANDOM_SEED, verbose=-1)
        lgb.fit(X_train_t, y_train)
        model_metrics, business_metrics = _eval_model(MODEL_LGB, lgb, X_test_t, y_test)
        rows.append(model_metrics)
        business_rows.append(business_metrics)
        joblib.dump(Pipeline([("pre", pre), ("clf", lgb)]), MODELS_DIR / "automl_lightgbm_model.joblib")
    except ImportError:
        pass

    # Stacking (use pre-fit individual models)
    try:
        stack_pipe = _build_stacking(best_xgb, best_lgb, best_lr, feature_cols)
        stack_pipe.fit(X_train, y_train)
        model_metrics, business_metrics = _eval_model(MODEL_STACKING, stack_pipe, X_test, y_test)
        rows.append(model_metrics)
        business_rows.append(business_metrics)
        joblib.dump(stack_pipe, BEST_MODEL_PATH)
    except Exception as exc:
        logger.warning("Stacking failed: %s", exc)

    return pd.DataFrame(rows), pd.DataFrame(business_rows)


def _eval_model(name, model, X_test, y_test):
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= DEFAULT_THRESHOLD).astype(int)
    proba_metrics = _evaluate_proba(y_test, y_proba)
    model_metrics = {
        "model": name,
        "auc": proba_metrics["auc"],
        "ks": proba_metrics["ks"],
        "pr_auc": proba_metrics["pr_auc"],
        "brier_score": proba_metrics["brier_score"],
        "accuracy_at_0_5": round(accuracy_score(y_test, y_pred), 4),
        "precision_at_0_5": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall_at_0_5": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "top_decile_bad_rate": proba_metrics["top_decile_bad_rate"],
        "top_decile_bad_capture": proba_metrics["top_decile_bad_capture"],
    }
    business_metrics = {
        "model": name,
        **{key: value for key, value in proba_metrics.items() if "best_profit" in key},
    }
    return model_metrics, business_metrics


def _plot_optimization_history(trials, model_name):
    """绘制优化历史曲线"""
    if not hasattr(trials, "__iter__"):
        return
    values = [t.value for t in trials if t.value is not None]
    if not values:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, len(values) + 1), values, "b-", alpha=0.6)
    best = np.maximum.accumulate(values)
    ax.plot(range(1, len(best) + 1), best, "r-", linewidth=2, label="Best so far")
    ax.set_xlabel("Trial")
    ax.set_ylabel("AUC")
    ax.set_title(f"Optuna Optimization History ({model_name})")
    ax.legend()
    plt.tight_layout()
    # 命名区分多模型
    out = FIGURES_DIR / f"optimization_history_{model_name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Optimization history saved: %s", out)


def _plot_hyperparam_importance(trials, model_name):
    """绘制超参数重要性图"""
    try:
        import optuna
    except ImportError:
        return
    if not hasattr(trials, "__iter__") or len(list(trials)) < 5:
        return
    try:
        study = optuna.create_study(direction="maximize")
        for t in trials:
            study.add_trial(t)
        importance = optuna.importance.get_param_importances(study)
        if not importance:
            return
        names, values = zip(*sorted(importance.items(), key=lambda x: x[1]))
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.barh(names, values, color="steelblue")
        ax.set_xlabel("Importance")
        ax.set_title(f"Hyperparameter Importance ({model_name})")
        plt.tight_layout()
        out = FIGURES_DIR / f"hyperparameter_importance_{model_name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Hyperparameter importance saved: %s", out)
    except Exception as exc:
        logger.warning("Hyperparam importance plot failed: %s", exc)


def _write_automl_summary(
    feature_set_comparison: pd.DataFrame,
    model_comparison: pd.DataFrame,
    business_metrics: pd.DataFrame,
    best_params: dict,
    cash_result=None,
) -> None:
    """输出 AutoML 自动总结，服务报告、Dashboard 和答辩表述。"""
    best_feature = feature_set_comparison.sort_values("auc", ascending=False).iloc[0]
    best_model = model_comparison.sort_values("auc", ascending=False).iloc[0]
    best_business = business_metrics.sort_values("profit_per_loan_at_best_profit", ascending=False).iloc[0]
    base_rows = feature_set_comparison[feature_set_comparison["feature_set"] == FEATURE_SET_BASE]
    auc_lift = None
    if not base_rows.empty:
        auc_lift = float(best_feature["auc"] - base_rows.iloc[0]["auc"])

    lines = [
        "# AutoML 状态感知建模总结",
        "",
        "## 1. 模块定位",
        "",
        "本模块不是单纯调参，而是验证不同特征组、模型族和业务阈值在非平稳信贷风险场景下的表现。",
        "",
        "## 2. 特征组消融结论",
        "",
        f"- 最优特征组：`{best_feature['feature_set']}`，AUC = `{best_feature['auc']}`，KS = `{best_feature['ks']}`。",
    ]
    if auc_lift is not None:
        lines.append(f"- 相比 `{FEATURE_SET_BASE}`，最优特征组 AUC 变化为 `{auc_lift:+.4f}`。")
    lines.extend(
        [
            f"- Top Decile 坏账捕获率：`{best_feature['top_decile_bad_capture']}`。",
            "",
            "## 3. 模型族自动选择结论",
            "",
            f"- 最优模型：`{best_model['model']}`，AUC = `{best_model['auc']}`，PR-AUC = `{best_model['pr_auc']}`。",
            f"- 校准误差 Brier Score = `{best_model['brier_score']}`，Top Decile 捕获率 = `{best_model['top_decile_bad_capture']}`。",
            "",
            "## 4. 业务阈值结论",
            "",
            f"- 利润最优模型：`{best_business['model']}`。",
            f"- 利润最优阈值：`{best_business['best_profit_threshold']}`。",
            f"- 该阈值下通过率：`{best_business['approve_rate_at_best_profit']}`，坏账率：`{best_business['bad_rate_at_best_profit']}`。",
            f"- 单笔利润估算：`{best_business['profit_per_loan_at_best_profit']}`。",
            "",
            "## 5. 单模型最优参数",
            "",
            "```json",
            json.dumps(best_params, indent=2, ensure_ascii=False, default=str),
            "```",
        ]
    )
    # 6. CASH 联合搜索结论（真正的 AutoML：模型族 + 预处理 + 特征工程 + 不平衡 + 超参一站搜）
    if cash_result is not None:
        cfg = cash_result.best_config
        lines.extend(
            [
                "",
                "## 6. CASH 联合搜索结论（真正的 AutoML）",
                "",
                f"- 搜索 metric：`{cash_result.best_metric}`，best CV score = `{cash_result.best_score:.4f}`。",
                f"- 自动选中模型族：`{cfg.model_type}`。",
                f"- 自动选中预处理：imputer=`{cfg.num_imputer}`，scaler=`{cfg.num_scaler}`，cat_encoder=`{cfg.cat_encoder}`。",
                f"- 自动选中特征工程：`{cfg.feature_interaction}`。",
                f"- 自动选中不平衡处理：`{cfg.imbalance}`。",
                f"- 完整 trials 数：`{len(cash_result.trials_df)}`，Top-K 配置已落盘到 `cash_best_config.json`。",
                "",
                "**自动选中的模型超参：**",
                "",
                "```json",
                json.dumps(cfg.model_params, indent=2, ensure_ascii=False, default=str),
                "```",
            ]
        )
    AUTOML_SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    logger.info("AutoML summary saved: %s", AUTOML_SUMMARY_MD)


def main():
    run()


# AUTOML_CASH_DIR CASH 搜索产物目录
AUTOML_CASH_DIR = AUTOML_DIR / "cash"
CASH_BEST_MODEL_PATH = MODELS_DIR / "automl_cash_best_model.joblib"


def _run_cash_stage(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    feature_cols: list[str],
) -> dict | None:
    """_run_cash_stage CASH 联合搜索阶段：模型族 × 预处理 × 特征工程 × 不平衡 × 超参一站搜
    1. 列分类：从 feature_cols 中拆出数值列和类别列；
    2. 调用 run_cash_search 在子采样训练集上搜索最优配置；
    3. 用最优配置在全量训练集 refit 最终 pipeline；
    4. 在测试集评估，并返回与 _train_all_models 一致格式的指标行。
    """
    # 1. 拆分数值列和类别列
    num_cols = [c for c in feature_cols if c in ALL_NUMERIC]
    cat_cols = [c for c in feature_cols if c in CATEGORICAL_FEATURES]
    if not num_cols and not cat_cols:
        logger.warning("CASH 搜索跳过：无可用列。")
        return None
    # 2. 联合搜索
    logger.info("CASH 联合搜索启动：模型族 + 预处理 + 特征工程 + 不平衡 + 超参...")
    try:
        result = run_cash_search(
            X_train[feature_cols],
            np.asarray(y_train),
            num_cols,
            cat_cols,
        )
    except Exception as exc:
        logger.warning("CASH 搜索失败：%s", exc)
        return None
    # 3. 落盘搜索过程产物
    cash_save_artifacts(result, AUTOML_CASH_DIR)
    logger.info(
        "CASH best：%s | metric=%s score=%.4f",
        result.best_config.model_type,
        result.best_metric,
        result.best_score,
    )
    # 4. 用最优配置在全量训练集上 refit
    try:
        final_pipe = cash_fit_final_pipeline(
            result.best_config,
            X_train[feature_cols],
            np.asarray(y_train),
            num_cols,
            cat_cols,
        )
    except Exception as exc:
        logger.warning("CASH refit 失败：%s", exc)
        return None
    # 5. 测试集评估并落盘最优 pipeline
    model_metrics, business_metrics = _eval_model(
        "automl_cash",
        final_pipe,
        X_test[feature_cols],
        y_test,
    )
    joblib.dump(final_pipe, CASH_BEST_MODEL_PATH)
    logger.info("CASH 最优 pipeline 落盘：%s", CASH_BEST_MODEL_PATH)
    # 6. 可视化：优化历史 + 模型族分布
    _plot_cash_history(result.trials_df)
    _plot_cash_model_family(result.trials_df)
    return {
        "model_metrics": model_metrics,
        "business_metrics": business_metrics,
        "cash_result": result,
    }


def _plot_cash_history(trials_df: pd.DataFrame) -> None:
    """_plot_cash_history 绘制 CASH 联合搜索的优化历史曲线（每 trial 分数 + best-so-far）"""
    if trials_df.empty or "value" not in trials_df.columns:
        return
    df = trials_df.dropna(subset=["value"]).sort_values("number")
    if df.empty:
        return
    values = df["value"].to_numpy()
    best = np.maximum.accumulate(values)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df["number"], values, "o", markersize=3, alpha=0.5, label="trial")
    ax.plot(df["number"], best, "r-", linewidth=2, label="best so far")
    ax.set_xlabel("Trial number")
    ax.set_ylabel("CV score (CASH metric)")
    ax.set_title("CASH 联合搜索优化历史")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out = FIGURES_DIR / "cash_optimization_history.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("CASH 优化历史图保存：%s", out)


def _plot_cash_model_family(trials_df: pd.DataFrame) -> None:
    """_plot_cash_model_family 绘制 CASH 各模型族 trial 分布与最优分数"""
    if trials_df.empty or "param_model_type" not in trials_df.columns:
        return
    df = trials_df.dropna(subset=["value"])
    if df.empty:
        return
    grouped = df.groupby("param_model_type")["value"].agg(["count", "mean", "max"]).sort_values("max", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(grouped.index, grouped["max"], color="steelblue", alpha=0.85, label="best")
    ax.bar(grouped.index, grouped["mean"], color="orange", alpha=0.7, label="mean")
    ax.set_ylabel("CV score")
    ax.set_title("CASH 各模型族表现（best vs mean）")
    ax.legend()
    plt.tight_layout()
    out = FIGURES_DIR / "cash_model_family_distribution.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("CASH 模型族分布图保存：%s", out)


if __name__ == "__main__":
    main()
