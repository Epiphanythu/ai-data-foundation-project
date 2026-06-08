"""scripts/run_explainability.py 可解释性分析（SHAP + 决策追溯 + 跨模型一致性）

1. 加载已训练模型（LR / XGBoost / LightGBM）；
2. 在测试集上计算 SHAP 值（而非训练集随机子集）；
3. 跨模型 SHAP 排名一致性：Spearman 相关系数；
4. 决策追溯 + 审计报告（修复 MultiMethodExplainer bug）。
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr

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
    ADV_SHAP_BEESWARM_PNG,
    ADV_SHAP_HEATMAP_PNG,
    ADV_SHAP_INTERACTION_PNG,
    ADVANCED_FIGURES_DIR,
    FIGURES_DIR,
    MODEL_LR_PATH,
    MODEL_PIPELINE_PATH,
    MODEL_TEST_PREDICTIONS_CSV,
    MODEL_XGB_PATH,
    MODELS_DIR,
    PDP_DIR,
    SHAP_BAR_PNG,
    SHAP_SUMMARY_PNG,
    SHAP_VALUES_NPZ,
    TABLES_DIR,
)
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

SHAP_SAMPLE_SIZE = 5000
PDP_TOP_K = 4
ALL_NUMERIC = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES
CROSS_MODEL_CONSISTENCY_PNG = FIGURES_DIR / "cross_model_shap_consistency.png"
DECISION_LOGS_JSON = TABLES_DIR / "decision_logs.json"
DECISION_AUDIT_MD = TABLES_DIR / "decision_audit_report.md"


# =====================
# Decision Tracker（保留原有逻辑）
# =====================

class DecisionTracker:
    """决策追溯器"""

    def __init__(self):
        self.decision_logs = []

    def log_decision(self, application_id, features, probability, threshold, decision, rules=None):
        self.decision_logs.append({
            "timestamp": datetime.now().isoformat(),
            "application_id": application_id,
            "features": features.to_dict(),
            "probability": float(probability),
            "threshold": float(threshold),
            "decision": decision,
            "rules": rules or [],
        })

    def export_logs(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.decision_logs, f, ensure_ascii=False, indent=2)

    def generate_audit_report(self, filepath):
        df = pd.DataFrame(self.decision_logs)
        report = f"""# 决策审计报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 概览
- 总决策数: {len(df)}
- 通过数: {len(df[df['decision'] == 'accept'])}
- 拒绝数: {len(df[df['decision'] == 'reject'])}
- 通过率: {len(df[df['decision'] == 'accept']) / len(df) * 100:.2f}%
"""
        filepath.write_text(report, encoding="utf-8")


# =====================
# 工具函数
# =====================

def _get_feature_importance_rank(pipeline) -> dict[str, int] | None:
    """从 Pipeline 中提取特征重要性排名（高重要性 → 排名 1）。

    修复：正确访问 pipeline.named_steps["clf"].feature_importances_
    """
    pre = pipeline.named_steps["pre"]
    feature_names = pre.get_feature_names_out()
    clf = pipeline.named_steps["clf"]

    if hasattr(clf, "feature_importances_"):
        importance = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importance = np.abs(clf.coef_).ravel()
    else:
        return None

    # 排序：高重要性 → rank 1
    order = np.argsort(-importance)
    rank_map = {feature_names[i]: rank + 1 for rank, i in enumerate(order)}
    return rank_map


def _compute_cross_model_consistency():
    """计算不同模型间 SHAP 特征排名的 Spearman 相关系数。

    加载已训练的 LR 和 XGBoost Pipeline，从 built-in feature_importance 提取排名，
    计算 Spearman 秩相关系数，展示两个模型在"哪些特征重要"上是否一致。
    """
    model_paths = {
        MODEL_LR: MODEL_LR_PATH,
        MODEL_XGB: MODEL_XGB_PATH,
    }
    lgb_path = MODELS_DIR / "lightgbm_model.joblib"
    if lgb_path.exists():
        model_paths[MODEL_LGB] = lgb_path

    ranks = {}
    for name, path in model_paths.items():
        if not path.exists():
            logger.warning("Model %s not found: %s", name, path)
            continue
        pipeline = joblib.load(path)
        rank_map = _get_feature_importance_rank(pipeline)
        if rank_map:
            ranks[name] = rank_map

    if len(ranks) < 2:
        logger.warning("Need at least 2 models for cross-model consistency analysis")
        return

    # 取两个模型共有的特征，计算 Spearman
    model_names = sorted(ranks.keys())
    n_models = len(model_names)
    corr_matrix = np.zeros((n_models, n_models))

    for i, m1 in enumerate(model_names):
        for j, m2 in enumerate(model_names):
            common = sorted(set(ranks[m1]) & set(ranks[m2]))
            r1 = [ranks[m1][f] for f in common]
            r2 = [ranks[m2][f] for f in common]
            if len(common) >= 5:
                rho, _ = spearmanr(r1, r2)
                corr_matrix[i, j] = round(rho, 3)
            else:
                corr_matrix[i, j] = np.nan

    # 绘制热力图
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr_matrix, cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(n_models))
    ax.set_yticks(range(n_models))
    ax.set_xticklabels(model_names, rotation=45)
    ax.set_yticklabels(model_names)
    for i in range(n_models):
        for j in range(n_models):
            ax.text(j, i, str(corr_matrix[i, j]), ha="center", va="center", fontsize=12, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Spearman's ρ")
    ax.set_title("Cross-Model Feature Importance Consistency\n(Spearman Rank Correlation)")
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CROSS_MODEL_CONSISTENCY_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Cross-model consistency matrix saved: %s", CROSS_MODEL_CONSISTENCY_PNG)

    # 输出数值
    for i, m1 in enumerate(model_names):
        for j, m2 in enumerate(model_names):
            if j > i:
                logger.info("  %s vs %s: ρ = %.3f", m1, m2, corr_matrix[i, j])


# =====================
# SHAP 主流程
# =====================

def run_shap():
    """在测试集上计算 SHAP（XGBoost），生成所有图表。"""
    if not MODEL_XGB_PATH.exists():
        raise FileNotFoundError(f"XGBoost model not found: {MODEL_XGB_PATH}")

    pipeline = joblib.load(MODEL_XGB_PATH)
    pre = pipeline.named_steps["pre"]

    # 获取测试集（时序划分）
    df = build_training_sample(sample_size=None)
    _, test_df = split_by_time(df)
    feature_cols = [c for c in ALL_NUMERIC + CATEGORICAL_FEATURES if c in df.columns]
    X_test = test_df[feature_cols]

    # SHAP 抽样（测试集上采样）
    n_samples = min(SHAP_SAMPLE_SIZE, len(X_test))
    X_sample = X_test.sample(n=n_samples, random_state=RANDOM_SEED)

    X_trans = pre.transform(X_sample)
    feature_names = pre.get_feature_names_out()

    logger.info("Computing SHAP on test set: %d rows x %d features", X_trans.shape[0], X_trans.shape[1])
    explainer = shap.TreeExplainer(pipeline.named_steps["clf"])
    shap_values = explainer.shap_values(X_trans)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    ADVANCED_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # --- Summary plot ---
    plt.figure()
    shap.summary_plot(shap_values, X_trans, feature_names=feature_names, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(SHAP_SUMMARY_PNG, dpi=120)
    plt.close()
    logger.info("Saved %s", SHAP_SUMMARY_PNG)

    # --- Bar plot ---
    plt.figure()
    shap.summary_plot(shap_values, X_trans, feature_names=feature_names, plot_type="bar", show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(SHAP_BAR_PNG, dpi=120)
    plt.close()
    logger.info("Saved %s", SHAP_BAR_PNG)

    # --- Persist SHAP values ---
    np.savez_compressed(SHAP_VALUES_NPZ, shap_values=shap_values, feature_names=feature_names)

    # --- Beeswarm ---
    explanation = shap.Explanation(values=shap_values, data=X_trans, feature_names=list(feature_names))
    plt.figure()
    shap.plots.beeswarm(explanation, max_display=20, show=False)
    plt.tight_layout()
    plt.savefig(ADV_SHAP_BEESWARM_PNG, dpi=130)
    plt.close()
    logger.info("Saved %s", ADV_SHAP_BEESWARM_PNG)

    # --- Interaction: FICO × interest rate ---
    fico_candidates = [n for n in feature_names if "fico" in n.lower()]
    intrate_candidates = [n for n in feature_names if "int_rate" in n.lower()]
    if fico_candidates and intrate_candidates:
        f_main, f_color = fico_candidates[0], intrate_candidates[0]
        idx_main = list(feature_names).index(f_main)
        idx_color = list(feature_names).index(f_color)
        fig, ax = plt.subplots(figsize=(8, 6))
        sc = ax.scatter(X_trans[:, idx_main], shap_values[:, idx_main],
                        c=X_trans[:, idx_color], cmap="coolwarm", s=10, alpha=0.6)
        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label(f"{f_color} (standardized)")
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_xlabel(f"{f_main} (standardized)")
        ax.set_ylabel(f"SHAP value of {f_main}")
        ax.set_title("Interaction: FICO marginal contribution, colored by interest rate")
        plt.tight_layout()
        plt.savefig(ADV_SHAP_INTERACTION_PNG, dpi=130)
        plt.close()
        logger.info("Saved %s", ADV_SHAP_INTERACTION_PNG)

    # --- Heatmap ---
    try:
        plt.figure(figsize=(12, 6))
        shap.plots.heatmap(explanation, max_display=15, show=False)
        plt.tight_layout()
        plt.savefig(ADV_SHAP_HEATMAP_PNG, dpi=130)
        plt.close()
        logger.info("Saved %s", ADV_SHAP_HEATMAP_PNG)
    except Exception as exc:
        logger.warning("SHAP heatmap failed: %s", exc)

    # --- PDP ---
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
        plt.title(f"SHAP Dependence: {feat_name}")
        plt.tight_layout()
        out_path = PDP_DIR / f"pdp_{feat_name.replace('__', '_')}.png"
        plt.savefig(out_path, dpi=110)
        plt.close()
        logger.info("Saved %s", out_path)


# =====================
# 决策追溯
# =====================

def run_decision_tracking():
    """决策追溯：在测试集上对 XGBoost 模型前 200 条记录做决策记录。"""
    if not MODEL_XGB_PATH.exists():
        logger.warning("XGBoost model not found, skipping decision tracking")
        return

    pipeline = joblib.load(MODEL_XGB_PATH)
    df = build_training_sample(sample_size=None)
    _, test_df = split_by_time(df)
    feature_cols = [c for c in ALL_NUMERIC + CATEGORICAL_FEATURES if c in test_df.columns]
    X_test = test_df[feature_cols]

    tracker = DecisionTracker()
    for i in range(min(200, len(X_test))):
        prob = pipeline.predict_proba(X_test.iloc[[i]])[0, 1]
        decision = "reject" if prob >= 0.5 else "accept"
        tracker.log_decision(f"APP_{i:06d}", X_test.iloc[i], prob, 0.5, decision)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tracker.export_logs(DECISION_LOGS_JSON)
    tracker.generate_audit_report(DECISION_AUDIT_MD)
    logger.info("Decision logs: %s / Audit: %s", DECISION_LOGS_JSON, DECISION_AUDIT_MD)


# =====================
# 入口
# =====================

def run():
    logger.info("=" * 50)
    logger.info("Part 1: SHAP analysis on test set")
    logger.info("=" * 50)
    run_shap()

    logger.info("=" * 50)
    logger.info("Part 2: Cross-model SHAP consistency")
    logger.info("=" * 50)
    _compute_cross_model_consistency()

    logger.info("=" * 50)
    logger.info("Part 3: Decision tracking & audit")
    logger.info("=" * 50)
    run_decision_tracking()

    logger.info("Explainability analysis complete.")


def main():
    run()


if __name__ == "__main__":
    main()
