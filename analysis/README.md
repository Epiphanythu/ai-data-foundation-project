# analysis 数据分析模块

`analysis/` 是独立的数据分析层，负责从贷款数据和融合特征中提取可解释的统计结论。

## 职责边界

- 负责：EDA、标签分布、单变量违约率、组合风险分层、州级控制变量、季度宏观相关分析。
- 不负责：原始数据存放和基础特征下载，这些放在 `data/`。
- 不负责：模型训练，这些放在 `modeling/`。
- 不负责：图表统一美化，这些放在 `visualization/`。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `analyze_lending_club.py` | Lending Club 基础 EDA、标签过滤、单变量违约率 | `lc_overview.csv`、`lc_default_by_*.csv`、基础图表 |
| `build_lc_risk_segments.py` | 构造 Grade × Purpose、Interest × FICO 等组合风险分层 | `lc_segment_*.csv`、高风险组合图 |
| `build_state_control_analysis.py` | 控制平均利率和 FICO 后分析州级经济变量 | `lc_state_control_*.csv`、残差散点图 |
| `build_quarterly_macro_analysis.py` | 将季度违约率与 FRED 宏观变量对齐 | `lc_default_by_quarter_with_fred_macro.csv`、季度趋势图 |

## 依赖关系

```text
analysis/analyze_lending_club.py
  ↓
data/build_fred_macro_features.py
  ↓
analysis/build_quarterly_macro_analysis.py
```

`analysis/` 生成的表格会被 `modeling/`、`strategy/`、`visualization/`、`llm/` 和 `dashboard/` 复用。
