# state_aware_risk 状态感知风控子模块

该子模块属于 `strategy/`，用于验证宏观状态是否应该影响审批阈值和风控策略。

## 文件说明

| 文件 | 作用 |
|---|---|
| `analysis.py` | 状态识别、状态风险汇总、状态感知模型验证和动态阈值分析 |
| `run_state_aware_risk_analysis.py` | 命令入口，调度完整状态感知风控流程 |

## 输入依赖

| 输入 | 来源 |
|---|---|
| `outputs/tables/lc_default_by_quarter_with_fred_macro.csv` | `analysis/build_quarterly_macro_analysis.py` |
| `outputs/models/test_predictions.csv` | `modeling/train_baseline_model.py` |

## 输出产物

- `outputs/tables/state_aware_risk_summary.csv`
- `outputs/models/state_aware_model_validation_summary.csv`
- `outputs/models/state_aware_dynamic_threshold_strategy.csv`
- `outputs/figures/state_aware_dynamic_threshold_strategy.png`
