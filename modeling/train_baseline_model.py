"""modeling/train_baseline_model.py 训练基准模型并对比
1. 加载训练样本（自动构造，含跨源特征）；
2. 时序划分训练/测试集（杜绝未来信息泄漏）；
3. 训练 LR / XGBoost / LightGBM；
4. 概率校准 + 校准曲线；
5. 输出 AUC、KS、准确率、召回率指标与特征重要性。
"""
from __future__ import annotations

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
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# 兼容直接 python modeling/train_baseline_model.py 调用
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    MODEL_LGB,
    MODEL_LR,
    MODEL_XGB,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODEL_FEATURE_IMPORTANCE_CSV,
    MODEL_LR_PATH,
    MODEL_METRICS_CSV,
    MODEL_PIPELINE_PATH,
    MODEL_TEST_PREDICTIONS_CSV,
    MODEL_XGB_PATH,
    MODELS_DIR,
)
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MODEL_LGB_PATH = MODELS_DIR / "lightgbm_model.joblib"
CALIBRATION_CURVE_PNG = FIGURES_DIR / "calibration_curve.png"

ALL_NUMERIC = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES


def build_preprocess_pipeline(available_columns: list[str] | None = None) -> ColumnTransformer:
    """build_preprocess_pipeline 构造预处理 ColumnTransformer"""
    from sklearn.impute import SimpleImputer

    avail = set(available_columns) if available_columns is not None else None
    num_cols = [c for c in ALL_NUMERIC if avail is None or c in avail]
    cat_cols = [c for c in CATEGORICAL_FEATURES if avail is None or c in avail]

    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    cat_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, num_cols),
            ("cat", cat_pipe, cat_cols),
        ]
    )


def evaluate(name: str, y_true: np.ndarray, y_proba: np.ndarray, threshold: float = 0.5) -> dict:
    """evaluate 计算单个模型的核心指标"""
    y_pred = (y_proba >= threshold).astype(int)
    auc = roc_auc_score(y_true, y_proba)
    order = np.argsort(-y_proba)
    cum_pos = np.cumsum(y_true[order]) / max(y_true.sum(), 1)
    cum_neg = np.cumsum(1 - y_true[order]) / max((1 - y_true).sum(), 1)
    ks = float(np.max(cum_pos - cum_neg))
    brier = brier_score_loss(y_true, y_proba)
    return {
        "model": name,
        "auc": round(auc, 4),
        "ks": round(ks, 4),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "brier": round(brier, 4),
        "default_rate_test": round(float(y_true.mean()), 4),
    }


def extract_feature_importance(pipeline: Pipeline, model_name: str) -> pd.DataFrame:
    """extract_feature_importance 提取特征重要性（兼容 LR/XGBoost/LightGBM）"""
    pre: ColumnTransformer = pipeline.named_steps["pre"]
    feature_names = pre.get_feature_names_out()
    model = pipeline.named_steps["clf"]
    if hasattr(model, "coef_"):
        importance = np.abs(model.coef_).ravel()
    elif hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
    else:
        importance = np.zeros(len(feature_names))
    df = pd.DataFrame({"model": model_name, "feature": feature_names, "importance": importance})
    return df.sort_values("importance", ascending=False)


def _plot_calibration_curve(
    y_test: np.ndarray,
    probas: dict[str, np.ndarray],
    calibrated_probas: dict[str, np.ndarray],
    out_path: Path,
):
    """绘制校准曲线对比图"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    colors = {"lr": "#e74c3c", "xgb": "#3498db", "lgb": "#2ecc71"}

    for idx, name in enumerate(["lr", "xgb", "lgb"]):
        ax = axes[idx]
        if name not in probas:
            continue

        # 校准前
        frac_pos, mean_pred = calibration_curve(y_test, probas[name], n_bins=10, strategy="uniform")
        ax.plot(mean_pred, frac_pos, "s-", color=colors[name], alpha=0.5, label="Before calibration")

        # 校准后
        frac_pos_cal, mean_pred_cal = calibration_curve(y_test, calibrated_probas[name], n_bins=10, strategy="uniform")
        ax.plot(mean_pred_cal, frac_pos_cal, "o-", color=colors[name], linewidth=2, label="After calibration")

        ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title(f"{name.upper()}")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)

    fig.suptitle("Calibration Curves (Before vs After Platt Scaling)", fontsize=14)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Calibration curve saved to %s", out_path)


def _platt_calibrate(pipeline: Pipeline, X_train, y_train, y_proba_test):
    """从训练集中划分保留集来拟合 Platt 缩放，并应用于测试预测。

    克隆 pipeline 在 80% 训练子集上训练，在 20% 保留集上校准，
    使原始 pipeline（在全量训练数据上拟合）保持不变。
    """
    from sklearn.base import clone

    n_cal = max(int(len(X_train) * 0.2), 200)
    X_tr, X_cal = X_train.iloc[:-n_cal], X_train.iloc[-n_cal:]
    y_tr, y_cal = y_train[:-n_cal], y_train[-n_cal:]

    cal_pipe = clone(pipeline)
    cal_pipe.fit(X_tr, y_tr)
    cal_proba = cal_pipe.predict_proba(X_cal)[:, 1]

    cal = LogisticRegression()
    cal.fit(cal_proba.reshape(-1, 1), y_cal)
    return cal.predict_proba(y_proba_test.reshape(-1, 1))[:, 1]


def train_and_eval():
    """train_and_eval 主训练流程（时序划分 + 三模型 + 校准）"""
    # 1. 加载样本
    df = build_training_sample()
    logger.info("Sample shape: %s, default rate=%.4f", df.shape, df[LABEL_COL].mean())

    # 2. 时序划分（杜绝未来信息泄漏）
    feature_cols = [c for c in ALL_NUMERIC + CATEGORICAL_FEATURES if c in df.columns]
    train_df, test_df = split_by_time(df)
    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train = train_df[LABEL_COL].values
    y_test = test_df[LABEL_COL].values

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    metrics: list[dict] = []
    importances: list[pd.DataFrame] = []
    probas: dict[str, np.ndarray] = {}
    calibrated_probas: dict[str, np.ndarray] = {}

    # 3.1 逻辑回归
    lr_pipe = Pipeline(
        steps=[
            ("pre", build_preprocess_pipeline(feature_cols)),
            ("clf", LogisticRegression(max_iter=500, solver="lbfgs", random_state=RANDOM_SEED)),
        ]
    )
    logger.info("Training Logistic Regression ...")
    lr_pipe.fit(X_train, y_train)
    lr_proba = lr_pipe.predict_proba(X_test)[:, 1]
    probas["lr"] = lr_proba
    lr_proba_cal = _platt_calibrate(lr_pipe, X_train, y_train, lr_proba)
    calibrated_probas["lr"] = lr_proba_cal
    metrics.append(evaluate(f"{MODEL_LR}_raw", y_test, lr_proba))
    metrics.append(evaluate(f"{MODEL_LR}_calibrated", y_test, lr_proba_cal))
    importances.append(extract_feature_importance(lr_pipe, MODEL_LR))
    joblib.dump(lr_pipe, MODEL_LR_PATH)

    # 3.2 XGBoost
    xgb_pipe = Pipeline(
        steps=[
            ("pre", build_preprocess_pipeline(feature_cols)),
            (
                "clf",
                XGBClassifier(
                    n_estimators=400, max_depth=6, learning_rate=0.05,
                    subsample=0.9, colsample_bytree=0.8,
                    eval_metric="auc", n_jobs=4,
                    random_state=RANDOM_SEED, tree_method="hist",
                ),
            ),
        ]
    )
    logger.info("Training XGBoost ...")
    xgb_pipe.fit(X_train, y_train)
    xgb_proba = xgb_pipe.predict_proba(X_test)[:, 1]
    probas["xgb"] = xgb_proba
    xgb_proba_cal = _platt_calibrate(xgb_pipe, X_train, y_train, xgb_proba)
    calibrated_probas["xgb"] = xgb_proba_cal
    metrics.append(evaluate(f"{MODEL_XGB}_raw", y_test, xgb_proba))
    metrics.append(evaluate(f"{MODEL_XGB}_calibrated", y_test, xgb_proba_cal))
    importances.append(extract_feature_importance(xgb_pipe, MODEL_XGB))
    joblib.dump(xgb_pipe, MODEL_XGB_PATH)

    # 3.3 LightGBM
    try:
        from lightgbm import LGBMClassifier
        lgb_pipe = Pipeline(
            steps=[
                ("pre", build_preprocess_pipeline(feature_cols)),
                (
                    "clf",
                    LGBMClassifier(
                        n_estimators=400, num_leaves=31, learning_rate=0.05,
                        subsample=0.9, colsample_bytree=0.8,
                        random_state=RANDOM_SEED, verbose=-1,
                    ),
                ),
            ]
        )
        logger.info("Training LightGBM ...")
        lgb_pipe.fit(X_train, y_train)
        lgb_proba = lgb_pipe.predict_proba(X_test)[:, 1]
        probas["lgb"] = lgb_proba
        lgb_proba_cal = _platt_calibrate(lgb_pipe, X_train, y_train, lgb_proba)
        calibrated_probas["lgb"] = lgb_proba_cal
        metrics.append(evaluate(f"{MODEL_LGB}_raw", y_test, lgb_proba))
        metrics.append(evaluate(f"{MODEL_LGB}_calibrated", y_test, lgb_proba_cal))
        importances.append(extract_feature_importance(lgb_pipe, MODEL_LGB))
        joblib.dump(lgb_pipe, MODEL_LGB_PATH)
    except ImportError:
        logger.warning("LightGBM not installed, skipping")

    # 4. 校准曲线
    _plot_calibration_curve(y_test, probas, calibrated_probas, CALIBRATION_CURVE_PNG)

    # 5. 持久化预测结果（用于策略模拟与 SHAP）
    test_pred_data = {"y_true": y_test, "lr_proba": lr_proba, "xgb_proba": xgb_proba}
    if "lgb" in probas:
        test_pred_data["lgb_proba"] = probas["lgb"]
    pd.DataFrame(test_pred_data).to_csv(MODEL_TEST_PREDICTIONS_CSV, index=False)

    # 6. 输出指标与重要性
    pd.DataFrame(metrics).to_csv(MODEL_METRICS_CSV, index=False)
    pd.concat(importances, ignore_index=True).to_csv(MODEL_FEATURE_IMPORTANCE_CSV, index=False)

    # 7. 保留预处理 pipeline 以便 SHAP 复用
    joblib.dump(xgb_pipe.named_steps["pre"], MODEL_PIPELINE_PATH)

    logger.info("Done. Metrics:\n%s", pd.DataFrame(metrics).to_string(index=False))


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    train_and_eval()


if __name__ == "__main__":
    main()
