# 数据字典与标签定义

## 1. Lending Club 原始贷款数据

来源文件：`data/raw/lending_club/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv`

该文件不上传 GitHub，只上传分析脚本和衍生统计结果。

### 核心字段

| 字段 | 含义 | 当前用途 |
|---|---|---|
| `loan_status` | 贷款当前或最终状态 | 构造违约标签 |
| `grade` | Lending Club 给出的贷款等级 A-G | 分析等级风险梯度、组合分层 |
| `sub_grade` | 更细的贷款等级 | 后续可扩展 |
| `int_rate` | 贷款利率 | 利率分箱、州级平均利率控制变量 |
| `annual_inc` | 借款人年收入 | 收入分箱 |
| `addr_state` | 借款人州代码 | 州级违约率、ERS 州级经济融合 |
| `issue_d` | 贷款发放月份 | 年度/季度违约率、FRED 宏观融合 |
| `dti` | 债务收入比 | DTI 分箱 |
| `fico_range_low` / `fico_range_high` | FICO 分数区间 | 取区间中点构造 FICO 分箱和平均 FICO |
| `purpose` | 贷款用途 | 用途违约率、Grade×Purpose 分层 |
| `home_ownership` | 住房状态 | 住房状态风险分析 |
| `term` | 贷款期限 | 期限风险分析、Grade×Term 分层 |
| `verification_status` | 收入验证状态 | 收入验证风险分析 |
| `emp_length` | 就业年限 | 就业年限风险分析 |
| `loan_amnt` | 贷款金额 | 贷款金额分箱 |

## 2. 违约标签定义

### 计为非违约 `default = 0`

| loan_status | 理由 |
|---|---|
| `Fully Paid` | 贷款已还清，可视为最终非违约结果 |

### 计为违约 `default = 1`

| loan_status | 理由 |
|---|---|
| `Charged Off` | 平台确认坏账核销 |
| `Default` | 明确违约状态 |
| `Late (31-120 days)` | 长期逾期，作为中期风险分析中的违约/高风险结果 |
| `Does not meet the credit policy. Status:Charged Off` | 不满足信用政策且已核销 |

### 排除出违约率统计

| loan_status | 排除理由 |
|---|---|
| `Current` | 贷款仍在进行中，不能判断最终是否违约 |
| `In Grace Period` | 宽限期内，最终结果未确定 |
| `Late (16-30 days)` | 短期逾期，最终结果不确定 |
| 其他未列状态 | 口径不稳定，暂不纳入最终违约率 |

当前统计结果：

- 原始 accepted 记录数：2,260,701
- 纳入最终违约率统计的已完结记录数：1,367,578
- 排除未完结或结果不确定记录数：893,123
- 已完结记录总体违约率：21.27%

## 3. 外部宏观数据：FRED

来源：FRED public CSV

文件：`data/external/fred_macro_monthly.csv`

| 字段 | 含义 | 当前用途 |
|---|---|---|
| `FEDFUNDS` | 联邦基金利率 | 年度/季度宏观利率变量 |
| `UNRATE` | 美国失业率 | 年度/季度宏观就业变量 |
| `CPIAUCSL` | CPI 指数 | 计算 CPI 通胀率 |
| `observation_date` | 月度观测时间 | 聚合到年度和季度 |

输出：

- `outputs/tables/fred_macro_annual.csv`
- `outputs/tables/fred_macro_quarterly.csv`
- `outputs/tables/lc_default_by_year_with_fred_macro.csv`
- `outputs/tables/lc_default_by_quarter_with_fred_macro.csv`

## 4. 外部区域经济数据：USDA ERS

来源：USDA ERS County-Level Data Sets

文件：

- `data/external/ers_unemployment_income_2000_2023.csv`
- `data/external/ers_poverty_2023.csv`

| 字段 | 含义 | 当前用途 |
|---|---|---|
| `ers_median_household_income_2022` | 州级家庭收入中位数 | 州级经济解释变量 |
| `ers_unemployment_rate_2023` | 州级失业率 | 州级经济解释变量 |
| `ers_poverty_rate_2023` | 州级贫困率 | 州级经济解释变量 |
| `state` | 州缩写 | 与 Lending Club `addr_state` 连接 |

输出：

- `outputs/tables/ers_state_economic_features.csv`
- `outputs/tables/lc_default_by_state_with_ers_features.csv`
- `outputs/tables/lc_state_control_features.csv`

## 5. 解释注意事项

- 当前分析以统计相关为主，不直接宣称因果关系。
- FRED 年度/季度分析需要进一步控制同期贷款结构变化。
- ERS 州级分析需要结合州内贷款等级、利率和 FICO 结构解释。
- Home Credit 尚未接入，跨市场泛化结论暂不做强表述。
