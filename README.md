# Personal Loan Default Risk Detection

融合个人信贷、区域经济与宏观金融三类数据源的违约风险检测项目，覆盖数据清洗、多源融合、基准建模、可解释性、风控策略与 LLM 助手全流程。

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Dashboard](#dashboard)
- [LLM Assistant](#llm-assistant)
- [Data Sources](#data-sources)
- [Outputs](#outputs)
- [License](#license)

## Overview

个人贷款违约不仅与借款人自身资质（信用等级、利率、FICO、收入、负债等）有关，也受所在地区经济环境（贫困率、失业率）和宏观金融周期（利率、通胀）影响。本项目融合三类异源数据，从描述统计到机器学习建模，再到可解释性与风控策略落地，回答以下问题：

1. 哪些个人特征对违约最具区分力？—— SHAP 全局排序 + PDP 单调性
2. 区域经济能否提供边际信息？—— 控制利率与 FICO 后的州级残差分析
3. 宏观周期与违约率是否同频？—— 季度违约率 vs FRED 利率 / 失业率
4. 如何转化为风控决策？—— 阈值扫描下的通过率 / 坏账率 / 利润曲线

## Highlights

项目相对常见的"单数据源 + 单模型 + 静态报告"做法，从五个方向提出改进：

1. **从描述到预测** —— 在描述统计基础上建立 LR / XGBoost 基准模型，量化外部数据带来的边际增益（AUC / KS / Recall）。
2. **从相关到因果** —— 控制利率与 FICO 后的州级残差分析、季度宏观对齐，剥离混淆因素，提升结论可靠性。
3. **从单一到融合** —— 个人信贷 × 州级经济 × 宏观金融三层数据按州 / 时间双维对齐，构造跨层次特征。
4. **从分析到决策** —— SHAP / PDP 落地为风控策略阈值扫描，输出通过率 / 坏账率 / 召回率 / 利润曲线，可直接用于阈值决策。
5. **从静态到交互** —— Streamlit Dashboard 阈值滑块联动 + LLM 自动报告与自然语言问答，让分析结果可探索、可对话。

## Features

- **多源数据融合**：Lending Club 贷款 × USDA ERS 州级经济 × FRED 宏观指标，按州 / 时间双维对齐
- **多维统计分析**：单变量、组合分层（Grade × Term / Grade × Purpose / Interest × FICO）、州级控制变量分析
- **时序特征工程**：滚动窗口统计（均值/标准差/趋势）、时间衰减特征、季节/节假日因子
- **基准模型对比**：Logistic Regression vs XGBoost，统一 Pipeline + ColumnTransformer，输出 AUC / KS / Recall
- **因果推断增强**：双重差分法(DID)、工具变量法(IV)、中介分析，从相关走向因果
- **反事实解释**：生成“如果改变某个特征，结果会如何”的反事实预测，寻找最小改变量
- **动态阈值机制**：根据宏观经济周期和客户细分自动调整审批阈值
- **组合风控策略**：规则引擎 + 机器学习混合决策，兼顾业务规则与模型精度
- **决策追溯**：完整记录每个决策的原因和依据，支持审计追踪
- **可解释性增强**：多方法特征重要性分析 + 自然语言解释 + 合规性报告
- **专业可视化**：统一配色方案、美观图表样式、自动化图表生成（需额外安装 seaborn>=0.12）
- **可解释性**：SHAP summary / bar 全局排序 + 关键特征 PDP
- **风控策略模拟**：阈值扫描下的通过率 / 坏账率 / 召回率 / 利润曲线
- **交互式 Dashboard**：Streamlit 5 Tab，阈值滑块联动指标
- **LLM 智能助手**：自动报告生成 + Text-to-Pandas 自然语言问答，沙箱执行保证安全

## Project Structure

```
DB/
├── constant/                              # 常量集中管理（路径 / 列名 / 模型 / LLM）
│   ├── paths.py
│   ├── columns.py
│   ├── model.py
│   └── llm.py
├── scripts/
│   ├── analyze_lending_club.py            # Lending Club 单变量分析
│   ├── build_fred_macro_features.py       # FRED 年度宏观融合
│   ├── build_ers_state_features.py        # ERS 州级融合
│   ├── build_lc_risk_segments.py          # 组合风险分层
│   ├── build_state_control_analysis.py    # 州级控制变量分析
│   ├── build_quarterly_macro_analysis.py  # 季度宏观融合
│   ├── build_temporal_features.py         # 时序特征工程（滚动窗口/时间衰减/季节因子）
│   ├── train_baseline_model.py            # LR + XGBoost 基准模型
│   ├── run_shap_analysis.py               # SHAP / PDP 可解释性
│   ├── run_risk_strategy_simulation.py    # 风控策略阈值扫描
│   ├── run_causal_analysis.py             # 因果推断与反事实解释
│   ├── run_dynamic_risk_strategy.py       # 动态阈值与组合风控策略
│   ├── run_explainability_enhancement.py  # 决策追溯与可解释性增强
│   ├── build_beautiful_visualizations.py  # 专业级可视化美化
│   ├── llm_auto_report.py                 # LLM 自动报告生成
│   ├── llm_qa_system.py                   # LLM 自然语言问答
│   └── run_all_analysis.py                # 一键串联脚本
├── dashboard/
│   └── app.py                             # Streamlit 5 Tab 可视化应用
├── data/
│   ├── raw/lending_club/                  # Lending Club CSV（手动下载）
│   ├── raw/home_credit/                   # Home Credit Default Risk 数据
│   └── external/                          # FRED / ERS 数据
├── outputs/
│   ├── tables/                            # 分析 CSV 与发现 markdown
│   ├── figures/                           # 单变量 / 组合 / SHAP / PDP / 策略图
│   ├── models/                            # 模型 + metrics + 测试预测
│   └── reports/                           # LLM 自动生成报告
├── .env.example                           # LLM 凭证模板
├── AGENTS.md                              # 开发协作规约
├── README.md
└── requirements.txt
```

## Prerequisites

- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) — 项目统一使用 uv 管理虚拟环境与依赖
- macOS 用户需安装 OpenMP 才能加载 XGBoost：`brew install libomp`
- LLM 凭证（可选）：兼容 OpenAI SDK 的 API Key，可直接复用 GLM key

### 额外依赖（新功能所需）
- **因果推断模块**：需要 scipy>=1.10
- **专业可视化美化模块**：需要 seaborn>=0.12

## Installation

```bash
# 1. 克隆仓库
git clone <repo-url>
cd DB

# 2. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 3. 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 4. macOS 安装 OpenMP（XGBoost 依赖）
brew install libomp
```

## Configuration

LLM 凭证写入 `.env`（项目根目录）：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_MODEL=glm-4-plus
```

未配置 LLM 时，分析 / 建模 / Dashboard 仍可正常运行，仅 AI 助手功能不可用。

## Usage

### 一键运行全流程

```bash
python scripts/run_all_analysis.py
```

依次执行：单变量分析 → 年度宏观融合 → 州级融合 → 组合风险分层 → 州级控制变量 → 季度宏观融合 → 基准模型 → SHAP / PDP → 风控策略模拟。

### 分步运行

```bash
# 数据分析与融合
python scripts/analyze_lending_club.py
python scripts/build_fred_macro_features.py
python scripts/build_ers_state_features.py
python scripts/build_lc_risk_segments.py
python scripts/build_state_control_analysis.py
python scripts/build_quarterly_macro_analysis.py

# 时序特征工程（自动集成到训练流程）
python scripts/build_temporal_features.py

# 建模与可解释性
python scripts/train_baseline_model.py
python scripts/run_shap_analysis.py

# 因果推断与反事实解释
python scripts/run_causal_analysis.py

# 动态阈值与组合风控策略
python scripts/run_dynamic_risk_strategy.py

# 决策追溯与可解释性增强
python scripts/run_explainability_enhancement.py

# 专业级可视化美化
python scripts/build_beautiful_visualizations.py

# 风控策略
python scripts/run_risk_strategy_simulation.py
```

### 启动 Dashboard

```bash
streamlit run dashboard/app.py
# 访问 http://localhost:8501
```

## Dashboard

| Tab | Content |
|---|---|
| 数据概览 | Lending Club 单变量违约率、组合分层、州级地图、宏观叠加图 |
| 模型表现 | LR vs XGBoost 指标对比表 + 特征重要性 |
| 可解释性 | SHAP summary / bar 全局排序 + 关键特征 PDP |
| 风控策略 | 阈值扫描曲线 + 阈值滑块联动 4 个 Metric（通过率 / 坏账率 / 召回率 / 利润） |
| 因果分析 | DID/IV/中介分析结果 + 反事实解释可视化 |
| 动态策略 | 动态阈值曲线 + 宏观场景模拟 + 规则引擎结果 |
| 决策追溯 | 决策日志 + 审计报告 + 可解释性分析 |
| 可视化 | 美化图表展示 + 专业配色方案 |
| AI 助手 | 自动分析报告 + 自然语言问答输入框 |

## LLM Assistant

```bash
# 自动生成 markdown 分析报告 → outputs/reports/llm_auto_report.md
python scripts/llm_auto_report.py

# 自然语言问答（Text-to-Pandas，黑名单沙箱执行）
python scripts/llm_qa_system.py "违约率最高的 5 个州是哪些？"
python scripts/llm_qa_system.py "FICO 700 以上的违约率是多少？"
```

## Data Sources

| Source | Description | Granularity | Access |
|---|---|---|---|
| [Lending Club Loan Data](https://www.kaggle.com/datasets/wordsforthewise/lending-club) | 个人贷款记录、利率、信用等级、收入、FICO、用途、州、放款时间 | 个人 × 月 | Kaggle 手动下载 |
| [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk) | 申请人信贷与人口统计特征 | 个人 | Kaggle 手动下载 |
| [USDA ERS](https://www.ers.usda.gov/data-products/county-level-data-sets/) | 州级收入中位数、贫困率、失业率 | 州 × 年 | 已下载（`data/external/`） |
| [FRED](https://fred.stlouisfed.org/) | 联邦基金利率、CPI 通胀、宏观失业率 | 月 / 季 / 年 | API 拉取 |

数据放置规范见 [data/README.md](file:///Users/bytedance/Desktop/DB/data/README.md)。

## Outputs

| 路径 | 内容 |
|---|---|
| `outputs/tables/` | 分析统计 CSV + 关键发现 markdown + 时序特征统计 + 因果分析结果 + 反事实报告 + 动态策略结果 + 决策日志 + 审计报告 |
| `outputs/figures/` | 单变量 / 组合 / SHAP / PDP / 风控策略 PNG + 因果分析可视化 + 动态策略可视化 + 可解释性图表 + 美化图表 |
| `outputs/models/` | 训练好的 LR / XGBoost 模型、metrics.json、测试集预测 |
| `outputs/reports/` | LLM 自动生成的分析报告 |

## License

本项目用于学术研究目的（清华大学 AI 数据基础课程大作业）。