"""scripts/run_automl.py AutoML 自动化建模模块

1. 三模型自动对比（LR / XGBoost / LightGBM）+ Stacking Ensemble
2. RFE 特征选择 + 时序稳定性分析
3. Optuna TPE 贝叶斯优化（TimeSeriesSplit CV，30 trials）
4. 最佳模型自动落地
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
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import StackingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
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
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    MODEL_LGB,
    MODEL_LR,
    MODEL_STACKING,
    MODEL_XGB,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODELS_DIR,
    TABLES_DIR,
)
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ALL_NUMERIC = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES

# 输出路径
AUTOML_DIR = TABLES_DIR / "automl"
AUTOML_DIR.mkdir(parents=True, exist_ok=True)
BEST_PARAMS_JSON = AUTOML_DIR / "best_params.json"
TRIALS_CSV = AUTOML_DIR / "trials.csv"
OPT_HISTORY_PNG = FIGURES_DIR / "optimization_history.png"
HYPERPARAM_IMPORTANCE_PNG = FIGURES_DIR / "hyperparameter_importance.png"
MODEL_COMPARISON_CSV = AUTOML_DIR / "model_comparison.csv"
FEATURE_SELECTION_PNG = FIGURES_DIR / "feature_selection_curve.png"
TEMPORAL_IMPORTANCE_PNG = FIGURES_DIR / "temporal_importance_heatmap.png"
BEST_MODEL_PATH = MODELS_DIR / "best_model.joblib"
BEST_MODEL_METRICS_CSV = MODELS_DIR / "best_model_metrics.csv"


def _build_preprocessor() -> ColumnTransformer:
    num_cols = [c for c in ALL_NUMERIC]
    cat_cols = [c for c in CATEGORICAL_FEATURES]
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
    pre = _build_preprocessor()
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

def _run_optuna(X_train, y_train, model_type: str, n_trials: int = AUTOML_N_TRIALS):
    """对指定模型类型运行 Optuna TPE 优化"""
    try:
        import optuna
    except ImportError:
        logger.warning("optuna not installed, using default params")
        return _default_params(model_type), []

    pre = _build_preprocessor()
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


# =====================
# 3. Stacking Ensemble
# =====================

def _build_stacking(params_xgb: dict, params_lgb: dict, params_lr: dict) -> Pipeline:
    """构建 Stacking Ensemble: LR + XGBoost + LightGBM 基学习器, LR 元学习器"""
    pre = _build_preprocessor()

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
    stack = StackingClassifier(estimators=estimators, final_estimator=meta, cv="prefit", passthrough=True)
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

    # --- 特征选择 ---
    run_feature_selection(train_df, y_train, feature_cols)

    # --- Optuna 优化 ---
    logger.info("Optuna optimization for XGBoost...")
    best_xgb, trials_xgb = _run_optuna(X_train, y_train, MODEL_XGB)
    logger.info("Optuna optimization for LightGBM...")
    best_lgb, trials_lgb = _run_optuna(X_train, y_train, MODEL_LGB)
    logger.info("Optuna optimization for LR...")
    best_lr, trials_lr = _run_optuna(X_train, y_train, MODEL_LR)

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
    pre = _build_preprocessor()
    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)
    feature_names = pre.get_feature_names_out()

    comparison = _train_all_models(X_train_t, y_train, X_test_t, y_test, best_xgb, best_lgb, best_lr, pre, feature_cols)

    # 保存模型对比
    comparison.to_csv(MODEL_COMPARISON_CSV, index=False)
    logger.info("Model comparison:\n%s", comparison.to_string(index=False))

    # --- 最佳模型落地 ---
    best_row = comparison.sort_values("auc", ascending=False).iloc[0]
    logger.info("Best model: %s (AUC=%.4f)", best_row["model"], best_row["auc"])
    comparison.to_csv(BEST_MODEL_METRICS_CSV, index=False)

    logger.info("AutoML pipeline complete.")


def _train_all_models(X_train_t, y_train, X_test_t, y_test, best_xgb, best_lgb, best_lr, pre, feature_cols):
    """训练四模型并返回对比表"""
    rows = []

    # LR
    lr = LogisticRegression(C=best_lr.get("C", 1.0), max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)
    lr.fit(X_train_t, y_train)
    rows.append(_eval_model(MODEL_LR, lr, X_test_t, y_test))

    # XGBoost (AutoML-tuned, saved separately from baseline)
    xgb = XGBClassifier(**(best_xgb or {}), eval_metric="auc", random_state=RANDOM_SEED, tree_method="hist", n_jobs=4)
    xgb.fit(X_train_t, y_train)
    rows.append(_eval_model(MODEL_XGB, xgb, X_test_t, y_test))
    joblib.dump(Pipeline([("pre", pre), ("clf", xgb)]), MODELS_DIR / "automl_xgboost_model.joblib")

    # LightGBM
    try:
        from lightgbm import LGBMClassifier
        lgb = LGBMClassifier(**(best_lgb or {}), random_state=RANDOM_SEED, verbose=-1)
        lgb.fit(X_train_t, y_train)
        rows.append(_eval_model(MODEL_LGB, lgb, X_test_t, y_test))
        joblib.dump(Pipeline([("pre", pre), ("clf", lgb)]), MODELS_DIR / "automl_lightgbm_model.joblib")
    except ImportError:
        pass

    # Stacking (use pre-fit individual models)
    try:
        stack_pipe = _build_stacking(best_xgb, best_lgb, best_lr)
        stack_pipe.fit(X_train_t, y_train)
        rows.append(_eval_model(MODEL_STACKING, stack_pipe, X_test_t, y_test))
        joblib.dump(stack_pipe, BEST_MODEL_PATH)
    except Exception as exc:
        logger.warning("Stacking failed: %s", exc)

    return pd.DataFrame(rows)


def _eval_model(name, model, X_test, y_test):
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    order = np.argsort(-y_proba)
    cum_pos = np.cumsum(y_test[order]) / max(y_test.sum(), 1)
    cum_neg = np.cumsum(1 - y_test[order]) / max((1 - y_test).sum(), 1)
    ks = float(np.max(cum_pos - cum_neg))
    return {
        "model": name, "auc": round(roc_auc_score(y_test, y_proba), 4),
        "ks": round(ks, 4), "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
    }


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


def main():
    run()


if __name__ == "__main__":
    main()
