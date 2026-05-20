# 中期汇报核心发现：结论—证据—图表索引

## 总体结论

本项目已经从开题阶段推进到真实数据分析阶段。当前主线不再只是“计划做多源数据融合”，而是已经完成 Lending Club 真实贷款数据、FRED 宏观金融数据、USDA ERS 州级经济数据的多轮处理与初步融合。

## 1. 贷款风险具有明显等级梯度

**结论：** Lending Club 的贷款等级能够显著区分违约风险，是后续分析中的重要基准变量。

**证据：**

- A 等级违约率约 6.57%。
- G 等级违约率约 51.57%。
- 整体已完结样本违约率为 21.27%。

**图表：**

- `outputs/figures/lc_default_rate_by_grade.png`
- `outputs/tables/lc_default_by_grade.csv`

**汇报表达：**

> 第一层风险已经能从平台自身的等级体系中看到：从 A 到 G，违约率呈明显上升趋势。这说明个体信用风险是违约检测的基础，但它还不能解释地区和宏观差异。

## 2. 利率与违约风险高度相关

**结论：** 贷款利率越高，违约率越高，说明平台定价中已经包含了风险补偿。

**证据：**

- `<8%` 利率分箱违约率约 6.38%。
- `>=24%` 利率分箱违约率约 48.56%。

**图表：**

- `outputs/figures/lc_default_rate_by_interest_bin.png`
- `outputs/tables/lc_default_by_interest_bin.csv`

**汇报表达：**

> 利率不是随机给出的，它本身已经包含了平台对风险的判断。高利率贷款违约率明显更高，因此后续分析地区和宏观变量时，必须考虑利率结构。

## 3. FICO 仍然有解释力，但不是全部

**结论：** FICO 分数越低，违约率通常越高，传统信用评分仍然有效；但项目的价值在于进一步补充地区经济和宏观环境变量。

**证据：**

- FICO 分箱违约率呈现信用分越低风险越高的趋势。
- 州级平均 FICO 与州级违约率相关系数为 -0.4523。

**图表：**

- `outputs/figures/lc_default_rate_by_fico_bin.png`
- `outputs/figures/lc_state_default_vs_avg_fico.png`
- `outputs/tables/lc_default_by_fico_bin.csv`
- `outputs/tables/lc_state_control_findings.md`

**汇报表达：**

> 我们不是否定传统信用评分，而是在其基础上引入外部环境变量，观察是否能解释单一信用分无法解释的风险差异。

## 4. 贷款用途、期限和金额进一步细分风险

**结论：** 除等级、利率、FICO 外，贷款用途、期限和金额也能提供额外风险切分。

**证据：**

- small_business 用途违约率约 31.53%。
- 60 months 贷款期限违约率约 34.29%。
- `>=30k` 贷款金额分箱违约率约 26.34%。

**图表：**

- `outputs/figures/lc_default_rate_by_purpose.png`
- `outputs/figures/lc_default_rate_by_term.png`
- `outputs/figures/lc_default_rate_by_loan_amount.png`
- `outputs/tables/lc_default_by_purpose_min1000.csv`
- `outputs/tables/lc_default_by_term.csv`
- `outputs/tables/lc_default_by_loan_amount_bin.csv`

**汇报表达：**

> 风险并不是单一维度决定的。相同信用等级下，贷款用途、期限和金额仍然会进一步改变风险结构。

## 5. 组合风险分层能识别高风险人群

**结论：** 组合维度比分别看单一变量更适合刻画高风险群体。

**证据：**

- Grade × Term 最高风险组合：G / 60 months，违约率 51.64%，样本数 7,817。
- Grade × Purpose 最高风险组合：G / debt_consolidation，违约率 52.99%，样本数 5,861。
- Interest × FICO 最高风险组合：`>=24% / 660-700`，违约率 49.13%，样本数 33,588。
- State × Grade 最高风险组合：CA / G，违约率 50.04%，样本数 1,279。

**图表：**

- `outputs/figures/lc_top_risk_grade_term_segments.png`
- `outputs/figures/lc_top_risk_grade_purpose_segments.png`
- `outputs/figures/lc_top_risk_interest_fico_segments.png`
- `outputs/figures/lc_top_risk_state_grade_segments.png`
- `outputs/tables/lc_segment_findings.md`

**汇报表达：**

> 如果只看单个变量，我们只能得到粗粒度结论；组合分层可以直接告诉我们哪些人群是高风险候选，这更接近真实风控场景。

## 6. 宏观金融环境与年度/季度违约率存在相关性

**结论：** Lending Club 年度和季度违约率与 FRED 宏观指标存在一定相关性，说明宏观环境值得纳入分析框架。

**证据：**

年度：

- 联邦基金利率与年度违约率相关系数：0.9408。
- CPI 通胀率与年度违约率相关系数：0.4347。

季度：

- 联邦基金利率与季度违约率相关系数：0.844。
- CPI 通胀率与季度违约率相关系数：0.3041。
- 季度级数据共有 47 个时间点，比年度 12 个点更适合分析趋势。

**图表：**

- `outputs/figures/lc_fred_macro_overlay.png`
- `outputs/figures/lc_fred_quarterly_overlay.png`
- `outputs/tables/fred_macro_findings.md`
- `outputs/tables/fred_quarterly_findings.md`

**汇报表达：**

> 我们已经把贷款发放时间和宏观金融时间序列对齐。当前结果不能说明因果，但说明宏观变量可能解释部分风险周期变化。

## 7. 地区经济变量与州级违约率存在关系

**结论：** 州级贫困率、收入与 Lending Club 州级违约率存在可解释的方向性相关。

**证据：**

- USDA ERS 州级贫困率与州级违约率相关系数：0.3982。
- 州级家庭收入中位数与州级违约率相关系数：-0.4041。
- 已匹配 50 个州。

**图表：**

- `outputs/figures/lc_state_default_vs_poverty.png`
- `outputs/figures/lc_state_default_vs_income.png`
- `outputs/figures/lc_state_default_vs_unemployment.png`
- `outputs/tables/ers_state_findings.md`

**汇报表达：**

> 地区经济变量并非噪音。贫困率更高、收入更低的州，整体违约率有上升趋势，这支持我们在开题中提出的“地区环境影响个人贷款风险”的假设。

## 8. 控制贷款结构后，地区变量仍有解释空间

**结论：** 即使考虑州级平均利率和平均 FICO，贫困率与违约率残差仍保持一定相关性。

**证据：**

- 贫困率与原始州级违约率相关系数：0.3982。
- 控制平均利率后的违约率残差与贫困率相关系数：0.3621。
- 控制平均 FICO 后的违约率残差与贫困率相关系数：0.4586。

**图表：**

- `outputs/figures/lc_state_default_residual_interest_vs_poverty.png`
- `outputs/figures/lc_state_default_residual_fico_vs_poverty.png`
- `outputs/tables/lc_state_control_findings.md`

**汇报表达：**

> 我们进一步检查了一个可能的反驳：是不是某些州只是高利率、高风险贷款更多？控制平均利率和平均 FICO 后，贫困率与违约率残差仍有相关性，说明地区环境值得继续分析。

## 中期汇报最推荐展示的 8 张图

1. `outputs/figures/lc_default_rate_by_grade.png`
2. `outputs/figures/lc_default_rate_by_interest_bin.png`
3. `outputs/figures/lc_default_rate_by_fico_bin.png`
4. `outputs/figures/lc_default_rate_by_purpose.png`
5. `outputs/figures/lc_top_risk_grade_purpose_segments.png`
6. `outputs/figures/lc_fred_quarterly_overlay.png`
7. `outputs/figures/lc_state_default_vs_poverty.png`
8. `outputs/figures/lc_state_default_residual_interest_vs_poverty.png`

## 一句话总结

> 中期阶段已经证明：贷款违约风险不仅能被个人信用变量解释，还与贷款用途、期限、地区经济和宏观金融环境存在可观察关系；下一阶段应围绕多源融合后的解释性建模继续推进。
