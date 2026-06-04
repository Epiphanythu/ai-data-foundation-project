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
