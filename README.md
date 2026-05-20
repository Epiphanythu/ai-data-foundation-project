# 基于多源数据的个人贷款违约风险检测

## 项目简介

本项目面向金融领域个人贷款违约风险检测，尝试融合个人信贷数据、区域经济数据与宏观金融数据，分析违约风险与个体特征、地区环境、宏观周期之间的关系。中期阶段重点展示数据获取、清洗、融合、统计分析和可视化流程，而不是追求复杂模型的最终精度。

## 数据来源

计划使用四类真实世界数据：

1. Lending Club 贷款数据：个人贷款记录、贷款状态、利率、信用等级、收入等。
2. Home Credit Default Risk：申请人信贷与人口统计特征，可作为补充对照数据。
3. 美国 ACS 5 年区域经济数据：州/县级收入、贫困率、就业等区域变量。
4. 美国联邦储备宏观金融数据：利率、通胀率、失业率等宏观变量。

Kaggle 数据需要手动下载，放置方式见 `data/README.md`。

## 当前中期进度

- 已完成项目开题报告。
- 已建立中期可提交的代码仓库结构。
- 已提供 Kaggle 数据接入约定，并已在本地下载 Lending Club accepted 贷款数据。
- 已实现一个可运行的中期演示流水线：在贷款数据尚未下载时，使用样例贷款、区域与宏观数据展示多源融合流程。
- 已完成 Lending Club 真实数据的阶段性分析：共读取 2,260,701 条 accepted 贷款记录，其中 1,367,578 条已完结记录用于违约率统计。
- 已生成真实 Lending Club 统计表和图表，覆盖等级、利率、FICO、州、年份、用途、住房状态、贷款金额、期限、收入验证和就业年限等维度。
- 已接入 FRED 公开宏观金融数据，将年度违约率与联邦基金利率、失业率、CPI 通胀率按年份对齐，形成第一版真实多源融合结果。
- 已接入 USDA ERS 州级经济数据，将 Lending Club 州级违约率与收入、贫困率、失业率融合，匹配 50 个州。
- 已完成组合风险分层分析，覆盖 Grade×Term、Grade×Purpose、Interest×FICO、State×Grade 等高风险人群切片。
- 已完成州级控制变量分析，在州级违约率中加入平均利率、平均 FICO、等级结构和 ERS 经济特征，初步评估地区变量的边际关系。
- 已完成季度级 Lending Club × FRED 宏观融合，将年度 12 个时间点扩展到 47 个季度时间点。
- 已准备 Markdown 版中期 PPT 框架。

## 数据流水线

```text
原始数据 / 样例数据
  ↓
数据探索：规模、字段、缺失值、标签分布
  ↓
数据清洗：字段标准化、缺失值统计、异常值检查
  ↓
多源融合：按州连接区域经济数据，按年份连接宏观金融数据
  ↓
SQL 聚合：按州统计样例贷款数量、违约率、收入与贫困率
  ↓
统计分析：贷款等级、地区、宏观指标与违约率关系
  ↓
可视化输出：PNG 图表与 CSV 表格
```

## 环境配置

建议使用 Python 3.10 或以上版本。

```bash
cd /Users/bytedance/Desktop/DB
python3 -m pip install -r requirements.txt
```

## 如何运行

运行中期样例流水线：

```bash
cd /Users/bytedance/Desktop/DB
python3 src/run_midterm_pipeline.py
```

如果 `data/raw/` 中没有 Kaggle 贷款 CSV，脚本会生成样例多源数据并输出样例图表。若后续放入 Lending Club 或 Home Credit CSV，脚本会自动额外生成贷款数据概览、缺失率统计和标签分布图。

运行 Lending Club 真实数据分析：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/analyze_lending_club.py
```

该脚本会流式读取大型 Lending Club CSV，不会把完整数据一次性载入内存，并输出 `outputs/tables/lc_*` 与 `outputs/figures/lc_*`。

运行 FRED 宏观数据接入与年度融合：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_fred_macro_features.py
```

该脚本会下载 FRED 月度宏观数据，聚合为年度指标，并与 Lending Club 年度违约率按 `issue_year` 对齐。

运行 USDA ERS 州级经济数据接入：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_ers_state_features.py
```

该脚本会下载 ERS 收入/失业率/贫困率数据，提取州级特征，并与 Lending Club 州级违约率按 `addr_state` 对齐。

运行 Lending Club 组合风险分层分析：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_lc_risk_segments.py
```

该脚本会生成 Grade×Term、Grade×Purpose、Interest×FICO、State×Grade 等组合风险切片，用于识别高风险人群。

运行州级控制变量分析：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_state_control_analysis.py
```

该脚本会构建州级控制变量表，将违约率、平均利率、平均 FICO、等级结构和 ERS 经济特征合并，并输出残差相关分析。

运行季度级 Lending Club × FRED 宏观融合：

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_quarterly_macro_analysis.py
```

该脚本会按季度聚合 Lending Club 违约率，并与 FRED 季度宏观指标对齐。

## 输出产物

- 样例数据：`data/sample/`
- 融合后数据：`data/processed/sample_integrated_credit_risk.csv`
- 统计表：`outputs/tables/`
- 图表：`outputs/figures/`
- Lending Club 阶段性发现：`outputs/tables/lc_findings.md`
- 真实数据图表：`outputs/figures/lc_default_rate_by_grade.png`、`outputs/figures/lc_default_rate_by_interest_bin.png`、`outputs/figures/lc_default_rate_by_fico_bin.png`、`outputs/figures/lc_default_rate_by_year.png`、`outputs/figures/lc_default_rate_top_states.png`
- 追加维度图表：`outputs/figures/lc_default_rate_by_purpose.png`、`outputs/figures/lc_default_rate_by_home_ownership.png`、`outputs/figures/lc_default_rate_by_loan_amount.png`、`outputs/figures/lc_default_rate_by_term.png`
- 宏观融合结果：`outputs/tables/lc_default_by_year_with_fred_macro.csv`、`outputs/tables/lc_fred_macro_correlations.csv`、`outputs/figures/lc_fred_macro_overlay.png`
- 州级经济融合结果：`outputs/tables/lc_default_by_state_with_ers_features.csv`、`outputs/tables/lc_ers_state_correlations.csv`、`outputs/figures/lc_state_default_vs_poverty.png`、`outputs/figures/lc_state_default_vs_income.png`、`outputs/figures/lc_state_default_vs_unemployment.png`
- 组合风险分层结果：`outputs/tables/lc_segment_findings.md`、`outputs/tables/lc_segment_*.csv`、`outputs/figures/lc_top_risk_*_segments.png`
- 州级控制变量结果：`outputs/tables/lc_state_control_features.csv`、`outputs/tables/lc_state_control_correlations.csv`、`outputs/tables/lc_state_control_findings.md`、`outputs/figures/lc_state_default_residual_*_vs_poverty.png`
- 季度级宏观融合结果：`outputs/tables/lc_default_by_quarter_with_fred_macro.csv`、`outputs/tables/lc_fred_quarterly_correlations.csv`、`outputs/tables/fred_quarterly_findings.md`、`outputs/figures/lc_fred_quarterly_overlay.png`
- 数据字典与标签定义：`outputs/tables/data_dictionary.md`
- 分析产物索引：`outputs/tables/analysis_index.md`
- 中期汇报框架：`slides/midterm_outline.md`
- 中期汇报 PPT：`slides/midterm_report.pptx`

## 生成 PPT

```bash
cd /Users/bytedance/Desktop/DB
python3 scripts/build_midterm_deck.py
```

脚本会读取 `outputs/figures/` 中的样例图表，生成 `slides/midterm_report.pptx`。

## 小组分工建议

- 成员 A：贷款数据下载、清洗、缺失值与异常值处理。
- 成员 B：ACS/Fed 外部数据处理、多源融合、SQL/DataFrame 聚合。
- 成员 C：可视化、PPT 整理、初步结论与答辩准备。

## 后续计划

1. 继续尝试接入 Home Credit 数据；该数据集需要先在 Kaggle 网页端接受 competition rules。
2. 扩展 Lending Club 清洗规则，加入贷款金额、用途、就业年限、住房状态等更多变量。
3. 接入真实 ACS/Fed 数据，完成州级和年度/季度级融合。
4. 对比单一贷款数据与多源融合数据的分析结果。
5. 制作最终 PPT、报告、代码 README 和 3 分钟演示视频。
