"""scripts/run_feature_ablation.py 特征增量消融实验

逐组叠加特征，量化每组对 AUC / KS 的边际贡献。
揭示"每多一组数据源，预测能力提升多少"——体现数据融合的价值链。
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
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_ISSUE_YEAR  # noqa: E402
from constant.model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import FIGURES_DIR, TABLES_DIR  # noqa: E402
from common.model_data import build_training_sample, split_by_time  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ABLATION_CSV = TABLES_DIR / "feature_ablation.csv"
ABLATION_BAR_PNG = FIGURES_DIR / "feature_ablation_bar.png"
ABLATION_WATERFALL_PNG = FIGURES_DIR / "feature_ablation_waterfall.png"

# 特征分组定义
FEATURE_GROUPS = [
    ("G1: Raw Lending Club", [
        "loan_amnt", "int_rate", "annual_inc", "dti", "fico_avg",
        "term_months", "installment", "revol_util", "open_acc", "delinq_2yrs",
    ], "基础借贷特征"),
    ("G2: + Categorical", [
        "grade", "purpose", "home_ownership", "verification_status", "emp_length",
    ], "类别特征"),
    ("G3: + Rolling Window", [
        "rolling_mean_30d", "rolling_mean_60d", "rolling_mean_90d",
        "rolling_std_30d", "rolling_std_60d", "rolling_std_90d",
        "rolling_trend_30d", "rolling_trend_60d", "rolling_trend_90d",
    ], "时序滚动窗口"),
    ("G4: + Time Decay", [
        "decayed_loan_amnt", "decayed_int_rate", "decayed_fico",
    ], "时间衰减特征"),
    ("G5: + Seasonal/Holiday", [
        "is_holiday", "is_weekend", "is_quarter_end", "is_month_end",
        "season", "month_of_year", "day_of_week",
    ], "季节/节假日因子"),
    ("G6: + FRED Macro", [
        "fed_funds_rate", "unemployment_rate", "cpi_inflation",
    ], "宏观经济指标"),
    ("G7: + ERS State", [
        "state_poverty_pct", "state_unemployment_rate", "state_median_income",
    ], "州级经济数据"),
    ("G8: + Cross Interactions", [
        "interact_int_rate_x_fed_funds", "interact_loan_amnt_x_state_unemp", "interact_fico_x_cpi",
    ], "跨源交互特征"),
]


def _train_and_eval(X_train, X_test, y_train, y_test):
    """用 XGBoost 训练并返回 AUC / KS"""
    num_cols = [c for c in X_train.columns if c not in CATEGORICAL_FEATURES]
    cat_cols = [c for c in X_train.columns if c in CATEGORICAL_FEATURES]

    pre = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), num_cols),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
                         ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False))]), cat_cols),
    ])

    X_train_t = pre.fit_transform(X_train)
    X_test_t = pre.transform(X_test)

    model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                          random_state=RANDOM_SEED, tree_method="hist", n_jobs=4, eval_metric="auc")
    model.fit(X_train_t, y_train)

    y_proba = model.predict_proba(X_test_t)[:, 1]
    auc = roc_auc_score(y_test, y_proba)

    order = np.argsort(-y_proba)
    cum_pos = np.cumsum(y_test[order]) / max(y_test.sum(), 1)
    cum_neg = np.cumsum(1 - y_test[order]) / max((1 - y_test).sum(), 1)
    ks = float(np.max(cum_pos - cum_neg))

    return auc, ks


def run():
    logger.info("=" * 60)
    logger.info("Feature Ablation Study")
    logger.info("=" * 60)

    # 加载数据（启用跨源特征）
    df = build_training_sample(sample_size=None, enable_macro=True, enable_state=True)
    all_feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES + CATEGORICAL_FEATURES if c in df.columns]
    train_df, test_df = split_by_time(df)

    y_train = train_df[LABEL_COL].values
    y_test = test_df[LABEL_COL].values

    results: list[dict] = []
    cumulative_features: list[str] = []
    prev_auc = 0

    for group_name, group_features, description in FEATURE_GROUPS:
        # 只保留实际存在的列
        available = [f for f in group_features if f in all_feature_cols]
        if not available:
            logger.info("  %s: 0 features available, skip", group_name)
            continue

        cumulative_features.extend(available)
        cumulative_features = list(dict.fromkeys(cumulative_features))  # 去重保序

        X_train = train_df[[c for c in cumulative_features if c in train_df.columns]]
        X_test = test_df[[c for c in cumulative_features if c in test_df.columns]]

        auc, ks = _train_and_eval(X_train, X_test, y_train, y_test)
        delta_auc = auc - prev_auc
        results.append({
            "group": group_name, "description": description,
            "n_features": len(cumulative_features), "auc": round(auc, 4),
            "ks": round(ks, 4), "delta_auc": round(delta_auc, 4),
        })
        logger.info("  %s: AUC=%.4f (Δ=%.4f), KS=%.4f, n_features=%d",
                     group_name, auc, delta_auc, ks, len(cumulative_features))
        prev_auc = auc

    # 保存结果
    results_df = pd.DataFrame(results)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(ABLATION_CSV, index=False)

    # 绘图：堆叠 AUC 柱状图
    _plot_ablation_bars(results_df)
    _plot_waterfall(results_df)

    logger.info("Ablation CSV: %s", ABLATION_CSV)
    logger.info("Full results:\n%s", results_df.to_string(index=False))


def _plot_ablation_bars(results_df):
    """绘制增量 AUC 柱状图"""
    fig, ax = plt.subplots(figsize=(12, 5))
    names = [r["group"].split(": ")[1] for r in results_df.to_dict("records")]
    aucs = results_df["auc"].values
    deltas = results_df["delta_auc"].values

    x = range(len(names))
    bars = ax.bar(x, aucs, color="steelblue", alpha=0.6, label="Cumulative AUC")
    # 在柱子上方标注 AUC 值
    for i, (auc, delta) in enumerate(zip(aucs, deltas)):
        ax.text(i, auc + 0.002, f"{auc:.4f}", ha="center", fontsize=8)
        if delta > 0:
            ax.text(i, auc - delta / 2 if i > 0 else auc * 0.5,
                    f"+{delta:.4f}", ha="center", fontsize=7, color="darkgreen", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("AUC")
    ax.set_title("Feature Ablation: Incremental AUC by Feature Group")
    ax.legend(loc="lower right")
    ax.set_ylim(bottom=max(0.55, aucs.min() - 0.02))
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ABLATION_BAR_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", ABLATION_BAR_PNG)


def _plot_waterfall(results_df):
    """绘制边际贡献瀑布图"""
    rows = results_df.to_dict("records")
    fig, ax = plt.subplots(figsize=(12, 5))

    cumsum = rows[0]["auc"]
    x_labels = ["Base"]
    values = [cumsum]
    colors = ["steelblue"]

    for i in range(1, len(rows)):
        delta = rows[i]["delta_auc"]
        x_labels.append(rows[i]["group"].split(": ")[1])
        values.append(delta)
        colors.append("darkgreen" if delta > 0 else "coral")

    x_labels.append("Total")
    values.append(rows[-1]["auc"])
    colors.append("navy")

    # 瀑布图
    bottoms = [0]
    running = rows[0]["auc"]
    for v in values[1:-1]:
        bottoms.append(running if v > 0 else running + v)
        running += v
    bottoms.append(0)

    bars = ax.bar(range(len(x_labels)), values, bottom=bottoms, color=colors, alpha=0.85, edgecolor="white")
    for i, (v, b) in enumerate(zip(values, bottoms)):
        label_y = b + v + 0.001 if v >= 0 else b + 0.001
        ax.text(i, label_y, f"{v:.4f}", ha="center", fontsize=8)

    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("AUC")
    ax.set_title("Feature Ablation Waterfall: Marginal AUC Contribution of Each Feature Group")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ABLATION_WATERFALL_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", ABLATION_WATERFALL_PNG)


def main():
    run()


if __name__ == "__main__":
    main()
