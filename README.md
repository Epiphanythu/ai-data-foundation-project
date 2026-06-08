# Personal Loan Default Risk Analysis System

本项目是一个面向个人贷款违约风险的多源数据分析与智能风控系统。项目不再采用 `scripts/` 平铺结构，而是按业务能力拆成独立分层模块：数据、分析、建模、解释性、策略、可视化、LLM 和 Dashboard。

## 项目主线

项目围绕“宏观非平稳环境下的贷款违约动态风险决策”展开：

1. 融合 Lending Club 贷款数据、FRED 宏观数据和 ERS 州级经济数据。
2. 通过数据分析识别违约风险在等级、利率、FICO、州、季度、宏观状态上的差异。
3. 训练基准模型并加入宏观、地区、时序和状态特征做验证。
4. 用 SHAP、PDP、因果分析和反事实解释模型结果。
5. 用固定阈值、动态阈值和状态感知策略做风控收益评估。
6. 用独立可视化模块生成高质量图表。
7. 用 Dashboard 和 LLM 助手完成最终交互展示与自然语言问答。

## 分层架构

```text
DB/
├── main.py                    # 一键运行入口，按依赖顺序调度各模块
├── constant/                  # 全局常量：路径、字段、模型参数、LLM 配置
├── common/                    # 共享工具：模型数据构造、LLM 客户端
├── data/                      # 数据层：原始数据、外部数据、融合/时序特征构造
├── analysis/                  # 数据分析层：EDA、风险分层、州级/季度分析
├── modeling/                  # 建模层：LR / XGBoost 基准模型与预测结果
├── explainability/            # 解释层：SHAP、PDP、因果、反事实、审计追溯
├── strategy/                  # 风控策略层：动态阈值、规则引擎、状态感知策略
├── visualization/             # 独立可视化层：高级图表和汇报图生成
├── llm/                       # LLM 智能层：自动报告、自然语言问答、自动出图
├── dashboard/                 # 交互展示层：Streamlit Dashboard 集成所有结果
├── outputs/                   # 运行产物：tables、figures、models、reports
└── requirements.txt           # Python 依赖
```

## 模块职责

| 模块 | 定位 | 主要职责 |
|---|---|---|
| `data/` | 数据层 | 放置原始/外部数据，构造 FRED、ERS、时序等建模特征 |
| `analysis/` | 数据分析层 | 贷款 EDA、单变量统计、组合风险分层、州级控制、季度宏观分析 |
| `modeling/` | 建模层 | 训练 Logistic Regression / XGBoost，输出模型、指标和预测结果 |
| `explainability/` | 解释层 | SHAP、PDP、因果推断、反事实解释、决策审计 |
| `strategy/` | 策略层 | 固定阈值、动态阈值、规则引擎、状态感知风控策略 |
| `visualization/` | 可视化层 | 独立生成高质量图表，输出到 `outputs/figures/` |
| `llm/` | 智能分析层 | 读取结果表和图表，生成报告，支持自然语言问答和自动出图 |
| `dashboard/` | 展示层 | 集成表格、图表、模型结果、策略结果和 LLM 助手 |
| `common/` | 共享层 | 复用数据加载、样本构造、LLM 客户端等公共能力 |
| `constant/` | 配置层 | 集中管理路径、字段名、模型参数和 LLM 配置 |

## 运行方式

### 一键运行

```bash
python main.py
```

`main.py` 会按依赖顺序执行：

```text
analysis → data → modeling → explainability → strategy → visualization
```

### 分模块运行

```bash
# 数据分析
python analysis/analyze_lending_club.py
python analysis/build_lc_risk_segments.py
python analysis/build_state_control_analysis.py
python analysis/build_quarterly_macro_analysis.py

# 数据特征构造
python data/build_fred_macro_features.py
python data/build_ers_state_features.py
python data/build_temporal_features.py

# 建模
python modeling/train_baseline_model.py

# 解释性分析
python explainability/run_shap_analysis.py
python explainability/run_causal_analysis.py
python explainability/run_explainability_enhancement.py

# 风控策略
python strategy/run_dynamic_risk_strategy.py
python strategy/run_risk_strategy_simulation.py
python strategy/state_aware_risk/run_state_aware_risk_analysis.py

# 可视化
python visualization/build_advanced_visualizations.py
python visualization/build_beautiful_visualizations.py

# LLM
python llm/llm_auto_report.py
python llm/llm_qa_system.py "违约率最高的 5 个州是哪些？"

# Dashboard
streamlit run dashboard/app.py
```

## 数据目录

| 路径 | 用途 |
|---|---|
| `data/raw/` | 手动放置 Lending Club / Home Credit 原始数据 |
| `data/external/` | FRED、ERS 等外部宏观和地区数据 |
| `outputs/tables/` | CSV、Markdown 统计结果 |
| `outputs/figures/` | 可视化图片 |
| `outputs/models/` | 模型文件、预测结果、模型指标 |
| `outputs/reports/` | 自动报告等文本产物 |

## LLM 配置

LLM 功能可选。未配置时，数据分析、建模、策略和 Dashboard 的非 AI 部分仍可运行。

```bash
cp .env.example .env
```

`.env` 示例：

```env
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_MODEL=glm-4-plus
```

## 协作约定

- `data/` 只负责数据与特征，不承担统计结论表达。
- `analysis/` 负责数据分析和阶段性发现。
- `visualization/` 是独立大模块，负责生产图表，不是 Dashboard 的子模块。
- `dashboard/` 只做交互展示和结果集成。
- `llm/` 读取标准产物做问答和报告，不直接改写核心数据。
- 新增公共函数优先放入 `common/`，新增常量放入 `constant/`。
- 不提交 `.env`、原始大数据、运行缓存和 `__pycache__`。
