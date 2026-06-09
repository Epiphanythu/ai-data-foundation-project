"""model.py 模型相关常量"""

# 训练采样规模（None 表示使用全量数据；建议 Dashboard/快速实验设置整数抽样）
TRAIN_SAMPLE_SIZE = None
RANDOM_SEED = 42
TEST_SIZE = 0.2

# 时序划分：最后 N 年作为测试集，其余为训练集
TEST_YEARS = [2017, 2018]

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
    # 季节/节假日二元特征
    "is_holiday",
    "is_weekend",
    "is_quarter_end",
    "is_month_end",
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

# 跨源融合数值特征（FRED 宏观 + ERS 州级 + 交互项）
CROSS_SOURCE_NUMERIC_FEATURES = [
    "fed_funds_rate",
    "unemployment_rate",
    "cpi_inflation",
    "state_poverty_pct",
    "state_unemployment_rate",
    "state_median_income",
    "interact_int_rate_x_fed_funds",
    "interact_loan_amnt_x_state_unemp",
    "interact_fico_x_cpi",
]

# 三组实验的特征集合（点 1 基准对比，本阶段先用 base，后续可扩展）
FEATURE_SET_BASE = "base"
FEATURE_SET_WITH_MACRO = "with_macro"
FEATURE_SET_WITH_REGION = "with_region"

# 模型标识
MODEL_LR = "logistic_regression"
MODEL_XGB = "xgboost"
MODEL_LGB = "lightgbm"
MODEL_STACKING = "stacking_ensemble"

# 默认风控阈值
DEFAULT_THRESHOLD = 0.5

# 风控策略模拟参数
STRATEGY_THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 20)]  # 0.05 ~ 0.95
ASSUMED_LGD = 0.55  # 违约损失率
ASSUMED_INTEREST_MARGIN = 0.08  # 平均息差（用于利润估算）

# 状态感知动态风控参数
MACRO_STATE_LOW = "正常期"
MACRO_STATE_MID = "观察期"
MACRO_STATE_HIGH = "压力期"
MACRO_STATE_GLOBAL = "全局"
MACRO_STATE_LABELS = [MACRO_STATE_LOW, MACRO_STATE_MID, MACRO_STATE_HIGH]
MACRO_STATE_QUANTILES = [0.33, 0.67]
MODEL_VALIDATION_TOP_DECILE_RATE = 0.10
STATE_AWARE_MODEL_FEATURE_GROUP = "current_baseline_temporal"
STATE_AWARE_PROBA_COL = "xgb_proba"
STATE_AWARE_PROBA_COLUMNS = {
    MODEL_LR: "lr_proba",
    MODEL_XGB: "xgb_proba",
}
STATE_AWARE_STRATEGY_TYPE = "state_aware_threshold"
FIXED_BEST_STRATEGY_TYPE = "fixed_best_threshold"
STATE_THRESHOLD_SHIFT = {
    MACRO_STATE_LOW: 0.05,
    MACRO_STATE_MID: 0.00,
    MACRO_STATE_HIGH: -0.05,
}

# ========================
# AutoML 常量
# ========================
AUTOML_N_TRIALS = 30  # Optuna 优化 trial 数
AUTOML_CV_FOLDS = 5  # TimeSeriesSplit 折数
AUTOML_RFE_MIN_FEATURES = 5  # RFE 最少保留特征数
AUTOML_RFE_STEP = 1  # RFE 每次删除的特征数
AUTOML_TIMESERIES_CV_GAP = 0  # TimeSeriesSplit gap（0 表示无间隔）
