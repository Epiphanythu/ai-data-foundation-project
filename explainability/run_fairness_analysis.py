"""explainability/run_fairness_analysis.py 模型公平性分析（Responsible AI）

评估模型在不同子群体上的公平性，覆盖三个维度：
1. Demographic Parity — 不同群体通过率是否一致
2. Equal Opportunity — 相同真实风险的人被拒绝概率是否一致
3. Disparate Impact — 是否存在系统性偏见

产出嵌入监控链路：公平性指标持续恶化时触发重训告警（被 run_model_monitoring.py 引用）。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_GRADE, COL_ADDR_STATE, COL_ISSUE_YEAR  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import FIGURES_DIR, TABLES_DIR, MODEL_XGB_PATH  # noqa: E402
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

FAIRNESS_REPORT_CSV = TABLES_DIR / "fairness_report.csv"
FAIRNESS_BAR_PNG = FIGURES_DIR / "fairness_disparity_bar.png"
FAIRNESS_STATE_PNG = FIGURES_DIR / "fairness_state_heatmap.png"


def _load_model():
    import joblib
    if MODEL_XGB_PATH.exists():
        return joblib.load(MODEL_XGB_PATH)
    from constant.paths import MODEL_LR_PATH
    if MODEL_LR_PATH.exists():
        return joblib.load(MODEL_LR_PATH)
    raise FileNotFoundError("No trained model found.")


def demographic_parity(y_pred: pd.Series, group: pd.Series, group_name: str) -> list[dict]:
    """计算各群体的通过率差异。Demographic Parity = P(accept | group)"""
    df = pd.DataFrame({"pred": y_pred, "group": group})
    overall_pass = 1 - y_pred.mean()
    rows = []
    for grp in sorted(group.dropna().unique()):
        mask = df["group"] == grp
        if mask.sum() < 50:
            continue
        grp_pass = 1 - df.loc[mask, "pred"].mean()
        disparity = grp_pass - overall_pass
        rows.append({
            "metric": "demographic_parity",
            "group_name": group_name,
            "group_value": str(grp),
            "n_samples": int(mask.sum()),
            "group_pass_rate": round(float(grp_pass), 4),
            "overall_pass_rate": round(float(overall_pass), 4),
            "disparity": round(float(disparity), 4),
            "disparity_pct": round(float(disparity / max(overall_pass, 0.01)) * 100, 1),
        })
    return rows


def equal_opportunity(y_true: pd.Series, y_pred: pd.Series, group: pd.Series, group_name: str) -> list[dict]:
    """Equal Opportunity：真实违约者中，被正确识别（拒绝）的比例在群体间一致。

    TPR = P(reject | truly bad)，我们希望这个值在不同群体间接近。
    """
    df = pd.DataFrame({"true": y_true, "pred": y_pred, "group": group})
    bad = df["true"] == 1
    overall_recall = (df.loc[bad, "pred"]).mean() if bad.sum() > 0 else 0
    rows = []
    for grp in sorted(group.dropna().unique()):
        mask = (df["group"] == grp) & bad
        if mask.sum() < 10:
            continue
        grp_recall = df.loc[mask, "pred"].mean()
        disparity = grp_recall - overall_recall
        rows.append({
            "metric": "equal_opportunity",
            "group_name": group_name,
            "group_value": str(grp),
            "n_bad": int(mask.sum()),
            "group_recall": round(float(grp_recall), 4),
            "overall_recall": round(float(overall_recall), 4),
            "disparity": round(float(disparity), 4),
            "disparity_pct": round(float(disparity / max(overall_recall, 0.01)) * 100, 1),
        })
    return rows


def disparate_impact_ratio(y_pred: pd.Series, group: pd.Series, group_name: str,
                           reference_group: Optional[str] = None) -> list[dict]:
    """Disparate Impact Ratio = 最差组通过率 / 最优组通过率。

    通常 < 0.8 视为需要审查的差异（美国 EEOC 四分之三规则）。
    """
    df = pd.DataFrame({"pred": y_pred, "group": group})
    pass_rates = {}
    for grp in sorted(group.dropna().unique()):
        mask = df["group"] == grp
        if mask.sum() < 50:
            continue
        pass_rates[str(grp)] = 1 - df.loc[mask, "pred"].mean()

    if len(pass_rates) < 2:
        return []

    best_group = max(pass_rates, key=pass_rates.get)
    best_rate = pass_rates[best_group]
    rows = []
    for grp, rate in pass_rates.items():
        di = rate / best_rate if best_rate > 0 else 1.0
        rows.append({
            "metric": "disparate_impact_ratio",
            "group_name": group_name,
            "group_value": grp,
            "pass_rate": round(float(rate), 4),
            "reference_group": best_group,
            "reference_rate": round(float(best_rate), 4),
            "di_ratio": round(float(di), 4),
            "flag": "⚠ 待审查" if di < 0.8 else "通过",
        })
    return rows


def _plot_disparity_bars(rows: list[dict], metric_name: str, out_path: Path):
    """按群体画差异柱状图"""
    df = pd.DataFrame(rows)
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(max(8, len(df) * 0.4), 5))
    values = df["disparity"].values
    colors = ["#e74c3c" if v > 0.05 else ("#3498db" if v < -0.05 else "#95a5a6") for v in values]
    labels = [f"{r['group_name']}={r['group_value']}" for _, r in df.iterrows()]
    ax.barh(range(len(labels)), values, color=colors, alpha=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.axvline(0.05, color="orange", linestyle="--", alpha=0.5, label="±5% threshold")
    ax.axvline(-0.05, color="orange", linestyle="--", alpha=0.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Disparity vs Overall")
    ax.set_title(f"Fairness: {metric_name}")
    ax.legend(fontsize=7)
    ax.invert_yaxis()
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def run():
    logger.info("=" * 60)
    logger.info("Model Fairness Analysis (Responsible AI)")
    logger.info("=" * 60)

    # 加载数据 + 模型
    df = build_training_sample(sample_size=60000, enable_macro=True, enable_state=True)
    model = _load_model()
    feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES + CATEGORICAL_FEATURES
                    if c in df.columns]
    X = df[feature_cols]
    y = df[LABEL_COL]
    y_proba = model.predict_proba(X)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    all_rows: list[dict] = []

    # 1. 按 Grade 分析
    if COL_GRADE in df.columns:
        all_rows.extend(demographic_parity(pd.Series(y_pred, index=df.index), df[COL_GRADE], "grade"))
        all_rows.extend(equal_opportunity(y, pd.Series(y_pred, index=df.index), df[COL_GRADE], "grade"))
        all_rows.extend(disparate_impact_ratio(pd.Series(y_pred, index=df.index), df[COL_GRADE], "grade"))
        _plot_disparity_bars(
            [r for r in all_rows if r["metric"] == "demographic_parity" and r["group_name"] == "grade"],
            "Demographic Parity by Grade",
            FIGURES_DIR / "fairness_grade_dp.png",
        )

    # 2. 按 State 分析（取贷款量最大的 15 个州）
    if COL_ADDR_STATE in df.columns:
        top_states = df[COL_ADDR_STATE].value_counts().head(15).index.tolist()
        state_mask = df[COL_ADDR_STATE].isin(top_states)
        all_rows.extend(disparate_impact_ratio(
            pd.Series(y_pred, index=df.index)[state_mask],
            df.loc[state_mask, COL_ADDR_STATE],
            "state",
        ))
        _plot_disparity_bars(
            [r for r in all_rows if r["metric"] == "disparate_impact_ratio" and r["group_name"] == "state"],
            "Disparate Impact by State",
            FAIRNESS_STATE_PNG,
        )

    # 3. 综合公平性图
    summary_rows = [r for r in all_rows if r["metric"] == "demographic_parity"]
    if summary_rows:
        _plot_disparity_bars(summary_rows, "Demographic Parity (all groups)", FAIRNESS_BAR_PNG)

    # 4. 生成报告
    report = pd.DataFrame(all_rows)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    report.to_csv(FAIRNESS_REPORT_CSV, index=False)

    # 高差异项
    high_disparity = [r for r in all_rows if abs(r.get("disparity", 0)) > 0.05]
    if high_disparity:
        logger.warning("Found %d high-disparity cases:", len(high_disparity))
        for r in high_disparity[:5]:
            logger.warning("  %s=%s: disparity=%.4f", r["group_name"], r["group_value"], r["disparity"])

    logger.info("Fairness report saved: %s (%d rows)", FAIRNESS_REPORT_CSV, len(report))
    return report


def main():
    run()


if __name__ == "__main__":
    main()
