"""scripts/run_shap_analysis.py 模型可解释性分析
1. 加载 XGBoost 模型与训练样本；
2. 抽样后计算 SHAP 值；
3. 生成 SHAP summary、bar、PDP 图。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODEL_XGB_PATH,
    PDP_DIR,
    SHAP_BAR_PNG,
    SHAP_SUMMARY_PNG,
    SHAP_VALUES_NPZ,
)
from scripts._model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# SHAP 抽样规模（控制在合理时间内）
SHAP_SAMPLE_SIZE = 5000
PDP_TOP_K = 4


def run():
    """run SHAP/PDP 主流程
    1. 载入模型与样本；
    2. 计算 SHAP；
    3. 输出 summary/bar；
    4. 生成 Top-K 数值特征 PDP。
    """
    # 1. 载入模型与样本
    if not MODEL_XGB_PATH.exists():
        raise FileNotFoundError(f"未找到模型，请先运行 train_baseline_model.py：{MODEL_XGB_PATH}")
    pipeline = joblib.load(MODEL_XGB_PATH)
    df = build_training_sample()
    sample = df.sample(n=min(SHAP_SAMPLE_SIZE, len(df)), random_state=RANDOM_SEED)
    X = sample[NUMERIC_FEATURES + CATEGORICAL_FEATURES]

    # 2. 走预处理后再喂 SHAP（保证特征空间一致）
    pre = pipeline.named_steps["pre"]
    X_trans = pre.transform(X)
    feature_names = pre.get_feature_names_out()

    logger.info("Computing SHAP values for %d rows / %d features ...", X_trans.shape[0], X_trans.shape[1])
    explainer = shap.TreeExplainer(pipeline.named_steps["clf"])
    shap_values = explainer.shap_values(X_trans)

    # 3.1 SHAP summary（散点）
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure()
    shap.summary_plot(shap_values, X_trans, feature_names=feature_names, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(SHAP_SUMMARY_PNG, dpi=120)
    plt.close()
    logger.info("Saved %s", SHAP_SUMMARY_PNG)

    # 3.2 SHAP bar（全局重要性）
    plt.figure()
    shap.summary_plot(shap_values, X_trans, feature_names=feature_names, plot_type="bar", show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(SHAP_BAR_PNG, dpi=120)
    plt.close()
    logger.info("Saved %s", SHAP_BAR_PNG)

    # 3.3 持久化 SHAP 值（供 Dashboard 复用）
    np.savez_compressed(SHAP_VALUES_NPZ, shap_values=shap_values, feature_names=feature_names)

    # 4. PDP：取 Top-K 重要的数值特征
    PDP_DIR.mkdir(parents=True, exist_ok=True)
    mean_abs = np.abs(shap_values).mean(axis=0)
    importance_df = pd.DataFrame({"feature": feature_names, "importance": mean_abs})
    numeric_top = (
        importance_df[importance_df["feature"].str.startswith("num__")]
        .sort_values("importance", ascending=False)
        .head(PDP_TOP_K)
    )
    for _, row in numeric_top.iterrows():
        feat_name = row["feature"]
        col_idx = list(feature_names).index(feat_name)
        values = X_trans[:, col_idx]
        order = np.argsort(values)
        plt.figure()
        plt.scatter(values[order], shap_values[order, col_idx], s=4, alpha=0.4)
        plt.xlabel(feat_name)
        plt.ylabel("SHAP value")
        plt.title(f"PDP-like: {feat_name}")
        plt.tight_layout()
        out_path = PDP_DIR / f"pdp_{feat_name.replace('__', '_')}.png"
        plt.savefig(out_path, dpi=110)
        plt.close()
        logger.info("Saved %s", out_path)


def main():
    run()


if __name__ == "__main__":
    main()
