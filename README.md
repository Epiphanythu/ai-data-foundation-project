# 📊 基于多源数据的个人贷款违约风险检测

> 融合个人信贷数据、区域经济数据与宏观金融数据，分析违约风险的影响因素。

---

## 📚 目录
- [项目简介](#项目简介)
- [数据来源](#数据来源)
- [当前进度](#当前进度)
- [数据流水线](#数据流水线)
- [环境配置](#环境配置)
- [快速开始](#快速开始)
- [输出产物](#输出产物)
- [后续计划](#后续计划)

---

## 📝 项目简介

本项目面向金融领域个人贷款违约风险检测，尝试融合**个人信贷数据**、**区域经济数据**与**宏观金融数据**，分析违约风险与个体特征、地区环境、宏观周期之间的关系。

中期阶段重点展示**数据获取、清洗、融合、统计分析和可视化**流程，而非追求复杂模型的最终精度。

---

## 📊 数据来源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| Lending Club Loan Data | 个人贷款记录、贷款状态、利率、信用等级、收入等 | ✅ 已完成 |
| Home Credit Default Risk | 申请人信贷与人口统计特征 | ✅ 数据已准备好 |
| USDA ERS 州级经济数据 | 州级收入、贫困率、失业率 | ✅ 已完成 |
| FRED 宏观金融数据 | 利率、通胀率、失业率等宏观指标 | ✅ 已完成 |

> 注：Kaggle 数据需要手动下载，放置方式见 [data/README.md](file:///Users/bytedance/Desktop/DB/data/README.md)。

---

## ✅ 当前进度

- ✅ 项目开题报告
- ✅ 代码仓库结构搭建
- ✅ Kaggle 数据接入约定
- ✅ Lending Club 真实数据处理（2,260,701 条记录）
- ✅ 单变量维度分析（等级、利率、FICO、州、年份等）
- ✅ 多维度组合风险分层（Grade×Term、Grade×Purpose、Interest×FICO 等）
- ✅ 年度宏观融合（FRED 指标 × 年度违约率）
- ✅ 季度宏观融合（47 个时间点）
- ✅ 州级经济融合（50 个州）
- ✅ 州级控制变量分析（控制利率/FICO后的残差分析）

---

## 🔄 数据流水线

```text
📂 原始数据 / 样例数据
    ↓
🔍 数据探索：规模、字段、缺失值、标签分布
    ↓
🧹 数据清洗：字段标准化、缺失值统计、异常值检查
    ↓
🔗 多源融合：按州连接区域经济，按时间连接宏观金融
    ↓
📈 统计分析：单变量、组合分层、相关系数
    ↓
📊 可视化输出：PNG 图表 & CSV 表格
```

---

## 🛠 环境配置

建议使用 **Python 3.10+** 版本。

```bash
# 进入项目目录
cd /Users/bytedance/Desktop/DB

# 安装依赖
python3 -m pip install -r requirements.txt
```

---

## 🚀 快速开始

### 一键运行所有分析

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/run_all_analysis.py
```

### 分步运行

#### 1. Lending Club 数据分析
```bash
python3 scripts/analyze_lending_club.py
```
流式读取大型 CSV，生成统计表和可视化图表。

#### 2. FRED 宏观数据融合（年度）
```bash
python3 scripts/build_fred_macro_features.py
```
下载 FRED 月度数据并聚合为年度指标。

#### 3. USDA ERS 州级数据融合
```bash
python3 scripts/build_ers_state_features.py
```
提取州级经济特征并与 Lending Club 数据对齐。

#### 4. 组合风险分层分析
```bash
python3 scripts/build_lc_risk_segments.py
```
识别高风险人群组合。

#### 5. 州级控制变量分析
```bash
python3 scripts/build_state_control_analysis.py
```
控制平均利率和 FICO 后，评估地区变量的边际解释力。

#### 6. 季度级宏观融合
```bash
python3 scripts/build_quarterly_macro_analysis.py
```
将 Lending Club 违约率按季度聚合并与 FRED 指标对齐。

---

## 📦 输出产物

### 📈 统计表格
路径：`outputs/tables/`
- Lending Club 各维度违约率统计
- FRED 宏观融合结果
- ERS 州级经济融合结果
- 组合风险分层结果
- 分析发现文档（含 progress_report、final_midterm_findings 等）

### 🖼 可视化图表
路径：`outputs/figures/`

#### 核心汇报图
| 图表 | 说明 |
|------|------|
| `lc_default_rate_by_grade.png` | 按等级的违约率 |
| `lc_default_rate_by_interest_bin.png` | 按利率分箱的违约率 |
| `lc_default_rate_by_fico_bin.png` | 按 FICO 分箱的违约率 |
| `lc_default_rate_by_purpose.png` | 按贷款用途的违约率 |
| `lc_default_rate_top_states.png` | 违约率最高的州 |
| `lc_fred_quarterly_overlay.png` | 季度违约率与 FRED 指标 |
| `lc_state_default_residual_interest_vs_poverty.png` | 控制利率后的残差 vs 贫困率 |
| `lc_top_risk_grade_purpose_segments.png` | 等级×用途的高风险组合 |

### 📚 文档与索引
- [分析产物索引](file:///Users/bytedance/Desktop/DB/outputs/tables/analysis_index.md)：完整输出列表
- [演讲脚本](file:///Users/bytedance/Desktop/DB/slides/midterm_speech_script_v2.md)：中期汇报讲稿
- 中期 PPT：`slides/midterm.pptx`、`slides/midterm_professional.pptx`

---

## 📋 后续计划（整合可视化、数据库、LLM）

### 🎯 核心改进

#### 1️⃣ **基准模型与对比实验**
- 逻辑回归、XGBoost模型
- 3组实验：仅个人特征 vs +宏观 vs +地区
- 对比指标：AUC、准确率、召回率

#### 2️⃣ **因果推断分析**
- 倾向得分匹配（PSM）
- 因果图（DAG）
- 中介效应分析

#### 3️⃣ **特征工程与数据库整合**
- 时间序列特征、交互特征
- **数据库设计**：SQLite建模，ETL pipeline
- **SQL分析**：用SQL替代部分聚合逻辑

#### 4️⃣ **模型可解释性与风控策略**
- SHAP、PDP图
- 风控策略模拟（通过率、坏账率、利润）
- **可视化Dashboard**：Streamlit交互展示

#### 5️⃣ **LLM赋能**
- 自动分析报告生成
- 交互式问答系统
- 分析思路建议

---

### 📅 实施路线

| 阶段 | 核心任务 |
|------|----------|
| 1 | 基准模型 + 数据库整合 |
| 2 | 特征工程 + 可解释性 + Dashboard |
| 3 | 因果推断 + LLM集成 |
| 4 | 整理报告 |

---

### 🎯 **预期亮点**

1. **从描述到预测**：建立基准模型，量化外部数据价值
2. **从相关到因果**：用因果推断方法提升结论可靠性
3. **从单一到融合**：实现多源数据的深度融合
4. **从分析到决策**：将分析结果转化为可操作的风控策略
5. **从静态到交互**：可视化Dashboard + 数据库 + LLM赋能

---

## 📝 许可证

本项目用于学术研究目的。

---
