"""scripts/train_baseline_model.py 训练基准模型并对比
1. 加载训练样本（自动构造）；
2. 切分训练/测试集；
3. 训练逻辑回归与 XGBoost；
4. 输出 AUC、KS、准确率、召回率指标与特征重要性。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# 兼容直接 python scripts/xxx.py 调用
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    MODEL_LR,
    MODEL_XGB,
    NUMERIC_FEATURES,
    RANDOM_SEED,
    TEST_SIZE,
)
from constant.paths import (  # noqa: E402
    MODEL_FEATURE_IMPORTANCE_CSV,
    MODEL_LR_PATH,
    MODEL_METRICS_CSV,
    MODEL_PIPELINE_PATH,
    MODEL_TEST_PREDICTIONS_CSV,
    MODEL_XGB_PATH,
    MODELS_DIR,
)
from scripts._model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def build_preprocess_pipeline() -> ColumnTransformer:
    """build_preprocess_pipeline 构造预处理 ColumnTransformer
    数值列：中位数填充 + 标准化；类别列：OneHotEncoder。
    """
    from sklearn.impute import SimpleImputer

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
            ("num", numeric_pipe, NUMERIC_FEATURES),
            ("cat", cat_pipe, CATEGORICAL_FEATURES),
        ]
    )


def evaluate(name: str, y_true: np.ndarray, y_proba: np.ndarray, threshold: float = 0.5) -> dict:
    """evaluate 计算单个模型的核心指标"""
    y_pred = (y_proba >= threshold).astype(int)
    auc = roc_auc_score(y_true, y_proba)
    # KS 统计：累积 TPR 与 FPR 之差的最大值
    order = np.argsort(-y_proba)
    cum_pos = np.cumsum(y_true[order]) / max(y_true.sum(), 1)
    cum_neg = np.cumsum(1 - y_true[order]) / max((1 - y_true).sum(), 1)
    ks = float(np.max(cum_pos - cum_neg))
    return {
        "model": name,
        "auc": round(auc, 4),
        "ks": round(ks, 4),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "default_rate_test": round(float(y_true.mean()), 4),
    }


def extract_feature_importance(pipeline: Pipeline, model_name: str) -> pd.DataFrame:
    """extract_feature_importance 提取特征重要性（兼容 LR/XGBoost）"""
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


def train_and_eval():
    """train_and_eval 主训练流程
    1. 加载样本；
    2. 切分；
    3. 训练 LR、XGBoost；
    4. 落盘指标、模型与特征重要性。
    """
    # 1. 加载样本
    df = build_training_sample()
    logger.info("Sample shape: %s, default rate=%.4f", df.shape, df[LABEL_COL].mean())

    # 2. 切分训练/测试集（按标签分层）
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[LABEL_COL].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    metrics: list[dict] = []
    importances: list[pd.DataFrame] = []

    # 3.1 逻辑回归
    lr_pipe = Pipeline(
        steps=[
            ("pre", build_preprocess_pipeline()),
            ("clf", LogisticRegression(max_iter=300, n_jobs=None, solver="lbfgs")),
        ]
    )
    logger.info("Training Logistic Regression ...")
    lr_pipe.fit(X_train, y_train)
    lr_proba = lr_pipe.predict_proba(X_test)[:, 1]
    metrics.append(evaluate(MODEL_LR, y_test, lr_proba))
    importances.append(extract_feature_importance(lr_pipe, MODEL_LR))
    joblib.dump(lr_pipe, MODEL_LR_PATH)

    # 3.2 XGBoost
    xgb_pipe = Pipeline(
        steps=[
            ("pre", build_preprocess_pipeline()),
            (
                "clf",
                XGBClassifier(
                    n_estimators=400,
                    max_depth=6,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.8,
                    eval_metric="auc",
                    n_jobs=4,
                    random_state=RANDOM_SEED,
                    tree_method="hist",
                ),
            ),
        ]
    )
    logger.info("Training XGBoost ...")
    xgb_pipe.fit(X_train, y_train)
    xgb_proba = xgb_pipe.predict_proba(X_test)[:, 1]
    metrics.append(evaluate(MODEL_XGB, y_test, xgb_proba))
    importances.append(extract_feature_importance(xgb_pipe, MODEL_XGB))
    joblib.dump(xgb_pipe, MODEL_XGB_PATH)

    # 4. 持久化预测结果（用于策略模拟与 SHAP）
    test_pred = pd.DataFrame(
        {
            "y_true": y_test,
            "lr_proba": lr_proba,
            "xgb_proba": xgb_proba,
        }
    )
    test_pred.to_csv(MODEL_TEST_PREDICTIONS_CSV, index=False)

    # 5. 输出指标与重要性
    pd.DataFrame(metrics).to_csv(MODEL_METRICS_CSV, index=False)
    pd.concat(importances, ignore_index=True).to_csv(MODEL_FEATURE_IMPORTANCE_CSV, index=False)

    # 6. 同时保留预处理 pipeline 以便 SHAP 复用
    joblib.dump(xgb_pipe.named_steps["pre"], MODEL_PIPELINE_PATH)

    logger.info("Done. Metrics:\n%s", pd.DataFrame(metrics).to_string(index=False))


def main():
    train_and_eval()


if __name__ == "__main__":
    main()
