# Personal Loan Default Risk Analysis System

面向个人贷款违约风险的多源数据分析与智能风控系统。项目按业务能力分层组织，覆盖数据融合 → 建模 → 可解释性 → 风控策略 → 可视化 → LLM 智能助手 的完整链路，并通过一个 Streamlit Dashboard 与 LLM 工具集统一对外。

> 主线：在宏观非平稳环境下，基于多源数据为个人贷款做**可解释、可审计、可决策**的违约风险预测与策略仿真。

---

## 目录

- [核心结果](#核心结果)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [运行方式](#运行方式)
- [Dashboard](#dashboard)
- [LLM 与 AI 助手](#llm-与-ai-助手)
- [数据目录](#数据目录)
- [产物目录](#产物目录)
- [模块职责](#模块职责)
- [开发约定](#开发约定)
- [常见问题](#常见问题)

---

## 核心结果

| 维度 | 数值 |
|---|---|
| 全量样本量 | Lending Club 2,260,701 行（可用标签 1,367,578 行） |
| 整体违约率 | 21.27% |
| Logistic Regression（基准） | AUC **0.7073** / KS **0.3011** |
| XGBoost（基准） | AUC **0.7186** / KS **0.3178** |
| 风控策略（阈值 0.15） | 通过率 38% / 坏账率 8.94% / 利润 0.0090 |

完整指标与可复现的图表见 [`outputs/`](outputs)。

---

## 项目结构

```text
DB/
├── main.py                       # 一键运行入口，按依赖顺序串联 26 个子脚本
├── constant/                     # 全局常量：路径、字段名、模型参数、LLM 配置
├── common/                       # 共享工具：模型数据构造、LLM 客户端
├── data/                         # 数据层：原始数据 + 特征构造（FRED / ERS / 时序 / 跨源）
├── analysis/                     # 数据分析层：EDA、风险分层、州级 / 季度 / 概念漂移
├── modeling/                     # 建模层：基准模型、诊断、评分卡、生存、贝叶斯、AutoML、监控
├── explainability/               # 解释层：SHAP / PDP / 因果 / 反事实
├── strategy/                     # 风控策略层：阈值扫描、动态阈值、状态感知、压力测试、组合优化、CECL
├── visualization/                # 独立可视化层：高级图表 / 演示图
├── llm/                          # LLM 智能层：QA / RAG / 决策解释 / Agent / 自动报告
├── dashboard/                    # 展示层：Streamlit Dashboard
├── data/raw/ data/external/      # 输入数据（手动下载）
├── outputs/                      # 全部运行产物：tables / figures / models / reports
├── requirements.txt
├── .env.example
└── AGENTS.md                     # Coding Agent 协作约束（环境、约束、关键路径）
```

---

## 快速开始

> **环境要求**：Python ≥ 3.10、macOS / Linux、推荐使用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境。

### 1. 创建并激活虚拟环境

```bash
# 安装 uv（已安装可跳过）
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. 安装系统依赖（仅 macOS）

XGBoost 需要 OpenMP：

```bash
brew install libomp
```

### 3. 配置 LLM 凭证（可选）

非 LLM 功能在没有 key 时仍可使用。如需启用 AI 助手 / 自动报告：

```bash
cp .env.example .env
# 编辑 .env：
#   OPENAI_API_KEY=<your-key>
#   OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
#   OPENAI_MODEL=glm-4-plus
```

凭证由 [`constant/llm.py`](constant/llm.py) 在调用时自动加载，**无需手动 `export`**。

### 4. 准备数据

将以下数据放入对应目录（详见 [数据目录](#数据目录)）：

- `data/raw/lending_club/`：Lending Club 226 万行 CSV
- `data/raw/home_credit/`（可选）
- `data/external/`：FRED 宏观、ERS 州级数据

---

## 运行方式

### 一键运行全部分析

```bash
source .venv/bin/activate
python main.py
```

`main.py` 按依赖顺序执行 26 个脚本，分为 11 个阶段：

| 阶段 | 内容 | 主要产物 |
|---|---|---|
| 1 | 数据探索（EDA / 数据质量 / 概念漂移） | `lc_overview.csv`、`data_quality_report.md`、`concept_drift_report.md` |
| 2 | 多源数据融合（FRED / ERS / 时序 / 跨源） | `cross_source_features.csv`、`fred_macro_*.csv`、`ers_state_*.csv` |
| 3 | 风险分层与宏观关联 | `lc_segment_*.csv`、`lc_state_control_*.csv` |
| 4 | 基准模型训练 | `*.joblib`、`test_predictions.csv`、`metrics.json` |
| 5 | 风控策略模拟 | `strategy_comparison.csv`、`risk_strategy.png` |
| 6 | 可解释性（SHAP / PDP / 因果） | `shap_*.png`、`pdp/*.png`、`causal_*.csv` |
| 7 | 模型诊断 / 评分卡 / 生存 / 贝叶斯 | `model_diagnostics_report.md`、`scorecard.csv`、`survival_*.png` |
| 8 | AutoML 自动调参 | `automl_*.csv`、`automl_summary.md` |
| 9 | 风控情景分析（动态阈值 / 状态感知 / 压力测试 / 组合 / CECL） | `state_aware_*.csv`、`stress_testing_results.csv`、`portfolio_*.csv`、`cecl_*.csv` |
| 10 | MLOps 模型监控 | `model_monitoring_report.csv`、`monitoring_*.png` |
| 11 | 进阶可视化 | `outputs/figures/advanced/` |

### 单独运行某个脚本

```bash
python modeling/train_baseline_model.py
python explainability/run_explainability.py
python strategy/run_risk_strategy_simulation.py
```

---

## Dashboard

```bash
source .venv/bin/activate
streamlit run dashboard/app.py --server.port=8502
# 浏览器打开 http://localhost:8502
```

7 个 Tab：

1. **数据概览**：质量报告、概念漂移、缺失分布
2. **模型表现**：基准/AutoML 指标、特征重要性、状态感知模型验证
3. **可解释性**：SHAP / PDP / 因果分析
4. **AutoML**：自动调参结果、超参重要性、模型族对比
5. **风控策略**：阈值扫描、状态感知动态阈值
6. **决策追溯**：单笔反事实解释、决策审计
7. **AI 助手**：4 个并发子 Tab——自然语言问答 / RAG 检索 / 决策解释 / Agent

> AI 助手底层使用 ThreadPoolExecutor + `st.fragment` 局部轮询，4 个子 Tab 互相独立，可同时各跑一个长任务而互不阻塞。

---

## LLM 与 AI 助手

| 能力 | 入口 | 说明 |
|---|---|---|
| 自然语言问答（Text-to-Pandas） | [`llm/llm_qa_system.py`](llm/llm_qa_system.py) | LLM 生成 pandas 代码 → AST 黑名单 + 受限 builtins 沙箱执行 |
| RAG 检索 | [`llm/llm_rag.py`](llm/llm_rag.py) | 将 markdown 报告与产物切片嵌入 → 检索后回答 |
| 决策解释 | [`llm/llm_decision_explainer.py`](llm/llm_decision_explainer.py) | 单笔贷款的反事实 + LLM 自然语言解释 |
| Agent 智能助手 | [`llm/llm_agent.py`](llm/llm_agent.py) | 多工具调用，按需读取产物表与图回答复杂问题 |

LLM 调用统一走 [`common/llm_client.py`](common/llm_client.py)，参数从 `OPENAI_*` 环境变量解析。

### 命令行直接调用

```bash
python llm/llm_qa_system.py "违约率最高的 5 个州是哪些？请画柱状图"
```

---

## 数据目录

| 路径 | 用途 |
|---|---|
| `data/raw/lending_club/` | Lending Club 原始 CSV（手动下载） |
| `data/raw/home_credit/` | Home Credit Default Risk 数据（可选） |
| `data/external/` | FRED 宏观月度、ERS 州级经济数据 |

> 项目**不缓存** processed 数据，每次脚本读取原始 CSV，避免临时数据堆积。

---

## 产物目录

| 路径 | 内容 |
|---|---|
| `outputs/tables/` | 分析 CSV、Markdown 发现、自动报告索引 |
| `outputs/figures/` | 单变量、组合、SHAP、PDP、风控、监控等图表 |
| `outputs/models/` | 训练模型 `.joblib`、`metrics.json`、`test_predictions.csv` |
| `outputs/reports/` | LLM 自动生成的 markdown 报告 |
| `outputs/llm_rag_index/` | RAG 索引（`docs.json` / 向量缓存） |

---

## 模块职责

| 模块 | 定位 | 主要职责 |
|---|---|---|
| [`data/`](data) | 数据层 | 原始 / 外部数据；构造 FRED、ERS、时序、跨源特征 |
| [`analysis/`](analysis) | 数据分析层 | EDA、单变量统计、组合风险分层、州级控制、季度宏观、数据质量、概念漂移 |
| [`modeling/`](modeling) | 建模层 | LR / XGBoost 基准、模型诊断、评分卡、生存分析、贝叶斯、AutoML、MLOps 监控 |
| [`explainability/`](explainability) | 解释层 | SHAP、PDP、因果（DID / IV / 中介）、反事实 |
| [`strategy/`](strategy) | 策略层 | 阈值扫描、动态阈值、状态感知、压力测试、组合优化、CECL 准备金 |
| [`visualization/`](visualization) | 可视化层 | 独立生成高级图表（ROC / KS / Lift / Choropleth 等） |
| [`llm/`](llm) | 智能分析层 | 自然语言问答、RAG、决策解释、Agent、自动报告 |
| [`dashboard/`](dashboard) | 展示层 | Streamlit Dashboard，集成所有产物与 AI 助手 |
| [`common/`](common) | 共享层 | 模型数据构造、LLM 客户端 |
| [`constant/`](constant) | 配置层 | 路径、字段、模型参数、LLM 配置 |

---

## 开发约定

详见 [AGENTS.md](AGENTS.md)。核心约束：

- **环境**：统一使用 uv 管理虚拟环境，禁止 `python3 -m pip install` 污染全局
- **数据**：不在 `data/processed/` 落盘临时缓存
- **常量**：业务实现文件不写魔法值，所有常量集中在 [`constant/`](constant) 包
- **注释**：函数注释采用 `# 函数名 简述` 风格；方法体内用 `1.` `2.` `3.` 段落注释组织逻辑
- **签名变更**：修改函数签名时必须同步更新所有调用点
- **不提交**：`.env`、原始大数据、`__pycache__/`、临时调试脚本

---

## 常见问题

| 现象 | 解决 |
|---|---|
| `libxgboost.dylib could not be loaded` | `brew install libomp` |
| `KeyError: 'default_flag'` | groupby.apply 后失去分组列；新版 pandas 改用按 group 抽样 |
| Dashboard 中文乱码 | matplotlib 已注册 `PingFang SC`，仍乱码可换字体 |
| LLM 调用 401 | 检查 `.env` 中 `OPENAI_API_KEY` / `OPENAI_BASE_URL` |
| Streamlit 端口被占用 | 换端口启动：`--server.port=8502` |
| LLM QA 报"代码包含禁用模式" | 沙箱拒绝代码：含 `import` / `open` / `__xxx__` 等高危关键字，调整 prompt 重试 |

---

## License

仅供学习与研究使用。Lending Club / FRED / ERS 等数据各自遵循其原始 License。
