"""scripts/analyze_data_quality.py 数据质量全景诊断

1. 缺失值模式分析（逐列缺失率 + 缺失共现矩阵）
2. 异常值检测（IQR 方法，逐数值特征）
3. 类别不平衡分析（标签 × 年份 / 等级 / 州 / 目的）
4. 数值特征分布与偏度
5. 多重共线性矩阵
6. 产出：缺失率表、异常值统计、不平衡热力图、相关性矩阵
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
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import (
    COL_ADDR_STATE,
    COL_FICO_AVG,
    COL_GRADE,
    COL_INT_RATE,
    COL_ISSUE_YEAR,
    COL_LOAN_AMNT,
    COL_LOAN_STATUS,
    COL_PURPOSE,
    LABEL_COL,
)
from constant.model import NUMERIC_FEATURES, CATEGORICAL_FEATURES
from constant.paths import FIGURES_DIR, TABLES_DIR
from common.model_data import find_lending_club_csv, USE_COLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

MISSING_RATE_CSV = TABLES_DIR / "data_quality_missing_rate.csv"
OUTLIER_CSV = TABLES_DIR / "data_quality_outliers.csv"
IMBALANCE_HEATMAP_PNG = FIGURES_DIR / "data_quality_imbalance_heatmap.png"
CORRELATION_HEATMAP_PNG = FIGURES_DIR / "data_quality_correlation_heatmap.png"
DISTRIBUTION_PNG = FIGURES_DIR / "data_quality_distributions.png"
QUALITY_REPORT_MD = TABLES_DIR / "data_quality_report.md"

SAMPLE_N = 200000  # 抽样规模以控制内存


def run():
    logger.info("=" * 60)
    logger.info("Data Quality Analysis")
    logger.info("=" * 60)

    csv_path = find_lending_club_csv()
    logger.info("Loading data: %s", csv_path)

    # 读入全量列（不做 usecols 限制）
    df_full = pd.read_csv(csv_path, low_memory=False)
    if len(df_full) > SAMPLE_N:
        df = df_full.sample(n=SAMPLE_N, random_state=42).copy()
        logger.info("Sampled %d rows from %d total", SAMPLE_N, len(df_full))
    else:
        df = df_full.copy()

    # 基础清洗（与 _model_data 一致）
    df[LABEL_COL] = df[COL_LOAN_STATUS].apply(_label_status)
    df = df.dropna(subset=[LABEL_COL])
    df[COL_FICO_AVG] = (pd.to_numeric(df["fico_range_low"], errors="coerce") +
                        pd.to_numeric(df["fico_range_high"], errors="coerce")) / 2
    df[COL_INT_RATE] = _parse_percent(df[COL_INT_RATE])

    # ---- 1. 缺失值分析 ----
    logger.info("--- Missing Value Analysis ---")
    missing_rate = df.isnull().mean().sort_values(ascending=False)
    missing_df = pd.DataFrame({"column": missing_rate.index, "missing_rate": missing_rate.values})
    missing_df.to_csv(MISSING_RATE_CSV, index=False)
    logger.info("Top-10 missing columns:\n%s", missing_df.head(10).to_string())

    # ---- 2. 异常值检测 ----
    logger.info("--- Outlier Detection (IQR) ---")
    outlier_stats: list[dict] = []
    for col in [c for c in df.columns if c in set(USE_COLS) and df[c].dtype in ("float64", "int64")]:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((series < lower) | (series > upper)).sum())
        outlier_stats.append({
            "column": col, "q1": round(q1, 4), "q3": round(q3, 4),
            "iqr": round(iqr, 4), "lower_fence": round(lower, 4),
            "upper_fence": round(upper, 4), "n_outliers": n_out,
            "outlier_pct": round(n_out / len(series) * 100, 2),
        })
    outlier_df = pd.DataFrame(outlier_stats).sort_values("outlier_pct", ascending=False)
    outlier_df.to_csv(OUTLIER_CSV, index=False)
    logger.info("Top-5 outlier columns:\n%s", outlier_df.head(5).to_string())

    # ---- 3. 类别不平衡分析 ----
    logger.info("--- Class Imbalance Analysis ---")
    _plot_imbalance_heatmap(df)
    logger.info("Default rate by year:\n%s", df.groupby(COL_ISSUE_YEAR)[LABEL_COL].agg(["mean", "count"]).to_string())

    # ---- 4. 数值特征分布 ----
    logger.info("--- Numeric Feature Distributions ---")
    _plot_distributions(df)

    # ---- 5. 多重共线性矩阵 ----
    logger.info("--- Multicollinearity Matrix ---")
    _plot_correlation_heatmap(df)

    # ---- 6. 综合报告 ----
    _write_report(df, missing_df, outlier_df)
    logger.info("All outputs written to %s / %s", TABLES_DIR, FIGURES_DIR)


def _label_status(status):
    GOOD = {"Fully Paid"}
    BAD = {"Charged Off", "Default", "Late (31-120 days)",
           "Does not meet the credit policy. Status:Charged Off"}
    if status in GOOD:
        return 0
    if status in BAD:
        return 1
    return None


def _parse_percent(series):
    return series.astype(str).str.replace("%", "", regex=False).str.strip().replace({"": np.nan, "nan": np.nan}).astype(float)


def _plot_imbalance_heatmap(df):
    """违约率热力图：Grade × Year"""
    pivot = df.pivot_table(
        values=LABEL_COL, index=COL_GRADE, columns=COL_ISSUE_YEAR, aggfunc="mean"
    ).fillna(0)
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(pivot, annot=True, fmt=".2%", cmap="YlOrRd", ax=ax,
                cbar_kws={"label": "Default Rate"}, linewidths=0.5)
    ax.set_title("Default Rate by Grade × Year")
    ax.set_ylabel("Grade")
    ax.set_xlabel("Year")
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMBALANCE_HEATMAP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", IMBALANCE_HEATMAP_PNG)


def _plot_distributions(df):
    """选 6 个关键数值特征画分布直方图"""
    key_cols = [COL_LOAN_AMNT, COL_INT_RATE, COL_FICO_AVG,
                "annual_inc", "dti", "revol_util"]
    key_cols = [c for c in key_cols if c in df.columns]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for idx, col in enumerate(key_cols):
        ax = axes[idx // 3][idx % 3]
        series = df[col].dropna()
        # 截断极端值
        q_low, q_high = series.quantile(0.01), series.quantile(0.99)
        clipped = series.clip(q_low, q_high)
        ax.hist(clipped, bins=60, color="steelblue", edgecolor="white", alpha=0.8)
        ax.axvline(clipped.mean(), color="red", linestyle="--", linewidth=1.5, label=f"μ={clipped.mean():.1f}")
        ax.axvline(clipped.median(), color="green", linestyle="--", linewidth=1.5, label=f"med={clipped.median():.1f}")
        ax.set_title(col, fontsize=10)
        ax.legend(fontsize=7)
    fig.suptitle("Key Numeric Feature Distributions (1st-99th percentile)", fontsize=13)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DISTRIBUTION_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", DISTRIBUTION_PNG)


def _plot_correlation_heatmap(df):
    """数值特征相关性矩阵（取关键列）"""
    cols = [c for c in NUMERIC_FEATURES if c in df.columns][:20]
    if len(cols) < 5:
        return
    corr = df[cols].corr()
    fig, ax = plt.subplots(figsize=(14, 11))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, ax=ax,
                square=True, linewidths=0.3, annot_kws={"fontsize": 6},
                cbar_kws={"shrink": 0.7})
    ax.set_title("Feature Correlation Matrix (Numeric)", fontsize=13)
    ax.tick_params(axis="both", labelsize=7)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CORRELATION_HEATMAP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", CORRELATION_HEATMAP_PNG)


def _write_report(df, missing_df, outlier_df):
    lines = [
        "# 数据质量全景诊断报告",
        f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 样本概况",
        f"- 抽样规模: {len(df):,} 条",
        f"- 违约率: {df[LABEL_COL].mean():.2%}",
        f"- 年份跨度: {int(df[COL_ISSUE_YEAR].min())} - {int(df[COL_ISSUE_YEAR].max())}",
        f"- 州数: {df[COL_ADDR_STATE].nunique()}",
        "",
        "## 缺失率 Top-5",
        "",
        "| 列名 | 缺失率 |",
        "|---|---|",
    ]
    for _, row in missing_df.head(5).iterrows():
        lines.append(f"| {row['column']} | {row['missing_rate']:.2%} |")

    lines.extend([
        "",
        "## 异常值 Top-5 (IQR 方法)",
        "",
        "| 列名 | 下限 | 上限 | 异常数 | 异常比例 |",
        "|---|---|---|---|---|",
    ])
    for _, row in outlier_df.head(5).iterrows():
        lines.append(f"| {row['column']} | {row['lower_fence']:.2f} | {row['upper_fence']:.2f} | {row['n_outliers']} | {row['outlier_pct']:.1f}% |")

    QUALITY_REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved %s", QUALITY_REPORT_MD)


def main():
    run()


if __name__ == "__main__":
    main()
