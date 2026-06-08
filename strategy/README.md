# strategy 风控策略模块

`strategy/` 负责把模型预测结果转化为可执行的审批策略，比较固定阈值、动态阈值和状态感知策略的业务收益。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `run_dynamic_risk_strategy.py` | 动态阈值、规则引擎和机器学习混合策略 | `strategy_comparison.csv` |
| `run_risk_strategy_simulation.py` | 阈值扫描下的通过率、坏账率、利润曲线 | `risk_strategy.csv`、`risk_strategy.png` |
| `state_aware_risk/run_state_aware_risk_analysis.py` | 状态感知动态风控分析 | `state_aware_*` 表格和图表 |

## 策略层主线

```text
模型预测概率
  ↓
固定阈值 / 动态阈值 / 分状态阈值
  ↓
通过率、坏账率、召回率、利润
  ↓
可解释的审批策略建议
```
