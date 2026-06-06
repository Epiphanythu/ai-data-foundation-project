"""columns.py 数据列名 / 标签常量"""

# Lending Club 原始字段
COL_LOAN_STATUS = "loan_status"
COL_GRADE = "grade"
COL_SUB_GRADE = "sub_grade"
COL_INT_RATE = "int_rate"
COL_LOAN_AMNT = "loan_amnt"
COL_TERM = "term"
COL_ANNUAL_INC = "annual_inc"
COL_DTI = "dti"
COL_FICO_LOW = "fico_range_low"
COL_FICO_HIGH = "fico_range_high"
COL_PURPOSE = "purpose"
COL_HOME_OWNERSHIP = "home_ownership"
COL_VERIFICATION_STATUS = "verification_status"
COL_EMP_LENGTH = "emp_length"
COL_ADDR_STATE = "addr_state"
COL_ISSUE_D = "issue_d"
COL_INSTALLMENT = "installment"
COL_REVOL_UTIL = "revol_util"
COL_OPEN_ACC = "open_acc"
COL_DELINQ_2YRS = "delinq_2yrs"

# 衍生字段
COL_FICO_AVG = "fico_avg"
COL_TERM_MONTHS = "term_months"
COL_ISSUE_YEAR = "issue_year"
COL_ISSUE_QUARTER = "issue_quarter"
COL_ISSUE_MONTH = "issue_month"
COL_ISSUE_DAY = "issue_day"
COL_ISSUE_DATE = "issue_date"

# 时序特征字段 - 滚动窗口统计
COL_ROLLING_MEAN_30D = "rolling_mean_30d"
COL_ROLLING_MEAN_60D = "rolling_mean_60d"
COL_ROLLING_MEAN_90D = "rolling_mean_90d"
COL_ROLLING_STD_30D = "rolling_std_30d"
COL_ROLLING_STD_60D = "rolling_std_60d"
COL_ROLLING_STD_90D = "rolling_std_90d"
COL_ROLLING_TREND_30D = "rolling_trend_30d"
COL_ROLLING_TREND_60D = "rolling_trend_60d"
COL_ROLLING_TREND_90D = "rolling_trend_90d"

# 时间衰减特征
COL_DECAYED_AMNT = "decayed_loan_amnt"
COL_DECAYED_INT_RATE = "decayed_int_rate"
COL_DECAYED_FICO = "decayed_fico"

# 季节/节假日因子
COL_IS_HOLIDAY = "is_holiday"
COL_IS_WEEKEND = "is_weekend"
COL_IS_QUARTER_END = "is_quarter_end"
COL_IS_MONTH_END = "is_month_end"
COL_SEASON = "season"
COL_MONTH_OF_YEAR = "month_of_year"
COL_DAY_OF_WEEK = "day_of_week"

# 模型标签
LABEL_COL = "default_flag"

# 标签映射
GOOD_STATUSES = {"Fully Paid"}
BAD_STATUSES = {
    "Charged Off",
    "Default",
    "Late (31-120 days)",
    "Does not meet the credit policy. Status:Charged Off",
}