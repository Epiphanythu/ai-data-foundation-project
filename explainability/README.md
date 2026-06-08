# explainability 解释性模块

`explainability/` 负责解释模型为什么做出某种预测，并将模型输出转化为可审计、可追溯的风险说明。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `run_shap_analysis.py` | 生成 SHAP summary、bar 和 PDP 图 | `outputs/figures/shap_*.png`、`outputs/figures/pdp/` |
| `run_causal_analysis.py` | DID、IV、中介分析和反事实解释 | `causal_*_result.csv`、`counterfactual_*.csv` |
| `run_explainability_enhancement.py` | 决策日志、审计报告、自然语言解释增强 | `decision_logs.json`、`decision_audit_report.md` |

## 模块定位

- 对模型全局行为做解释：SHAP、PDP。
- 对宏观/地区因素做更强解释：DID、IV、中介分析。
- 对单笔贷款做解释：反事实改善路径和决策追溯。
