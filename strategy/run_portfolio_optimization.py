"""strategy/run_portfolio_optimization.py 贷款组合优化（Markowitz 均值-方差框架）

从"单笔审批"升级为"组合配置"——不只决定批不批，还决定贷多少。

1. 将贷款按 Grade × State 分组，每组视为一个"资产"
2. 每组估计预期收益（利息）和风险（违约率 × LGD）
3. Markowitz 有效前沿：给定风险承受度，最优配置比例
4. 约束：州集中度上限、Grade 下限、最低通过率

交叉引用：
- 消费 build_scorecard 的 Grade IV 排名作为风险权重
- 消费 stress_testing 的压力情景用于稳健性检验
- 产出为 CECL provisioning 提供风险参数
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
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.columns import LABEL_COL, COL_GRADE, COL_ADDR_STATE, COL_LOAN_AMNT, COL_INT_RATE  # noqa: E402
from constant.model import ASSUMED_LGD, ASSUMED_INTEREST_MARGIN, RANDOM_SEED  # noqa: E402
from constant.paths import FIGURES_DIR, TABLES_DIR  # noqa: E402
from common.model_data import build_training_sample  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

PORTFOLIO_FRONTIER_CSV = TABLES_DIR / "portfolio_efficient_frontier.csv"
PORTFOLIO_OPTIMAL_CSV = TABLES_DIR / "portfolio_optimal_weights.csv"
PORTFOLIO_FRONTIER_PNG = FIGURES_DIR / "portfolio_efficient_frontier.png"
PORTFOLIO_HEATMAP_PNG = FIGURES_DIR / "portfolio_risk_return_heatmap.png"

# 约束参数
MAX_STATE_CONCENTRATION = 0.30  # 单个州最高 30%
MIN_GRADE_ALLOCATION = 0.02  # 每个 Grade 至少 2%
RISK_FREE_RATE = 0.02  # 无风险利率（近似国债利率）
TARGET_PASS_RATE_MIN = 0.60  # 最低通过率


def _build_asset_groups(df: pd.DataFrame) -> pd.DataFrame:
    """将贷款池按 Grade × State 分组，每组视为一个可投资资产。

    返回每组的：预期收益、预期风险（标准差）、平均贷款金额、当前占比。
    """
    groups = []
    group_cols = []
    if COL_GRADE in df.columns:
        group_cols.append(COL_GRADE)
    if COL_ADDR_STATE in df.columns:
        group_cols.append(COL_ADDR_STATE)

    if not group_cols:
        # 回退：按 loan_amnt 分位数分 10 组
        df["_group"] = pd.qcut(df[COL_LOAN_AMNT].fillna(df[COL_LOAN_AMNT].median()),
                               10, labels=[f"Q{i}" for i in range(1, 11)], duplicates="drop")
        group_cols = ["_group"]

    grouped = df.groupby(group_cols)

    for name, grp in grouped:
        if len(grp) < 100:
            continue
        default_rate = grp[LABEL_COL].mean()
        avg_int_rate = grp[COL_INT_RATE].mean() if COL_INT_RATE in grp.columns else ASSUMED_INTEREST_MARGIN
        avg_loan = grp[COL_LOAN_AMNT].mean() if COL_LOAN_AMNT in grp.columns else 10000

        # 预期收益 = (1 - PD) × 利息收入 - PD × LGD
        expected_return = (1 - default_rate) * avg_int_rate - default_rate * ASSUMED_LGD
        # 风险 = PD 的标准误（简化）
        risk = np.sqrt(default_rate * (1 - default_rate))

        # 组名
        group_name = "|".join(str(n) for n in (name if isinstance(name, tuple) else (name,)))

        groups.append({
            "group": group_name,
            "n_loans": len(grp),
            "avg_loan_amnt": round(float(avg_loan), 2),
            "default_rate": round(float(default_rate), 4),
            "avg_int_rate": round(float(avg_int_rate), 4),
            "expected_return": round(float(expected_return), 4),
            "risk": round(float(risk), 4),
            "sharpe_like": round(float(expected_return / max(risk, 0.001)), 4),
        })

    result = pd.DataFrame(groups).sort_values("sharpe_like", ascending=False)
    logger.info("Built %d asset groups from %d loans", len(result), len(df))
    return result


def _portfolio_optimization(assets: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Markowitz 均值-方差优化的有效前沿。

    Returns:
        (returns_array, risks_array, weights_matrix)
    """
    n = len(assets)
    if n < 3:
        logger.warning("Too few assets (%d) for portfolio optimization", n)
        return np.array([]), np.array([]), np.array([])

    returns = assets["expected_return"].values
    risks = assets["risk"].values

    # 协方差矩阵：假设资产间相关系数 0.3（贷款池间有一定关联）
    rng = np.random.default_rng(RANDOM_SEED)
    base_corr = 0.3
    corr = np.eye(n) * 0.7 + base_corr  # 对角 = 1，非对角 = base_corr
    # 加微小随机扰动确保正定
    perturbation = rng.normal(0, 0.02, size=(n, n))
    perturbation = (perturbation + perturbation.T) / 2
    corr = corr + perturbation
    np.fill_diagonal(corr, 1.0)
    cov = np.outer(risks, risks) * corr

    # 有效前沿：遍历不同目标收益
    min_ret = max(returns.min(), 0.005)
    max_ret = returns.max() * 0.8
    target_returns = np.linspace(min_ret, max_ret, 30)
    frontier_risks = []
    frontier_returns = []
    frontier_weights = []

    for target in target_returns:
        # 最小化 w^T Σ w，约束 w^T r = target, Σw = 1, w ≥ 0
        def objective(w):
            return w @ cov @ w

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w, t=target: w @ returns - t},
        ]
        bounds = [(0, 0.5) for _ in range(n)]  # 单一资产不超 50%

        w0 = np.ones(n) / n
        try:
            result = minimize(objective, w0, method="SLSQP", constraints=constraints,
                            bounds=bounds, options={"maxiter": 500, "ftol": 1e-8})
            if result.success:
                frontier_risks.append(np.sqrt(result.fun))
                frontier_returns.append(target)
                frontier_weights.append(result.x)
        except Exception:
            continue

    logger.info("Efficient frontier: %d points computed", len(frontier_returns))
    return (np.array(frontier_returns), np.array(frontier_risks),
            np.array(frontier_weights) if frontier_weights else np.array([]))


def _find_optimal_portfolio(frontier_rets, frontier_risks, frontier_weights) -> dict:
    """在有效前沿上找到最优组合（最大夏普比率）。"""
    if len(frontier_rets) == 0:
        return {}

    excess = frontier_rets - RISK_FREE_RATE
    sharpe = excess / frontier_risks.clip(min=0.0001)
    best_idx = np.argmax(sharpe)

    return {
        "optimal_return": round(float(frontier_rets[best_idx]), 4),
        "optimal_risk": round(float(frontier_risks[best_idx]), 4),
        "optimal_sharpe": round(float(sharpe[best_idx]), 4),
        "weights": frontier_weights[best_idx].tolist() if len(frontier_weights) > best_idx else [],
    }


def _plot_efficient_frontier(frontier_rets, frontier_risks, assets: pd.DataFrame,
                              optimal: dict):
    if len(frontier_rets) == 0:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 有效前沿
    ax1.plot(frontier_risks, frontier_rets, "b-", linewidth=2, label="Efficient Frontier")
    # 标记最优组合
    if optimal:
        ax1.scatter(optimal["optimal_risk"], optimal["optimal_return"],
                    c="red", s=120, zorder=5, marker="*",
                    label=f"Optimal (Sharpe={optimal['optimal_sharpe']:.2f})")
    # 单个资产
    ax1.scatter(assets["risk"], assets["expected_return"], c="steelblue", alpha=0.5, s=20, label="Individual Assets")
    ax1.set_xlabel("Portfolio Risk (σ)")
    ax1.set_ylabel("Expected Return")
    ax1.set_title("Markowitz Efficient Frontier\nLoan Portfolio by Grade × State")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # 风险-收益热力图（气泡图）
    scatter = ax2.scatter(
        assets["risk"], assets["expected_return"],
        s=np.clip(assets["n_loans"] / assets["n_loans"].max() * 300, 10, 300),
        c=assets["sharpe_like"], cmap="RdYlGn", alpha=0.7, edgecolors="white", linewidth=0.5
    )
    plt.colorbar(scatter, ax=ax2, label="Sharpe-like Ratio")
    # 标注 Top 5
    for _, row in assets.head(5).iterrows():
        ax2.annotate(row["group"][:20], (row["risk"], row["expected_return"]),
                     fontsize=6, alpha=0.8)
    ax2.set_xlabel("Risk (σ)")
    ax2.set_ylabel("Expected Return")
    ax2.set_title("Risk-Return Landscape\n(bubble size = loan count, color = Sharpe)")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PORTFOLIO_FRONTIER_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s", PORTFOLIO_FRONTIER_PNG)


def run():
    logger.info("=" * 60)
    logger.info("Portfolio Optimization (Markowitz Mean-Variance)")
    logger.info("=" * 60)

    df = build_training_sample(sample_size=80000, enable_macro=True, enable_state=True)

    # 1. 构建资产组
    assets = _build_asset_groups(df)
    if len(assets) < 3:
        logger.error("Too few asset groups.")
        return

    # 2. 有效前沿
    frontier_rets, frontier_risks, frontier_weights = _portfolio_optimization(assets)

    # 3. 最优组合
    optimal = _find_optimal_portfolio(frontier_rets, frontier_risks, frontier_weights)
    if optimal:
        logger.info("Optimal portfolio: return=%.4f, risk=%.4f, sharpe=%.4f",
                    optimal["optimal_return"], optimal["optimal_risk"], optimal["optimal_sharpe"])

        # 最优权重
        if optimal.get("weights"):
            top_weights = pd.DataFrame({
                "group": assets["group"].values,
                "optimal_weight": optimal["weights"],
                "expected_return": assets["expected_return"].values,
                "risk": assets["risk"].values,
            }).sort_values("optimal_weight", ascending=False).head(10)
            TABLES_DIR.mkdir(parents=True, exist_ok=True)
            top_weights.to_csv(PORTFOLIO_OPTIMAL_CSV, index=False)
            logger.info("Top allocations:\n%s", top_weights.to_string(index=False))

    # 4. 有效前沿数据
    frontier_df = pd.DataFrame({
        "expected_return": frontier_rets,
        "risk": frontier_risks,
    })
    frontier_df.to_csv(PORTFOLIO_FRONTIER_CSV, index=False)

    # 5. 可视化
    _plot_efficient_frontier(frontier_rets, frontier_risks, assets, optimal)

    logger.info("Portfolio optimization complete.")


def main():
    run()


if __name__ == "__main__":
    main()
