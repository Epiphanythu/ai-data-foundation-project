"""build_temporal_features.py 时序特征工程模块
提供滚动窗口统计、时间衰减特征、季节/节假日因子的构建功能。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from constant.columns import (
    COL_ANNUAL_INC,
    COL_DAY_OF_WEEK,
    COL_DECAYED_AMNT,
    COL_DECAYED_FICO,
    COL_DECAYED_INT_RATE,
    COL_FICO_AVG,
    COL_INT_RATE,
    COL_INSTALLMENT,
    COL_IS_HOLIDAY,
    COL_IS_MONTH_END,
    COL_IS_QUARTER_END,
    COL_IS_WEEKEND,
    COL_ISSUE_D,
    COL_ISSUE_DATE,
    COL_ISSUE_MONTH,
    COL_LOAN_AMNT,
    COL_MONTH_OF_YEAR,
    COL_ROLLING_MEAN_30D,
    COL_ROLLING_MEAN_60D,
    COL_ROLLING_MEAN_90D,
    COL_ROLLING_STD_30D,
    COL_ROLLING_STD_60D,
    COL_ROLLING_STD_90D,
    COL_ROLLING_TREND_30D,
    COL_ROLLING_TREND_60D,
    COL_ROLLING_TREND_90D,
    COL_SEASON,
)
from constant.paths import TABLES_DIR

logger = logging.getLogger(__name__)

# 美国联邦节假日（2007-2018年）
US_HOLIDAYS = [
    # 新年
    "2007-01-01", "2008-01-01", "2009-01-01", "2010-01-01", "2011-01-01",
    "2012-01-02", "2013-01-01", "2014-01-01", "2015-01-01", "2016-01-01",
    "2017-01-02", "2018-01-01",
    # 马丁·路德·金纪念日
    "2007-01-15", "2008-01-21", "2009-01-19", "2010-01-18", "2011-01-17",
    "2012-01-16", "2013-01-21", "2014-01-20", "2015-01-19", "2016-01-18",
    "2017-01-16", "2018-01-15",
    # 总统日
    "2007-02-19", "2008-02-18", "2009-02-16", "2010-02-15", "2011-02-21",
    "2012-02-20", "2013-02-18", "2014-02-17", "2015-02-16", "2016-02-15",
    "2017-02-20", "2018-02-19",
    # 阵亡将士纪念日
    "2007-05-28", "2008-05-26", "2009-05-25", "2010-05-31", "2011-05-30",
    "2012-05-28", "2013-05-27", "2014-05-26", "2015-05-25", "2016-05-30",
    "2017-05-29", "2018-05-28",
    # 独立日
    "2007-07-04", "2008-07-04", "2009-07-04", "2010-07-05", "2011-07-04",
    "2012-07-04", "2013-07-04", "2014-07-04", "2015-07-03", "2016-07-04",
    "2017-07-04", "2018-07-04",
    # 劳动节
    "2007-09-03", "2008-09-01", "2009-09-07", "2010-09-06", "2011-09-05",
    "2012-09-03", "2013-09-02", "2014-09-01", "2015-09-07", "2016-09-05",
    "2017-09-04", "2018-09-03",
    # 哥伦布日
    "2007-10-08", "2008-10-13", "2009-10-12", "2010-10-11", "2011-10-10",
    "2012-10-08", "2013-10-14", "2014-10-13", "2015-10-12", "2016-10-10",
    "2017-10-09", "2018-10-08",
    # 退伍军人节
    "2007-11-11", "2008-11-11", "2009-11-11", "2010-11-11", "2011-11-11",
    "2012-11-12", "2013-11-11", "2014-11-11", "2015-11-11", "2016-11-11",
    "2017-11-10", "2018-11-11",
    # 感恩节
    "2007-11-22", "2008-11-27", "2009-11-26", "2010-11-25", "2011-11-24",
    "2012-11-22", "2013-11-28", "2014-11-27", "2015-11-26", "2016-11-24",
    "2017-11-23", "2018-11-22",
    # 圣诞节
    "2007-12-25", "2008-12-25", "2009-12-25", "2010-12-24", "2011-12-26",
    "2012-12-25", "2013-12-25", "2014-12-25", "2015-12-25", "2016-12-26",
    "2017-12-25", "2018-12-25",
]

# 季节映射
SEASON_MAP = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def build_time_decay_features(
    df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
    decay_lambda: float = 0.001,
) -> pd.DataFrame:
    """build_time_decay_features 构建时间衰减特征
    
    时间衰减特征：越近期的数据权重越高，公式为 exp(-λ*t) * feature
    
    Args:
        df: 包含 issue_d 字段的 DataFrame
        reference_date: 参考日期，默认为数据中的最大日期
        decay_lambda: 衰减系数，值越大衰减越快
    
    Returns:
        添加了时间衰减特征的 DataFrame
    """
    df = df.copy()
    
    if COL_ISSUE_DATE not in df.columns:
        df[COL_ISSUE_DATE] = pd.to_datetime(df[COL_ISSUE_D], format="%b-%Y", errors="coerce")
    
    if reference_date is None:
        reference_date = df[COL_ISSUE_DATE].max()
    
    df["_days_since"] = (reference_date - df[COL_ISSUE_DATE]).dt.days.fillna(0)
    df["_decay_weight"] = np.exp(-decay_lambda * df["_days_since"])
    
    df[COL_DECAYED_AMNT] = df[COL_LOAN_AMNT] * df["_decay_weight"]
    df[COL_DECAYED_INT_RATE] = df[COL_INT_RATE] * df["_decay_weight"]
    df[COL_DECAYED_FICO] = df[COL_FICO_AVG] * df["_decay_weight"]
    
    df = df.drop(["_days_since", "_decay_weight"], axis=1)
    logger.info("Built time decay features for %d rows", len(df))
    return df


def build_rolling_window_features(
    df: pd.DataFrame,
    window_sizes: Sequence[int] = (30, 60, 90),
) -> pd.DataFrame:
    """build_rolling_window_features 构建滚动窗口统计特征
    
    按日期排序后，计算指定窗口大小的滚动均值、标准差和趋势斜率。
    
    Args:
        df: 包含 issue_d 和数值字段的 DataFrame
        window_sizes: 窗口大小列表（单位：天）
    
    Returns:
        添加了滚动窗口特征的 DataFrame
    """
    df = df.copy()
    
    if COL_ISSUE_DATE not in df.columns:
        df[COL_ISSUE_DATE] = pd.to_datetime(df[COL_ISSUE_D], format="%b-%Y", errors="coerce")
    
    df = df.sort_values(by=COL_ISSUE_DATE).reset_index(drop=True)
    base_series = df[COL_INSTALLMENT].fillna(0)
    
    for window in window_sizes:
        df[f"rolling_mean_{window}d"] = base_series.rolling(window=window, min_periods=1).mean()
        df[f"rolling_std_{window}d"] = base_series.rolling(window=window, min_periods=2).std().fillna(0)
        df[f"rolling_trend_{window}d"] = _rolling_trend(base_series, window)
    
    logger.info("Built rolling window features with windows: %s", window_sizes)
    return df


def _rolling_trend(series: pd.Series, window: int) -> pd.Series:
    """_rolling_trend 计算滚动窗口内的趋势斜率"""
    trend_values = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        window_data = series.iloc[start:i+1]
        
        if len(window_data) < 2:
            trend_values.append(0.0)
            continue
        
        x = np.arange(len(window_data))
        slope, _, _, _, _ = stats.linregress(x, window_data.values)
        trend_values.append(slope)
    
    return pd.Series(trend_values, index=series.index)


def build_seasonal_holiday_features(df: pd.DataFrame) -> pd.DataFrame:
    """build_seasonal_holiday_features 构建季节/节假日因子特征
    
    Args:
        df: 包含 issue_d 字段的 DataFrame
    
    Returns:
        添加了季节/节假日特征的 DataFrame
    """
    df = df.copy()
    
    if COL_ISSUE_DATE not in df.columns:
        df[COL_ISSUE_DATE] = pd.to_datetime(df[COL_ISSUE_D], format="%b-%Y", errors="coerce")
    
    df[COL_ISSUE_MONTH] = df[COL_ISSUE_DATE].dt.month
    df[COL_MONTH_OF_YEAR] = df[COL_ISSUE_DATE].dt.month.astype(str)
    df[COL_DAY_OF_WEEK] = df[COL_ISSUE_DATE].dt.dayofweek.astype(str)
    
    df[COL_IS_WEEKEND] = (df[COL_ISSUE_DATE].dt.dayofweek >= 5).astype(int)
    
    df["_date_str"] = df[COL_ISSUE_DATE].dt.strftime("%Y-%m-%d")
    df[COL_IS_HOLIDAY] = df["_date_str"].isin(US_HOLIDAYS).astype(int)
    
    df[COL_IS_MONTH_END] = df[COL_ISSUE_DATE].dt.is_month_end.astype(int)
    df[COL_IS_QUARTER_END] = df[COL_ISSUE_DATE].dt.is_quarter_end.astype(int)
    
    df[COL_SEASON] = df[COL_ISSUE_MONTH].map(SEASON_MAP).fillna("unknown")
    df = df.drop(["_date_str"], axis=1)
    
    logger.info("Built seasonal/holiday features for %d rows", len(df))
    return df


def build_all_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """build_all_temporal_features 一键构建所有时序特征"""
    logger.info("Starting temporal feature engineering...")
    df = build_seasonal_holiday_features(df)
    df = build_time_decay_features(df)
    df = build_rolling_window_features(df)
    logger.info("Completed temporal feature engineering")
    return df


def analyze_temporal_features(df: pd.DataFrame) -> None:
    """analyze_temporal_features 分析时序特征的统计信息"""
    logger.info("Analyzing temporal features...")
    
    holiday_stats = df[COL_IS_HOLIDAY].value_counts().reset_index()
    holiday_stats.columns = ["is_holiday", "count"]
    holiday_stats["percentage"] = holiday_stats["count"] / len(df)
    
    season_stats = df[COL_SEASON].value_counts().reset_index()
    season_stats.columns = ["season", "count"]
    season_stats["percentage"] = season_stats["count"] / len(df)
    
    weekend_stats = df[COL_IS_WEEKEND].value_counts().reset_index()
    weekend_stats.columns = ["is_weekend", "count"]
    weekend_stats["percentage"] = weekend_stats["count"] / len(df)
    
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    holiday_stats.to_csv(TABLES_DIR / "temporal_holiday_stats.csv", index=False)
    season_stats.to_csv(TABLES_DIR / "temporal_season_stats.csv", index=False)
    weekend_stats.to_csv(TABLES_DIR / "temporal_weekend_stats.csv", index=False)
    
    logger.info("Temporal feature analysis saved")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 模拟数据加载和预处理，以避免循环导入 _model_data.py
    # 实际应用中，这里会根据需要加载原始数据并进行基本处理
    # 为了演示，我们创建一个虚拟 DataFrame
    data = {
        'issue_d': pd.to_datetime(['2015-01-01', '2015-02-01', '2015-03-01', '2015-04-01', '2015-05-01', '2015-06-01']),
        'loan_amnt': [10000, 12000, 15000, 11000, 13000, 16000],
        'int_rate': [10.5, 11.0, 10.0, 12.0, 11.5, 10.8],
        'fico_avg': [700, 710, 690, 705, 715, 695],
        'installment': [300, 350, 400, 320, 380, 420],
    }
    df = pd.DataFrame(data)
    df['issue_date'] = df['issue_d'] # COL_ISSUE_DATE
    
    df = build_all_temporal_features(df)
    analyze_temporal_features(df)
    
    temporal_features = [
        COL_ROLLING_MEAN_30D, COL_ROLLING_MEAN_60D, COL_ROLLING_MEAN_90D,
        COL_ROLLING_STD_30D, COL_ROLLING_STD_60D, COL_ROLLING_STD_90D,
        COL_ROLLING_TREND_30D, COL_ROLLING_TREND_60D, COL_ROLLING_TREND_90D,
        COL_DECAYED_AMNT, COL_DECAYED_INT_RATE, COL_DECAYED_FICO,
        COL_IS_HOLIDAY, COL_IS_WEEKEND, COL_IS_QUARTER_END, COL_IS_MONTH_END,
        COL_SEASON, COL_MONTH_OF_YEAR, COL_DAY_OF_WEEK,
    ]
    
    print("\nGenerated temporal features:")
    for feat in temporal_features:
        print(f"  - {feat}")
    print(f"\nTotal features added: {len(temporal_features)}")
    print(f"DataFrame shape after feature engineering: {df.shape}")