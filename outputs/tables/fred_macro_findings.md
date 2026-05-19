# FRED 宏观数据融合阶段性发现

- 已下载 FRED 月度宏观数据并聚合为年度表：data/external/fred_macro_monthly.csv。
- 已将 Lending Club 年度违约率与联邦基金利率、失业率、CPI 通胀率按 issue_year 对齐。
- avg_fed_funds_rate 与年度违约率的样本相关系数：0.9408。
- avg_unemployment_rate 与年度违约率的样本相关系数：-0.7281。
- cpi_inflation_rate 与年度违约率的样本相关系数：0.4347。
- 该结果只是年度层面的初步相关分析，不能直接解释因果；后续需要季度级或控制变量分析。