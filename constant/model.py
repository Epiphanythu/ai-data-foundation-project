"""model.py 模型相关常量"""

# 训练采样规模（None 表示使用全量数据；建议 Dashboard/快速实验设置整数抽样）
TRAIN_SAMPLE_SIZE = None
RANDOM_SEED = 42
TEST_SIZE = 0.2

# 数值特征
NUMERIC_FEATURES = [
    "loan_amnt",
    "int_rate",
    "annual_inc",
    "dti",
    "fico_avg",
    "term_months",
    "installment",
    "revol_util",
    "open_acc",
    "delinq_2yrs",
    # 滚动窗口特征
    "rolling_mean_30d",
    "rolling_mean_60d",
    "rolling_mean_90d",
    "rolling_std_30d",
    "rolling_std_60d",
    "rolling_std_90d",
    "rolling_trend_30d",
    "rolling_trend_60d",
    "rolling_trend_90d",
    # 时间衰减特征
    "decayed_loan_amnt",
    "decayed_int_rate",
    "decayed_fico",
]

# 时序类别特征
TEMPORAL_CATEGORICAL_FEATURES = [
    "season",
    "month_of_year",
    "day_of_week",
]

# 类别特征
CATEGORICAL_FEATURES = [
    "grade",
    "purpose",
    "home_ownership",
    "verification_status",
    "emp_length",
    # 时序类别特征
    "season",
    "month_of_year",
    "day_of_week",
]

# 三组实验的特征集合（点 1 基准对比，本阶段先用 base，后续可扩展）
FEATURE_SET_BASE = "base"
FEATURE_SET_WITH_MACRO = "with_macro"
FEATURE_SET_WITH_REGION = "with_region"

# 模型标识
MODEL_LR = "logistic_regression"
MODEL_XGB = "xgboost"

# 默认风控阈值
DEFAULT_THRESHOLD = 0.5

# 风控策略模拟参数
STRATEGY_THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 20)]  # 0.05 ~ 0.95
ASSUMED_LGD = 0.55  # 违约损失率
ASSUMED_INTEREST_MARGIN = 0.08  # 平均息差（用于利润估算）