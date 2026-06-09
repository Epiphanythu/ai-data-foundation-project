"""strategy/run_loan_provisioning.py 贷款损失准备金（CECL / IFRS 9 框架）

会计要求：银行必须在贷款发放时就估算全生命周期预期信用损失，而非等到违约后才确认。

三阶段减值模型：
- Stage 1: 正常贷款 — 计提 12 个月预期损失
- Stage 2: 信用恶化 — 计提全生命周期预期损失（PD 显著上升但未违约）
- Stage 3: 已减值 — 单独评估损失

跨模块引用：
- 消费 survival_analysis 的生存曲线 → 估算 lifetime PD
- 消费 train_baseline_model 的校准后概率 → 估计 12-month PD
- 为 portfolio_optimization 提供风险成本参数
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

from constant.columns import LABEL_COL, COL_GRADE, COL_ISSUE_YEAR, COL_LOAN_AMNT  # noqa: E402
from constant.model import (  # noqa: E402
    ASSUMED_LGD,
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
)
from constant.paths import FIGURES_DIR, TABLES_DIR, MODEL_XGB_PATH  # noqa: E402
from common.model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CECL_RESULT_CSV = TABLES_DIR / "cecl_provisioning.csv"
CECL_STAGE_PNG = FIGURES_DIR / "cecl_stage_distribution.png"
CECL_WATERFALL_PNG = FIGURES_DIR / "cecl_provision_waterfall.png"

# Stage 划分阈值
SIGNIFICANT_PD_INCREASE = 2.0  # 当前 PD / 初始 PD > 2 → Stage 2
DEFAULT_THRESHOLD = 0.5


def _load_model():
    if MODEL_XGB_PATH.exists():
        return joblib.load(MODEL_XGB_PATH)
    from constant.paths import MODEL_LR_PATH
    if MODEL_LR_PATH.exists():
        return joblib.load(MODEL_LR_PATH)
    raise FileNotFoundError("No trained model found.")


def _stage_assignment(initial_pd: pd.Series, current_pd: pd.Series, is_default: pd.Series) -> pd.Series:
    """三阶段减值分类。

    Stage 1: 正常 — 当前 PD 未显著上升
    Stage 2: 信用恶化 — 当前 PD / 初始 PD > 阈值，但尚未违约
    Stage 3: 已减值 — 已违约
    """
    stage = pd.Series(1, index=initial_pd.index, dtype=int)  # default Stage 1
    stage[is_default == 1] = 3
    pd_increase = (current_pd / initial_pd.clip(lower=0.001))
    stage[(pd_increase > SIGNIFICANT_PD_INCREASE) & (is_default == 0)] = 2
    return stage


def _estimate_lifetime_pd(survival_df: pd.DataFrame | None) -> dict:
    """从生存分析结果估算各 Grade 的 lifetime PD。

    若 survival_cox_summary.csv 存在则读取；否则用 term 近似。
    """
    cox_path = TABLES_DIR / "survival_cox_summary.csv"
    if cox_path.exists():
        cox = pd.read_csv(cox_path, index_col=0)
        return {"source": "survival_cox_summary.csv", "available": True}

    # 回退：各 Grade 简单平均 PD
    return {"source": "grade_average", "available": False}


def run():
    logger.info("=" * 60)
    logger.info("Loan Loss Provisioning (CECL / IFRS 9 Framework)")
    logger.info("=" * 60)

    df = build_training_sample(sample_size=50000, enable_macro=True, enable_state=True)
    model = _load_model()

    feature_cols = [c for c in NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES + CATEGORICAL_FEATURES
                    if c in df.columns]
    X = df[feature_cols]
    y = df[LABEL_COL]

    # 1. 当前 PD（从模型概率获得）
    current_pd = pd.Series(model.predict_proba(X)[:, 1], index=df.index)

    # 2. 初始 PD（模拟：用保守估计，或按 Grade 分组取平均 PD）
    if COL_GRADE in df.columns:
        grade_avg_pd = df.groupby(COL_GRADE)[LABEL_COL].transform("mean")
        # 初始 PD = Grade 平均 PD（保守估计），加噪声模拟差异
        rng = np.random.default_rng(RANDOM_SEED)
        noise = rng.normal(0, 0.01, size=len(df))
        initial_pd = (grade_avg_pd + noise).clip(0.001, 0.99)
    else:
        initial_pd = current_pd * 0.8  # 粗略近似：当前 PD 的 80%

    # 3. Stage 分配
    is_default = (y == 1).astype(int)
    stage = _stage_assignment(initial_pd, current_pd, is_default)

    # 4. 计算准备金
    # Stage 1: 12-month ECL = 12-month PD × LGD × EAD
    # Stage 2: Lifetime ECL = lifetime PD × LGD × EAD（lifetime PD ≈ term × annualized PD）
    # Stage 3: ECL = LGD × EAD（已违约，全额计提）

    loan_amnt = df[COL_LOAN_AMNT] if COL_LOAN_AMNT in df.columns else pd.Series(10000, index=df.index)
    twelve_month_pd = current_pd / 3  # 简化：年化 PD ≈ 模型 PD / 3（36月贷款）
    lifetime_pd = current_pd  # 简化近似

    provision = pd.Series(0.0, index=df.index)
    provision[stage == 1] = twelve_month_pd[stage == 1] * ASSUMED_LGD * loan_amnt[stage == 1]
    provision[stage == 2] = lifetime_pd[stage == 2] * ASSUMED_LGD * loan_amnt[stage == 2]
    provision[stage == 3] = ASSUMED_LGD * loan_amnt[stage == 3]  # 违约贷款全额计提

    # 5. 汇总
    stage_summary = []
    for s in [1, 2, 3]:
        mask = stage == s
        stage_summary.append({
            "stage": f"Stage {s}",
            "description": {1: "正常 (12-month ECL)", 2: "信用恶化 (Lifetime ECL)", 3: "已减值 (全额计提)"}[s],
            "n_loans": int(mask.sum()),
            "pct_loans": round(float(mask.sum() / len(df)) * 100, 2),
            "avg_pd": round(float(current_pd[mask].mean()), 4),
            "total_provision": round(float(provision[mask].sum()), 2),
            "avg_provision_per_loan": round(float(provision[mask].mean()), 2),
            "total_exposure": round(float(loan_amnt[mask].sum()), 2),
        })

    summary = pd.DataFrame(stage_summary)
    total_provision = summary["total_provision"].sum()
    total_exposure = summary["total_exposure"].sum()
    coverage_ratio = total_provision / total_exposure * 100 if total_exposure > 0 else 0

    logger.info("Total provision: $%.0f (coverage ratio: %.2f%%)", total_provision, coverage_ratio)
    logger.info("Stage distribution:\n%s", summary.to_string(index=False))

    # 保存
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(CECL_RESULT_CSV, index=False)

    # 6. 可视化
    _plot_stage_distribution(summary, total_provision, coverage_ratio)

    logger.info("CECL provisioning complete.")


def _plot_stage_distribution(summary: pd.DataFrame, total_provision: float, coverage_ratio: float):
    """三阶段准备金分布图"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 饼图：贷款数量分布
    colors = ["#2ecc71", "#f39c12", "#e74c3c"]
    labels = summary["stage"].tolist()
    sizes = summary["n_loans"].tolist()
    ax1.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90)
    ax1.set_title("Loan Distribution by CECL Stage")

    # 柱状图：各阶段准备金
    bars = ax2.bar(labels, summary["total_provision"].values / 1e6, color=colors, alpha=0.85, edgecolor="white")
    for bar, val in zip(bars, summary["total_provision"].values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                 f"${val:,.0f}", ha="center", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Provision ($M)")
    ax2.set_title("Provision by Stage")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(f"CECL Loan Loss Provisioning\nTotal: ${total_provision:,.0f} | Coverage: {coverage_ratio:.2f}%",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(CECL_STAGE_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", CECL_STAGE_PNG)


def main():
    run()


if __name__ == "__main__":
    main()
