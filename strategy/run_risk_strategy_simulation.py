"""strategy/run_risk_strategy_simulation.py 风控策略模拟
基于模型预测概率，扫描不同审批阈值下的：
- 通过率（approve rate）
- 拒绝率（reject rate）
- 实际坏账率（bad rate among approved）
- 召回率（拦截了多少违约）
- 估算利润（按息差与 LGD 假设）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 兼容 macOS 中文字体（缺失则回退英文）
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.model import (  # noqa: E402
    ASSUMED_INTEREST_MARGIN,
    ASSUMED_LGD,
    STRATEGY_THRESHOLDS,
)
from constant.paths import (  # noqa: E402
    MODEL_TEST_PREDICTIONS_CSV,
    MODELS_DIR,
    RISK_STRATEGY_CSV,
    RISK_STRATEGY_PNG,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROBA_COL = "xgb_proba"


def simulate(predictions: pd.DataFrame) -> pd.DataFrame:
    """simulate 在多阈值下计算通过率/坏账率/利润"""
    rows: list[dict] = []
    total = len(predictions)
    total_bad = predictions["y_true"].sum()
    for thr in STRATEGY_THRESHOLDS:
        approved_mask = predictions[PROBA_COL] < thr
        approved = predictions[approved_mask]
        approve_rate = len(approved) / total
        bad_in_approved = approved["y_true"].sum()
        bad_rate = bad_in_approved / max(len(approved), 1)
        # 召回率：被拒绝的违约占全部违约比例
        recall_bad = (total_bad - bad_in_approved) / max(total_bad, 1)
        # 利润估算：好账户带息差，坏账户损失 LGD
        good_count = len(approved) - bad_in_approved
        profit_per_loan = (
            good_count * ASSUMED_INTEREST_MARGIN
            - bad_in_approved * ASSUMED_LGD
        ) / max(total, 1)
        rows.append(
            {
                "threshold": thr,
                "approve_rate": round(approve_rate, 4),
                "bad_rate_in_approved": round(bad_rate, 4),
                "bad_recall": round(recall_bad, 4),
                "profit_per_loan": round(profit_per_loan, 4),
            }
        )
    return pd.DataFrame(rows)


def plot(df: pd.DataFrame, out_path: Path):
    """plot 输出阈值-通过率-坏账率-利润 三轴图"""
    _, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(df["threshold"], df["approve_rate"], "-o", color="#3778b4", label="通过率")
    ax1.plot(df["threshold"], df["bad_rate_in_approved"], "-s", color="#dc6446", label="放贷后坏账率")
    ax1.set_xlabel("审批阈值（违约概率）")
    ax1.set_ylabel("比例")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(df["threshold"], df["profit_per_loan"], "--^", color="#2ca02c", label="单笔利润估算")
    ax2.set_ylabel("利润（相对单位）")
    ax2.legend(loc="upper right")
    plt.title("风控策略模拟：阈值 vs 通过率 / 坏账率 / 利润")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def run():
    """run 风控策略主流程
    1. 加载 test_predictions；
    2. 扫描阈值；
    3. 输出 CSV 与图。
    """
    pred_path = MODEL_TEST_PREDICTIONS_CSV
    if not pred_path.exists():
        raise FileNotFoundError(f"未找到 {pred_path}，请先运行 train_baseline_model.py")
    predictions = pd.read_csv(pred_path)
    df = simulate(predictions)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RISK_STRATEGY_CSV, index=False)
    plot(df, RISK_STRATEGY_PNG)
    logger.info("Saved %s\n%s", RISK_STRATEGY_CSV, df.to_string(index=False))


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    run()


if __name__ == "__main__":
    main()
