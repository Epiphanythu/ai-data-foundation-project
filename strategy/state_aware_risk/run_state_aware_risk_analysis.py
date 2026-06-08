"""run_state_aware_risk_analysis.py 状态感知动态风控分析
命令入口仅负责编排执行顺序，具体计算逻辑集中在 strategy/state_aware_risk/analysis.py。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from constant.paths import (  # noqa: E402
    STATE_AWARE_DYNAMIC_STRATEGY_CSV,
    STATE_AWARE_DYNAMIC_STRATEGY_PNG,
    STATE_AWARE_MACRO_FEATURES_CSV,
    STATE_AWARE_MODEL_VALIDATION_CSV,
    STATE_AWARE_RISK_SUMMARY_CSV,
)
from strategy.state_aware_risk.analysis import (  # noqa: E402
    build_dynamic_threshold_strategy,
    build_macro_state_features,
    build_model_validation_summary,
    build_state_risk_summary,
    plot_dynamic_strategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    """run 执行状态感知动态风控最小闭环"""
    # 1. 构造宏观状态和状态风险汇总
    macro = build_macro_state_features()
    state_summary = build_state_risk_summary(macro)

    # 2. 生成模型验证摘要和动态阈值策略
    validation = build_model_validation_summary()
    strategy = build_dynamic_threshold_strategy(state_summary)
    plot_dynamic_strategy(strategy)

    # 3. 输出关键路径，便于脚本运行后核对
    logger.info("Saved %s", STATE_AWARE_MACRO_FEATURES_CSV)
    logger.info("Saved %s", STATE_AWARE_RISK_SUMMARY_CSV)
    logger.info("Saved %s\n%s", STATE_AWARE_MODEL_VALIDATION_CSV, validation.to_string(index=False))
    logger.info("Saved %s\n%s", STATE_AWARE_DYNAMIC_STRATEGY_CSV, strategy.to_string(index=False))
    logger.info("Saved %s", STATE_AWARE_DYNAMIC_STRATEGY_PNG)


def main() -> None:
    """main 命令行入口"""
    run()


if __name__ == "__main__":
    main()
