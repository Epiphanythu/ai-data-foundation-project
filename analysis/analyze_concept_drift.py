"""scripts/analyze_concept_drift.py 概念漂移检测（PSI + 分布偏移）

1. Population Stability Index (PSI)：逐关键特征、逐年 vs 基准年
2. 特征均值/标准差年度偏移
3. 违约率时序趋势（年度 + 季度）
4. 模型分数分布偏移（若已有模型）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import (
    COL_FICO_AVG,
    COL_INT_RATE,
    COL_ISSUE_YEAR,
    COL_LOAN_AMNT,
    LABEL_COL,
)
from constant.model import RANDOM_SEED
from constant.paths import FIGURES_DIR, TABLES_DIR
from common.model_data import find_lending_club_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

PSI_CSV = TABLES_DIR / "concept_drift_psi.csv"
DRIFT_MEAN_PNG = FIGURES_DIR / "concept_drift_feature_mean_shift.png"
DEFAULT_TREND_PNG = FIGURES_DIR / "concept_drift_default_trend.png"
PSI_HEATMAP_PNG = FIGURES_DIR / "concept_drift_psi_heatmap.png"
DRIFT_REPORT_MD = TABLES_DIR / "concept_drift_report.md"

SAMPLE_N = 300000
PSI_THRESHOLD_MODERATE = 0.10
PSI_THRESHOLD_HIGH = 0.25

# 关键特征（存在且可计算 PSI）
KEY_FEATURES = [
    COL_LOAN_AMNT, COL_INT_RATE, COL_FICO_AVG,
    "annual_inc", "dti", "revol_util", "installment", "open_acc",
]


def _calc_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """计算 Population Stability Index。

    expected: 基准分布样本
    actual: 待比较分布样本
    bins: 分箱数
    """
    if len(expected) < bins or len(actual) < bins:
        return np.nan

    # 在 expected 上确定分箱边界
    bin_edges = np.percentile(expected, np.linspace(0, 100, bins + 1))
    # 去重边界
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 3:
        return np.nan

    exp_hist, _ = np.histogram(expected, bins=bin_edges)
    act_hist, _ = np.histogram(actual, bins=bin_edges)

    # 避免零值
    exp_pct = exp_hist / exp_hist.sum()
    act_pct = act_hist / act_hist.sum()
    exp_pct = np.clip(exp_pct, 1e-6, 1)
    act_pct = np.clip(act_pct, 1e-6, 1)

    psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(psi)


def _label_status(status):
    GOOD = {"Fully Paid"}
    BAD = {"Charged Off", "Default", "Late (31-120 days)",
           "Does not meet the credit policy. Status:Charged Off"}
    if status in GOOD:
        return 0
    if status in BAD:
        return 1
    return None


def run():
    logger.info("=" * 60)
    logger.info("Concept Drift Detection (PSI + Distribution Shift)")
    logger.info("=" * 60)

    csv_path = find_lending_club_csv()
    logger.info("Loading Lending Club data: %s", csv_path)

    df = pd.read_csv(csv_path, low_memory=False)
    if len(df) > SAMPLE_N:
        df = df.sample(n=SAMPLE_N, random_state=RANDOM_SEED).copy()

    # 清洗
    df[LABEL_COL] = df["loan_status"].apply(_label_status)
    df = df.dropna(subset=[LABEL_COL])
    df[COL_FICO_AVG] = (pd.to_numeric(df["fico_range_low"], errors="coerce") +
                        pd.to_numeric(df["fico_range_high"], errors="coerce")) / 2
    df[COL_INT_RATE] = (df[COL_INT_RATE].astype(str)
                        .str.replace("%", "", regex=False).str.strip()
                        .replace({"": np.nan}).astype(float))
    df[COL_LOAN_AMNT] = pd.to_numeric(df[COL_LOAN_AMNT], errors="coerce")

    # 解析时间
    df[COL_ISSUE_YEAR] = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce").dt.year
    df["issue_quarter"] = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce").dt.to_period("Q").astype(str)
    df = df.dropna(subset=[COL_ISSUE_YEAR])

    years = sorted(df[COL_ISSUE_YEAR].dropna().unique().astype(int))
    baseline_year = years[0]
    logger.info("Years: %d - %d (baseline: %d)", years[0], years[-1], baseline_year)

    # ---- 1. PSI 逐特征逐年 vs 基准年 ----
    logger.info("--- PSI Analysis ---")
    baseline = df[df[COL_ISSUE_YEAR] == baseline_year]
    psi_matrix: list[dict] = []

    for year in years:
        year_data = df[df[COL_ISSUE_YEAR] == year]
        for feat in KEY_FEATURES:
            if feat not in df.columns:
                continue
            exp_vals = baseline[feat].dropna().values
            act_vals = year_data[feat].dropna().values
            psi_val = _calc_psi(exp_vals, act_vals)
            psi_matrix.append({
                "feature": feat, "year": int(year),
                "psi": round(psi_val, 6) if not np.isnan(psi_val) else "",
            })

    psi_df = pd.DataFrame(psi_matrix)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    psi_df.to_csv(PSI_CSV, index=False)

    # PSI 热力图
    _plot_psi_heatmap(psi_df, years)

    # ---- 2. 特征均值年度偏移 ----
    logger.info("--- Feature Mean/Std Shift ---")
    _plot_mean_shift(df, baseline, years)

    # ---- 3. 违约率时序趋势 ----
    logger.info("--- Default Rate Trend ---")
    _plot_default_trend(df, years)

    # ---- 4. 综合报告 ----
    _write_report(psi_df, years)
    logger.info("All outputs written.")


def _plot_psi_heatmap(psi_df, years):
    """PSI 热力图：特征 × 年份"""
    pivot = psi_df.pivot_table(values="psi", index="feature", columns="year", aggfunc="first")
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(max(10, len(years)), max(5, len(pivot) * 0.4)))
    # 自定义颜色：绿(低) → 黄(中) → 红(高)
    import matplotlib.colors as mcolors
    cmap = mcolors.LinearSegmentedColormap.from_list("psi", ["#2ecc71", "#f1c40f", "#e74c3c"])
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto", vmin=0, vmax=max(0.5, pivot.max().max()))
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(y)) for y in pivot.columns], rotation=45)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=9)
    # 标注
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if pd.notna(val):
                color = "white" if val > PSI_THRESHOLD_HIGH else "black"
                ax.text(j, i, f"{val:.3f}", ha="center", va="center", fontsize=7, color=color)
    plt.colorbar(im, ax=ax, label="PSI (green=stable, yellow=moderate, red=significant drift)")
    ax.set_title("Population Stability Index (PSI) by Feature × Year\nReference: first year")
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PSI_HEATMAP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", PSI_HEATMAP_PNG)


def _plot_mean_shift(df, baseline, years):
    """特征均值逐年变化（以基准年标准差为单位）"""
    available = [f for f in KEY_FEATURES if f in df.columns][:6]
    if not available:
        return

    mean_shifts: dict[str, list] = {f: [] for f in available}
    for year in years:
        year_data = df[df[COL_ISSUE_YEAR] == year]
        for feat in available:
            baseline_mean = baseline[feat].mean()
            baseline_std = baseline[feat].std()
            year_mean = year_data[feat].mean()
            shift = (year_mean - baseline_mean) / baseline_std if baseline_std > 0 else 0
            mean_shifts[feat].append(shift)

    fig, ax = plt.subplots(figsize=(12, 5))
    for feat in available:
        ax.plot(years, mean_shifts[feat], marker="o", markersize=4, label=feat[:25], linewidth=1.5)

    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
    ax.axhline(0.25, color="orange", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(-0.25, color="orange", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean Shift (in baseline std units)")
    ax.set_title("Feature Mean Drift Over Time (relative to first year)")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    ax.grid(alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DRIFT_MEAN_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", DRIFT_MEAN_PNG)


def _plot_default_trend(df, years):
    """违约率年度 + 季度趋势"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 年度违约率
    yr = df.groupby(COL_ISSUE_YEAR)[LABEL_COL].agg(["mean", "count"])
    ax1.bar(yr.index.astype(int), yr["mean"] * 100, color="steelblue", alpha=0.7)
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Default Rate (%)")
    ax1.set_title("Annual Default Rate Trend")
    ax1.grid(axis="y", alpha=0.3)

    # 季度违约率
    if "issue_quarter" in df.columns:
        qtr = df.groupby("issue_quarter")[LABEL_COL].agg(["mean", "count"])
        qtr = qtr[qtr["count"] > 500]  # 过滤小样本季度
        ax2.plot(range(len(qtr)), qtr["mean"] * 100, "o-", markersize=3, color="coral", linewidth=1.5)
        ax2.set_xlabel("Quarter (chronological)")
        ax2.set_ylabel("Default Rate (%)")
        ax2.set_title("Quarterly Default Rate Trend")
        ax2.grid(alpha=0.3)
        # 标注 x 轴刻度（每 4 个季度标一个）
        tick_indices = range(0, len(qtr), 4)
        tick_labels = [qtr.index[i] for i in tick_indices]
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels(tick_labels, rotation=45, fontsize=8)

    fig.suptitle("Default Rate Temporal Trend", fontsize=13)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DEFAULT_TREND_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", DEFAULT_TREND_PNG)


def _write_report(psi_df, years):
    """生成概念漂移评估报告"""
    # 识别高漂移特征
    high_drift = psi_df[psi_df["psi"].apply(lambda x: isinstance(x, (int, float)) and x > PSI_THRESHOLD_HIGH)]
    moderate_drift = psi_df[psi_df["psi"].apply(lambda x: isinstance(x, (int, float)) and PSI_THRESHOLD_MODERATE < x <= PSI_THRESHOLD_HIGH)]

    lines = [
        "# 概念漂移检测报告",
        f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 评估标准",
        f"- PSI < {PSI_THRESHOLD_MODERATE}: 稳定",
        f"- PSI {PSI_THRESHOLD_MODERATE} - {PSI_THRESHOLD_HIGH}: 中度漂移",
        f"- PSI > {PSI_THRESHOLD_HIGH}: 显著漂移（需关注）",
        "",
        f"## 显著漂移特征 (PSI > {PSI_THRESHOLD_HIGH})",
    ]
    if not high_drift.empty:
        for _, row in high_drift.iterrows():
            lines.append(f"- {row['feature']} @ {int(row['year'])}: PSI={row['psi']:.4f}")
    else:
        lines.append("无显著漂移特征。")

    lines.append(f"\n## 中度漂移特征 (PSI {PSI_THRESHOLD_MODERATE} - {PSI_THRESHOLD_HIGH})")
    if not moderate_drift.empty:
        for _, row in moderate_drift.iterrows():
            lines.append(f"- {row['feature']} @ {int(row['year'])}: PSI={row['psi']:.4f}")
    else:
        lines.append("无中度漂移特征。")

    lines.extend([
        "",
        "## 建模建议",
        "1. 对于 PSI > 0.25 的特征，考虑按年份分段建模或在特征中加入年份交互项。",
        "2. 若违约率趋势存在结构性断点（如 2008 金融危机），应评估是否需要剔除或标记该时段。",
    ])

    DRIFT_REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    DRIFT_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved %s", DRIFT_REPORT_MD)


def main():
    run()


if __name__ == "__main__":
    main()
