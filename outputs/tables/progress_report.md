# 数据处理阶段进度报告

## 已完成数据源

| 数据源 | 状态 | 产出 |
|---|---|---|
| Lending Club accepted loans | 已下载并完成多轮分析 | `outputs/tables/lc_*`, `outputs/figures/lc_*` |
| FRED 宏观金融数据 | 已下载并按年度/季度聚合 | `fred_macro_annual.csv`, `fred_macro_quarterly.csv`, `lc_default_by_year_with_fred_macro.csv`, `lc_default_by_quarter_with_fred_macro.csv` |
| USDA ERS 州级经济数据 | 已下载并提取州级特征 | `ers_state_economic_features.csv`, `lc_default_by_state_with_ers_features.csv` |
| Home Credit | 数据已准备好 | 数据已下载至 data/raw/home_credit/ |

## 核心进展

1. Lending Club 原始 accepted 记录数为 2,260,701。
2. 过滤未完结状态后，1,367,578 条记录可用于最终违约率统计。
3. 已完成单变量维度分析：等级、利率、FICO、州、年份、用途、住房状态、贷款金额、期限、收入验证、就业年限。
4. 已完成组合风险分层：Grade×Term、Grade×Purpose、Interest×FICO、State×Grade、Home Ownership×Term。
5. 已完成年度宏观融合：Lending Club 年度违约率 × FRED 联邦基金利率、失业率、CPI 通胀率。
6. 已完成季度宏观融合：Lending Club 季度违约率 × FRED 宏观指标（47个时间点）。
7. 已完成州级区域融合：Lending Club 州级违约率 × ERS 收入、贫困率、失业率。
8. 已完成州级控制变量分析：控制平均利率、平均 FICO 后，贫困率与违约率残差仍有相关性。

## 关键发现

- 已完结 Lending Club 样本总体违约率为 21.27%。
- A 等级违约率约 6.57%，G 等级约 51.57%，等级风险梯度明显。
- `<8%` 利率分箱违约率约 6.38%，`>=24%` 利率分箱约 48.56%。
- 样本量超过 1000 的州中，MS 州违约率最高，约 28.37%。
- small_business 用途违约率较高，约 31.53%。
- 60 months 贷款期限违约率约 34.29%。
- Grade×Purpose 最高风险组合为 G / debt_consolidation，违约率约 52.99%。
- FRED 年度联邦基金利率与年度违约率样本相关系数为 0.9408。
- FRED 季度联邦基金利率与季度违约率样本相关系数为 0.844。
- ERS 州级贫困率与州级违约率样本相关系数为 0.3982，州级收入与州级违约率相关系数为 -0.4041。
- 控制平均利率后的违约率残差与贫困率相关系数为 0.3621。

## 需要谨慎解释的地方

- FRED 年度相关分析样本只有 12 个年份，不能解释因果。
- ERS 州级经济数据是横截面相关，尚未控制贷款等级、利率、FICO 等个体变量。
- Lending Club 数据来自 P2P 平台，不一定代表所有商业银行个人贷款。
- Home Credit 尚未接入，跨市场对照分析仍是后续工作。

## 下一轮任务

1. 数据工作稳定后，把发现系统性整理到最终报告。
2. 尝试下载 Home Credit；如果仍受限，则记录为风险并专注 Lending Club + FRED + ERS 主线。
3. 围绕多源融合后的解释性建模继续推进。