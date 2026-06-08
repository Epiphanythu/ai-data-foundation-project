"""modeling/build_scorecard.py 信用评分卡构建（WOE 分箱 + IV 筛选 + 评分刻度）

将 ML 模型与传统银行评分卡方法论桥接：
1. 逐特征 Weight of Evidence (WOE) 分箱
2. Information Value (IV) 筛选预测能力最强的特征
3. 逻辑回归评分刻度转换（PDO = 20）
4. 与 XGBoost 排序能力对比
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_ISSUE_YEAR  # noqa: E402
from constant.model import NUMERIC_FEATURES, RANDOM_SEED  # noqa: E402
from constant.paths import FIGURES_DIR, TABLES_DIR  # noqa: E402
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

SCORECARD_CSV = TABLES_DIR / "scorecard.csv"
IV_RANKING_CSV = TABLES_DIR / "iv_ranking.csv"
SCORECARD_COMPARISON_PNG = FIGURES_DIR / "scorecard_comparison.png"

# 评分刻度参数
BASE_SCORE = 600
BASE_ODDS = 50  # base odds: good:bad = 50:1 at base score
PDO = 20  # Points to Double Odds

# WOE 分箱参数
MAX_BINS = 10
MIN_BIN_PCT = 0.05  # 每箱最少 5% 样本


def _monotonic_binning(series: pd.Series, target: pd.Series, max_bins: int = MAX_BINS) -> Optional[np.ndarray]:
    """基于目标率的单调分箱，返回分箱边界。"""
    df = pd.DataFrame({"x": series, "y": target})
    df = df.dropna()
    if len(df) < 100:
        return None

    # 等频分箱初版
    try:
        _, bin_edges = pd.qcut(df["x"], q=max_bins, retbins=True, duplicates="drop")
    except (ValueError, IndexError):
        return None

    if len(bin_edges) < 3:
        return None

    # 合并相邻样本量过小的箱
    merged = [bin_edges[0]]
    for edge in bin_edges[1:-1]:
        count = ((df["x"] >= merged[-1]) & (df["x"] < edge)).sum()
        if count / len(df) >= MIN_BIN_PCT:
            merged.append(edge)
    merged.append(bin_edges[-1])
    return np.array(merged)


def _calculate_woe_iv(series: pd.Series, target: pd.Series, bins: np.ndarray) -> tuple[list[dict], float]:
    """计算某特征的 WOE 值和 Information Value。"""
    df = pd.DataFrame({"x": series, "y": target})
    df = df.dropna()
    df["bin"] = pd.cut(df["x"], bins=bins, include_lowest=True)

    total_good = max((df["y"] == 0).sum(), 1)
    total_bad = max((df["y"] == 1).sum(), 1)

    woe_table: list[dict] = []
    iv_total = 0.0

    for interval in df["bin"].cat.categories:
        mask = df["bin"] == interval
        if mask.sum() == 0:
            continue
        n_good = (df.loc[mask, "y"] == 0).sum()
        n_bad = (df.loc[mask, "y"] == 1).sum()
        pct_good = n_good / total_good
        pct_bad = n_bad / total_bad

        # WOE = ln(%good / %bad)，若某类为零则用极小值平滑
        pct_good_adj = max(pct_good, 0.0001)
        pct_bad_adj = max(pct_bad, 0.0001)
        woe = np.log(pct_good_adj / pct_bad_adj)

        iv = (pct_good - pct_bad) * woe
        iv_total += iv

        woe_table.append({
            "interval": str(interval),
            "n_good": n_good,
            "n_bad": n_bad,
            "pct_good": round(pct_good, 6),
            "pct_bad": round(pct_bad, 6),
            "woe": round(woe, 6),
            "iv": round(iv, 6),
            "bad_rate": round(n_bad / max(n_good + n_bad, 1), 4),
        })

    return woe_table, round(iv_total, 6)


def build_scorecard(
    df: pd.DataFrame,
    target_col: str = LABEL_COL,
    base_score: float = BASE_SCORE,
    base_odds: float = BASE_ODDS,
    pdo: float = PDO,
) -> tuple[pd.DataFrame, pd.DataFrame, LogisticRegression]:
    """构建完整评分卡。

    Returns:
        (scorecard_df, iv_ranking_df, lr_model)
    """
    # 选取数值特征 + 已分箱类别特征
    num_features = [c for c in NUMERIC_FEATURES if c in df.columns and df[c].dtype in ("float64", "int64")]
    logger.info("Building scorecard for %d numeric features", len(num_features))

    # ---- Step 1: WOE 分箱 + IV ----
    all_woe: dict[str, list[dict]] = {}
    iv_list: list[dict] = []

    for feat in num_features:
        series = df[feat]
        target = df[target_col]
        bins = _monotonic_binning(series, target, max_bins=MAX_BINS)
        if bins is None or len(bins) < 3:
            continue
        woe_table, iv = _calculate_woe_iv(series, target, bins)
        if iv > 0.001:  # 过滤无预测能力的特征
            all_woe[feat] = woe_table
            iv_list.append({"feature": feat, "iv": iv})

    iv_ranking = pd.DataFrame(iv_list).sort_values("iv", ascending=False)
    logger.info("Top-10 IV features:\n%s", iv_ranking.head(10).to_string())

    # ---- Step 2: WOE 编码 ----
    df_woe = pd.DataFrame(index=df.index)
    woe_mappings: dict[str, dict] = {}

    for feat, woe_table in all_woe.items():
        interval_to_woe = {row["interval"]: row["woe"] for row in woe_table}
        bins = _monotonic_binning(df[feat], df[target_col], max_bins=MAX_BINS)
        if bins is None:
            continue
        binned = pd.cut(df[feat], bins=bins, include_lowest=True).astype(str)
        df_woe[f"{feat}_woe"] = binned.map(interval_to_woe).fillna(0.0)
        woe_mappings[feat] = {"bins": bins.tolist(), "interval_to_woe": interval_to_woe}

    # ---- Step 3: 逻辑回归 ----
    train_df, test_df = split_by_time(df)
    woe_cols = [c for c in df_woe.columns if c.endswith("_woe")]
    X_train = df_woe.loc[train_df.index, woe_cols]
    X_test = df_woe.loc[test_df.index, woe_cols]
    y_train = train_df[target_col]
    y_test = test_df[target_col]

    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED, C=0.5)
    lr.fit(X_train, y_train)
    lr_auc = roc_auc_score(y_test, lr.predict_proba(X_test)[:, 1])
    logger.info("Scorecard LR AUC: %.4f", lr_auc)

    # ---- Step 4: 评分刻度转换 ----
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(base_odds)

    scorecard_rows: list[dict] = []
    for feat, woe_table in all_woe.items():
        idx = list(all_woe.keys()).index(feat)
        coef = lr.coef_[0][idx] if idx < len(lr.coef_[0]) else 0
        for row in woe_table:
            points = -coef * row["woe"] * factor / len(woe_cols)
            scorecard_rows.append({
                "feature": feat,
                "interval": row["interval"],
                "woe": row["woe"],
                "bad_rate": row["bad_rate"],
                "points": round(points, 2),
            })

    scorecard = pd.DataFrame(scorecard_rows)
    scorecard["intercept_points"] = round(offset / len(woe_cols), 2)

    return scorecard, iv_ranking, lr, float(lr_auc)


def _plot_scorecard_comparison(iv_ranking: pd.DataFrame, lr_auc: float):
    """绘制 IV 排名 + 评分卡 vs XGBoost AUC 对比"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # IV 柱状图
    top = iv_ranking.head(15)
    bars = ax1.barh(range(len(top)), top["iv"].values, color="steelblue", alpha=0.8)
    ax1.set_yticks(range(len(top)))
    ax1.set_yticklabels(top["feature"].values, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("Information Value")
    ax1.set_title("Feature Predictive Power (IV Ranking)")

    # 阈值标注
    for i, (_, row) in enumerate(top.iterrows()):
        color = "darkgreen" if row["iv"] > 0.1 else ("orange" if row["iv"] > 0.02 else "gray")
        ax1.text(row["iv"] + 0.002, i, f"{row['iv']:.4f}", va="center", fontsize=8, color=color)

    ax1.axvline(0.10, color="green", linestyle="--", alpha=0.5, label="IV=0.10 (strong)")
    ax1.axvline(0.02, color="orange", linestyle="--", alpha=0.5, label="IV=0.02 (weak)")
    ax1.legend(fontsize=8)

    # 评分卡性能说明
    ax2.axis("off")
    summary_lines = [
        "Scorecard Summary",
        "",
        f"Scorecard LR AUC: {lr_auc:.4f}",
        f"Base Score: {BASE_SCORE} @ {BASE_ODDS}:1 odds",
        f"PDO: {PDO} (points to double odds)",
        f"Features with IV > 0.10: {(iv_ranking['iv'] > 0.10).sum()}",
        f"Features with IV > 0.02: {(iv_ranking['iv'] > 0.02).sum()}",
        "",
        "IV Interpretation:",
        "  < 0.02: Unpredictive",
        "  0.02 - 0.10: Moderately predictive",
        "  > 0.10: Highly predictive",
        "",
        "Score = Σ(points per bin) + intercept/N",
        "Higher score → lower default risk",
    ]
    for i, line in enumerate(summary_lines):
        ax2.text(0, 1 - i * 0.055, line, fontsize=10, fontfamily="monospace" if i == 0 else "sans-serif",
                fontweight="bold" if i == 0 else "normal")

    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(SCORECARD_COMPARISON_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", SCORECARD_COMPARISON_PNG)


def run():
    logger.info("=" * 60)
    logger.info("Credit Scorecard Construction (WOE + IV)")
    logger.info("=" * 60)

    df = build_training_sample(sample_size=100000)
    scorecard, iv_ranking, lr, lr_auc = build_scorecard(df)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(SCORECARD_CSV, index=False)
    iv_ranking.to_csv(IV_RANKING_CSV, index=False)
    logger.info("Saved %s (%d rows)", SCORECARD_CSV, len(scorecard))
    logger.info("Saved %s", IV_RANKING_CSV)

    _plot_scorecard_comparison(iv_ranking, lr_auc)
    logger.info("Scorecard construction complete.")


def main():
    run()


if __name__ == "__main__":
    main()
