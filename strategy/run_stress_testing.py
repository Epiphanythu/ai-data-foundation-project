"""strategy/run_stress_testing.py 宏观压力测试（CCAR 风格情景推演）

利用 FRED 宏观数据定义压力情景，推演对贷款组合违约率和利润的影响：
1. 定义三级情景：Baseline / Adverse / Severely Adverse
2. 对每个情景施加宏观冲击（失业率、利率、CPI）
3. 使用已训练模型重预测全量贷款池
4. 输出情景对比表 + 冲击可视化
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_ISSUE_YEAR  # noqa: E402
from constant.model import (  # noqa: E402
    ASSUMED_LGD,
    ASSUMED_INTEREST_MARGIN,
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import (  # noqa: E402
    FIGURES_DIR,
    MODEL_XGB_PATH,
    TABLES_DIR,
)
from common.model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

STRESS_RESULT_CSV = TABLES_DIR / "stress_testing_results.csv"
STRESS_IMPACT_PNG = FIGURES_DIR / "stress_testing_impact.png"
STRESS_WATERFALL_PNG = FIGURES_DIR / "stress_testing_waterfall.png"

# ========================
# 压力情景定义
# ========================
# 冲击以标准差为单位施加在关键宏观特征上
SCENARIOS = {
    "Baseline": {
        "label": "基线情景",
        "description": "当前宏观环境不变",
        "shocks": {},  # 无冲击
    },
    "Adverse": {
        "label": "不利情景",
        "description": "失业率 +1.5σ, 联邦基金利率 +1σ, CPI +1σ",
        "shocks": {
            "unemployment_rate": 1.5,    # 失业率上升 1.5 个标准差
            "fed_funds_rate": 1.0,       # 利率上升 1 个标准差
            "cpi_inflation": 1.0,        # 通胀上升 1 个标准差
        },
    },
    "Severely Adverse": {
        "label": "严重不利情景",
        "description": "失业率 +3σ, 联邦基金利率 +2σ, CPI +2σ",
        "shocks": {
            "unemployment_rate": 3.0,
            "fed_funds_rate": 2.0,
            "cpi_inflation": 2.0,
        },
    },
}

# 冲击可影响的特征（必须同时存在于 CROSS_SOURCE_NUMERIC_FEATURES 和模型中）
SHOCKABLE_FEATURES = ["unemployment_rate", "fed_funds_rate", "cpi_inflation"]


def _load_model():
    """加载训练好的 XGBoost 模型"""
    if not MODEL_XGB_PATH.exists():
        logger.warning("XGBoost model not found at %s, will use LR fallback", MODEL_XGB_PATH)
        from constant.paths import MODEL_LR_PATH
        if MODEL_LR_PATH.exists():
            return joblib.load(MODEL_LR_PATH)
        raise FileNotFoundError(f"No model found. Run modeling/train_baseline_model.py first.")
    return joblib.load(MODEL_XGB_PATH)


def _apply_shocks(df: pd.DataFrame, scenario: dict) -> pd.DataFrame:
    """对 DataFrame 的宏观特征列施加冲击。"""
    df_shocked = df.copy()
    shocks = scenario.get("shocks", {})

    for feat, n_std in shocks.items():
        if feat not in df_shocked.columns:
            logger.warning("Feature %s not found in data, skipping shock", feat)
            continue
        std = df_shocked[feat].std()
        if pd.isna(std) or std == 0:
            continue
        df_shocked[feat] = df_shocked[feat] + n_std * std
        logger.info("  %s: +%.2fσ = +%.4f (μ=%.4f, σ=%.4f)",
                    feat, n_std, n_std * std, df[feat].mean(), std)

    # 重新计算交互特征（受冲击影响）
    if "interact_int_rate_x_fed_funds" in df_shocked.columns and "fed_funds_rate" in df_shocked.columns:
        df_shocked["interact_int_rate_x_fed_funds"] = df_shocked["int_rate"] * df_shocked["fed_funds_rate"]

    if "interact_loan_amnt_x_state_unemp" in df_shocked.columns and "unemployment_rate" in df_shocked.columns:
        df_shocked["interact_loan_amnt_x_state_unemp"] = df_shocked["loan_amnt"] * df_shocked["unemployment_rate"]

    if "interact_fico_x_cpi" in df_shocked.columns and "cpi_inflation" in df_shocked.columns:
        df_shocked["interact_fico_x_cpi"] = df_shocked["fico_avg"] * df_shocked["cpi_inflation"]

    return df_shocked


def _evaluate_portfolio(y_true: pd.Series, y_proba: pd.Series, loan_amounts: pd.Series,
                        threshold: float = 0.5) -> dict:
    """评估贷款组合在特定违约概率下的表现。"""
    y_pred = (y_proba >= threshold).astype(int)
    accepted = y_pred == 0

    n_accepted = accepted.sum()
    n_total = len(y_true)
    if n_accepted == 0:
        return {"pass_rate": 0.0, "bad_rate": 0.0, "expected_loss": 0.0, "profit": 0.0,
                "avg_pd": 0.0, "n_loans": n_total}

    avg_loan = loan_amounts[accepted].mean()
    profit = n_accepted * ASSUMED_INTEREST_MARGIN * avg_loan - y_true[accepted].sum() * ASSUMED_LGD * avg_loan
    expected_loss = y_true[accepted].sum() * ASSUMED_LGD * avg_loan

    return {
        "pass_rate": round(float(n_accepted / n_total), 4),
        "bad_rate": round(float(y_true[accepted].mean()), 4),
        "expected_loss": round(float(expected_loss), 2),
        "profit": round(float(profit), 2),
        "avg_pd": round(float(y_proba.mean()), 4),
        "n_loans": n_total,
    }


def run():
    logger.info("=" * 60)
    logger.info("Macro Stress Testing (CCAR-style)")
    logger.info("=" * 60)

    # 1. 加载数据
    df = build_training_sample(sample_size=80000, enable_macro=True, enable_state=True)
    model = _load_model()

    feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES + CATEGORICAL_FEATURES
                    if c in df.columns]
    X = df[feature_cols]
    y = df[LABEL_COL]
    loan_amnt = df["loan_amnt"] if "loan_amnt" in df.columns else pd.Series(10000, index=df.index)

    # 2. 各情景推演
    results: list[dict] = []

    for scenario_name, scenario_def in SCENARIOS.items():
        logger.info("--- %s: %s ---", scenario_name, scenario_def["description"])
        X_shocked = _apply_shocks(X, scenario_def)

        try:
            y_proba = model.predict_proba(X_shocked)[:, 1]
        except Exception:
            logger.warning("Model predict failed for %s, using baseline", scenario_name)
            y_proba = np.full(len(y), y.mean())

        metrics = _evaluate_portfolio(y, pd.Series(y_proba, index=y.index), loan_amnt)
        metrics["scenario"] = scenario_name
        metrics["label"] = scenario_def["label"]
        metrics["description"] = scenario_def["description"]
        results.append(metrics)

        logger.info("  Pass Rate=%.2f%%, Bad Rate=%.2f%%, Profit=%.0f, Avg PD=%.4f",
                    metrics["pass_rate"] * 100, metrics["bad_rate"] * 100,
                    metrics["profit"], metrics["avg_pd"])

    # 3. 保存结果
    results_df = pd.DataFrame(results)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(STRESS_RESULT_CSV, index=False)
    logger.info("Saved %s", STRESS_RESULT_CSV)

    # 4. 可视化
    _plot_stress_impact(results_df)
    _plot_stress_waterfall(results_df)

    logger.info("Stress testing complete.")


def _plot_stress_impact(results_df: pd.DataFrame):
    """情景冲击对比图"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    metrics = [
        ("bad_rate", "Bad Rate in Approved", "Reds"),
        ("profit", "Portfolio Profit ($)", "Blues"),
        ("avg_pd", "Average Default Probability", "Oranges"),
    ]
    scenario_labels = results_df["label"].tolist()

    for ax, (col, title, _) in zip(axes, metrics):
        values = results_df[col].values
        colors = ["#2ecc71", "#f39c12", "#e74c3c"]
        bars = ax.bar(scenario_labels, values, color=colors[:len(values)], alpha=0.85, edgecolor="white")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.01,
                    f"{val:,.4f}", ha="center", fontsize=9, fontweight="bold")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Macro Stress Testing: Scenario Impact Comparison", fontsize=14, fontweight="bold")
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(STRESS_IMPACT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", STRESS_IMPACT_PNG)


def _plot_stress_waterfall(results_df: pd.DataFrame):
    """利润瀑布图：从 Baseline 到 Severely Adverse"""
    if len(results_df) < 2:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    baseline_profit = results_df["profit"].iloc[0]

    x_labels = ["Baseline"]
    values = [baseline_profit]
    colors = ["steelblue"]

    for i in range(1, len(results_df)):
        delta = results_df["profit"].iloc[i] - baseline_profit
        x_labels.append(f"{results_df['scenario'].iloc[i]}\n(Δ)")
        values.append(delta)
        colors.append("coral")

    # 瀑布图逻辑
    bottoms = [0]
    running = baseline_profit
    for v in values[1:]:
        bottoms.append(running if v < 0 else running)
        running += v

    bars = ax.bar(range(len(x_labels)), values, bottom=bottoms, color=colors, alpha=0.85, edgecolor="white")
    for i, (v, b) in enumerate(zip(values, bottoms)):
        label_y = b + v + max(values) * 0.01 if v >= 0 else b + v - max(abs(v) for v in values) * 0.05
        ax.text(i, label_y, f"${v:,.0f}", ha="center", fontsize=10, fontweight="bold")

    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=9)
    ax.set_ylabel("Profit ($)")
    ax.set_title("Profit Waterfall Under Stress Scenarios")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(STRESS_WATERFALL_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", STRESS_WATERFALL_PNG)


def main():
    run()


if __name__ == "__main__":
    main()
