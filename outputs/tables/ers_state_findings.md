# ERS 州级经济数据融合阶段性发现

- 已下载 USDA ERS 州/县级经济数据：data/external/ers_unemployment_income_2000_2023.csv 与 data/external/ers_poverty_2023.csv。
- 已提取州级收入、贫困率、失业率，并与 Lending Club 州级违约率融合，匹配州数量：50。
- ers_unemployment_rate_2023 与州级违约率的样本相关系数：-0.0381。
- ers_median_household_income_2022 与州级违约率的样本相关系数：-0.4041。
- ers_poverty_rate_2023 与州级违约率的样本相关系数：0.3982。
- 该结果为州级横截面相关分析；下一步可进一步控制贷款等级、利率和 FICO 后再判断地区经济变量的边际解释力。