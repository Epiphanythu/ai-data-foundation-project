"""analysis.py 状态感知风控分层分析能力
1. 数据层：读取季度宏观融合表和模型测试预测；
2. 特征层：构造宏观压力分数和宏观状态；
3. 验证层：生成模型验证摘要与动态阈值策略；
4. 展示层：输出策略对比图。
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from constant.model import (
    ASSUMED_INTEREST_MARGIN,
    ASSUMED_LGD,
    FIXED_BEST_STRATEGY_TYPE,
    MACRO_STATE_GLOBAL,
    MACRO_STATE_HIGH,
    MACRO_STATE_LABELS,
    MACRO_STATE_LOW,
    MACRO_STATE_MID,
    MACRO_STATE_QUANTILES,
    MODEL_VALIDATION_TOP_DECILE_RATE,
    STATE_AWARE_MODEL_FEATURE_GROUP,
    STATE_AWARE_PROBA_COL,
    STATE_AWARE_PROBA_COLUMNS,
    STATE_AWARE_STRATEGY_TYPE,
    STATE_THRESHOLD_SHIFT,
    STRATEGY_THRESHOLDS,
)
from constant.paths import (
    FIGURES_DIR,
    STATE_AWARE_DYNAMIC_STRATEGY_CSV,
    STATE_AWARE_DYNAMIC_STRATEGY_PNG,
    STATE_AWARE_MACRO_FEATURES_CSV,
    STATE_AWARE_MODEL_VALIDATION_CSV,
    STATE_AWARE_RISK_SUMMARY_CSV,
    MODEL_TEST_PREDICTIONS_CSV,
    MODELS_DIR,
    TABLES_DIR,
)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

QUARTERLY_MACRO_CSV = TABLES_DIR / "lc_default_by_quarter_with_fred_macro.csv"
REQUIRED_MACRO_COLS = [
    "issue_quarter",
    "loan_count",
    "default_count",
    "default_rate",
    "avg_fed_funds_rate",
    "avg_unemployment_rate",
    "quarterly_cpi_inflation_rate",
]


def _zscore(series: pd.Series) -> pd.Series:
    """_zscore 计算稳健标准分，标准差为 0 时返回 0"""
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.mean()) / std


def _assign_macro_state(score: pd.Series) -> pd.Series:
    """_assign_macro_state 基于压力分数分位点分配宏观状态"""
    # 1. 固定分位点保证正常期、观察期、压力期的口径稳定
    low_q, high_q = score.quantile(MACRO_STATE_QUANTILES).tolist()
    conditions = [score <= low_q, score >= high_q]
    choices = [MACRO_STATE_LOW, MACRO_STATE_HIGH]
    state = np.select(conditions, choices, default=MACRO_STATE_MID)
    return pd.Series(state, index=score.index)


def load_quarterly_macro() -> pd.DataFrame:
    """load_quarterly_macro 读取季度宏观融合结果并校验字段"""
    # 1. 读取输入表
    if not QUARTERLY_MACRO_CSV.exists():
        raise FileNotFoundError(f"缺失 {QUARTERLY_MACRO_CSV}，请先运行季度 FRED 融合脚本")
    df = pd.read_csv(QUARTERLY_MACRO_CSV)

    # 2. 校验状态构造所需字段
    missing = [col for col in REQUIRED_MACRO_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"{QUARTERLY_MACRO_CSV.name} 缺少字段：{missing}")
    return df[REQUIRED_MACRO_COLS].copy()


def build_macro_state_features() -> pd.DataFrame:
    """build_macro_state_features 生成季度宏观状态特征表"""
    # 1. 使用宏观变量构造压力分数，方向按本样本相关性校准
    macro = load_quarterly_macro()
    macro["macro_pressure_score"] = (
        _zscore(macro["avg_fed_funds_rate"].astype(float))
        - _zscore(macro["avg_unemployment_rate"].astype(float))
        + _zscore(macro["quarterly_cpi_inflation_rate"].astype(float).abs())
    )
    macro["macro_state"] = _assign_macro_state(macro["macro_pressure_score"])

    # 2. 落盘供 Dashboard / LLM 查询
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    macro.to_csv(STATE_AWARE_MACRO_FEATURES_CSV, index=False)
    return macro


def build_state_risk_summary(macro: pd.DataFrame) -> pd.DataFrame:
    """build_state_risk_summary 汇总不同宏观状态下的风险差异"""
    # 1. 按状态聚合贷款量、违约数与宏观均值
    summary = (
        macro.groupby("macro_state", as_index=False)
        .agg(
            quarter_count=("issue_quarter", "count"),
            loan_count=("loan_count", "sum"),
            default_count=("default_count", "sum"),
            avg_macro_pressure=("macro_pressure_score", "mean"),
            avg_unemployment_rate=("avg_unemployment_rate", "mean"),
            avg_fed_funds_rate=("avg_fed_funds_rate", "mean"),
            avg_cpi_inflation_abs=("quarterly_cpi_inflation_rate", lambda x: x.abs().mean()),
        )
    )
    summary["weighted_default_rate"] = summary["default_count"] / summary["loan_count"].clip(lower=1)

    # 2. 固定状态顺序，便于图表和口径稳定
    order = {label: idx for idx, label in enumerate(MACRO_STATE_LABELS)}
    summary["state_order"] = summary["macro_state"].map(order)
    summary = summary.sort_values("state_order").drop(columns=["state_order"])
    summary = summary.round(
        {
            "weighted_default_rate": 4,
            "avg_macro_pressure": 4,
            "avg_unemployment_rate": 4,
            "avg_fed_funds_rate": 4,
            "avg_cpi_inflation_abs": 4,
        }
    )
    summary.to_csv(STATE_AWARE_RISK_SUMMARY_CSV, index=False)
    return summary


def _ks_stat(y_true: pd.Series, y_proba: pd.Series) -> float:
    """_ks_stat 计算 KS 统计量"""
    order = np.argsort(-y_proba.to_numpy())
    y_sorted = y_true.to_numpy()[order]
    cum_pos = np.cumsum(y_sorted) / max(y_sorted.sum(), 1)
    cum_neg = np.cumsum(1 - y_sorted) / max((1 - y_sorted).sum(), 1)
    return float(np.max(cum_pos - cum_neg))


def load_model_predictions() -> pd.DataFrame:
    """load_model_predictions 读取模型测试集预测结果"""
    if not MODEL_TEST_PREDICTIONS_CSV.exists():
        raise FileNotFoundError(f"缺失 {MODEL_TEST_PREDICTIONS_CSV}，请先运行模型训练脚本")
    return pd.read_csv(MODEL_TEST_PREDICTIONS_CSV)


def build_model_validation_summary() -> pd.DataFrame:
    """build_model_validation_summary 生成模型验证摘要表"""
    # 1. 基于测试集预测补充业务型验证指标
    pred = load_model_predictions()
    rows: list[dict] = []
    y_true = pred["y_true"]
    for model_name, proba_col in STATE_AWARE_PROBA_COLUMNS.items():
        y_proba = pred[proba_col]
        top_n = max(1, int(len(pred) * MODEL_VALIDATION_TOP_DECILE_RATE))
        top_bad = pred.nlargest(top_n, proba_col)["y_true"].sum()
        rows.append(
            {
                "model": model_name,
                "feature_group": STATE_AWARE_MODEL_FEATURE_GROUP,
                "auc": round(roc_auc_score(y_true, y_proba), 4),
                "ks": round(_ks_stat(y_true, y_proba), 4),
                "brier_score": round(brier_score_loss(y_true, y_proba), 4),
                "top_decile_bad_rate": round(top_bad / top_n, 4),
                "top_decile_bad_capture": round(top_bad / max(y_true.sum(), 1), 4),
                "default_rate_test": round(float(y_true.mean()), 4),
            }
        )

    # 2. 输出给 Dashboard / LLM 作为 M1 建模验证入口
    summary = pd.DataFrame(rows)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(STATE_AWARE_MODEL_VALIDATION_CSV, index=False)
    return summary


def _simulate_threshold(predictions: pd.DataFrame, threshold: float) -> dict:
    """_simulate_threshold 计算单个阈值下的策略指标"""
    approved = predictions[predictions[STATE_AWARE_PROBA_COL] < threshold]
    total = len(predictions)
    total_bad = predictions["y_true"].sum()
    bad_in_approved = approved["y_true"].sum()
    good_count = len(approved) - bad_in_approved
    return {
        "threshold": round(threshold, 2),
        "approve_rate": round(len(approved) / max(total, 1), 4),
        "bad_rate_in_approved": round(bad_in_approved / max(len(approved), 1), 4),
        "bad_recall": round((total_bad - bad_in_approved) / max(total_bad, 1), 4),
        "profit_per_loan": round(
            (good_count * ASSUMED_INTEREST_MARGIN - bad_in_approved * ASSUMED_LGD)
            / max(total, 1),
            4,
        ),
    }


def build_dynamic_threshold_strategy(state_summary: pd.DataFrame) -> pd.DataFrame:
    """build_dynamic_threshold_strategy 对比固定阈值与状态感知阈值"""
    # 1. 找到固定阈值下的利润最优点
    predictions = load_model_predictions()
    fixed_rows = [_simulate_threshold(predictions, threshold) for threshold in STRATEGY_THRESHOLDS]
    fixed_df = pd.DataFrame(fixed_rows)
    best_fixed = fixed_df.sort_values("profit_per_loan", ascending=False).iloc[0].to_dict()
    best_threshold = float(best_fixed["threshold"])

    # 2. 基于宏观状态调整阈值，形成情景化审批策略
    rows: list[dict] = []
    for _, state_row in state_summary.iterrows():
        macro_state = state_row["macro_state"]
        threshold = np.clip(best_threshold + STATE_THRESHOLD_SHIFT[macro_state], 0.05, 0.95)
        metrics = _simulate_threshold(predictions, float(threshold))
        rows.append(
            {
                "strategy_type": STATE_AWARE_STRATEGY_TYPE,
                "macro_state": macro_state,
                "state_weighted_default_rate": state_row["weighted_default_rate"],
                "fixed_best_threshold": best_threshold,
                **metrics,
                "profit_lift_vs_fixed": round(metrics["profit_per_loan"] - best_fixed["profit_per_loan"], 4),
                "bad_rate_change_vs_fixed": round(
                    metrics["bad_rate_in_approved"] - best_fixed["bad_rate_in_approved"], 4
                ),
            }
        )

    # 3. 增加固定最优阈值基准行，便于 LLM 直接比较
    rows.append(
        {
            "strategy_type": FIXED_BEST_STRATEGY_TYPE,
            "macro_state": MACRO_STATE_GLOBAL,
            "state_weighted_default_rate": round(float(state_summary["weighted_default_rate"].mean()), 4),
            "fixed_best_threshold": best_threshold,
            **best_fixed,
            "profit_lift_vs_fixed": 0.0,
            "bad_rate_change_vs_fixed": 0.0,
        }
    )
    strategy = pd.DataFrame(rows)
    strategy.to_csv(STATE_AWARE_DYNAMIC_STRATEGY_CSV, index=False)
    return strategy


def plot_dynamic_strategy(strategy: pd.DataFrame) -> None:
    """plot_dynamic_strategy 输出状态感知阈值策略图"""
    # 1. 仅绘制分状态策略，固定基准用横线表达
    view = strategy[strategy["strategy_type"] == STATE_AWARE_STRATEGY_TYPE].copy()
    fixed = strategy[strategy["strategy_type"] == FIXED_BEST_STRATEGY_TYPE].iloc[0]
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    _, ax1 = plt.subplots(figsize=(8, 4.8))
    ax1.bar(view["macro_state"], view["profit_per_loan"], color="#3778b4", alpha=0.85, label="状态阈值利润")
    ax1.axhline(fixed["profit_per_loan"], color="#2ca02c", linestyle="--", label="固定最优阈值利润")
    ax1.set_xlabel("宏观状态")
    ax1.set_ylabel("单笔利润估算")
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(view["macro_state"], view["bad_rate_in_approved"], color="#dc6446", marker="o", label="放贷后坏账率")
    ax2.set_ylabel("放贷后坏账率")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.title("状态感知动态阈值策略：利润与坏账率对比")
    plt.tight_layout()
    plt.savefig(STATE_AWARE_DYNAMIC_STRATEGY_PNG, dpi=140)
    plt.close()
