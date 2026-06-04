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
    ADV_SHAP_BEESWARM_PNG,
    ADV_SHAP_HEATMAP_PNG,
    ADV_SHAP_INTERACTION_PNG,
    ADVANCED_FIGURES_DIR,
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

# 全局风格统一
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

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

    # 3.4 进阶 SHAP：beeswarm / 交互效应 / heatmap（学术与工业风控常用）
    ADVANCED_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    explanation = shap.Explanation(
        values=shap_values,
        data=X_trans,
        feature_names=list(feature_names),
    )
    # 3.4.1 Beeswarm（颜色 = 特征值，比 summary 更直观）
    plt.figure()
    shap.plots.beeswarm(explanation, max_display=20, show=False)
    plt.tight_layout()
    plt.savefig(ADV_SHAP_BEESWARM_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_SHAP_BEESWARM_PNG)

    # 3.4.2 交互效应散点：FICO 主特征 × 利率 颜色（金融风控经典视角）
    fico_candidates = [n for n in feature_names if "fico" in n.lower()]
    intrate_candidates = [n for n in feature_names if "int_rate" in n.lower()]
    if fico_candidates and intrate_candidates:
        f_main = fico_candidates[0]
        f_color = intrate_candidates[0]
        idx_main = list(feature_names).index(f_main)
        idx_color = list(feature_names).index(f_color)
        fig, ax = plt.subplots(figsize=(8, 6))
        sc = ax.scatter(
            X_trans[:, idx_main],
            shap_values[:, idx_main],
            c=X_trans[:, idx_color],
            cmap="coolwarm",
            s=10,
            alpha=0.6,
        )
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label(f"{f_color}（标准化）")
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_xlabel(f"{f_main}（标准化）")
        ax.set_ylabel(f"SHAP value of {f_main}")
        ax.set_title("交互效应：FICO 对违约的边际贡献，按利率着色")
        plt.tight_layout()
        plt.savefig(ADV_SHAP_INTERACTION_PNG, dpi=130)
        plt.close()
        logger.info("Saved %s", ADV_SHAP_INTERACTION_PNG)

    # 3.4.3 Heatmap：样本聚类下的特征贡献矩阵
    try:
        plt.figure(figsize=(12, 6))
        shap.plots.heatmap(explanation, max_display=15, show=False)
        plt.tight_layout()
        plt.savefig(ADV_SHAP_HEATMAP_PNG, dpi=130)
        plt.close()
        logger.info("Saved %s", ADV_SHAP_HEATMAP_PNG)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SHAP heatmap 绘制失败：%s", exc)

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
