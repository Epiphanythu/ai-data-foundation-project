"""build_temporal_features.py 时序特征工程模块
提供滚动窗口统计、时间衰减特征、季节/节假日因子的构建功能。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Sequence

import numpy as np
import pandas as pd

from constant.columns import (
    COL_ANNUAL_INC,
    COL_DAY_OF_WEEK,
    COL_DECAYED_AMNT,
    COL_DECAYED_FICO,
    COL_DECAYED_INT_RATE,
    COL_DTI,
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

# 滚动窗口应用的数值列（贷前可观测、有经济含义的连续特征）
ROLLING_BASE_COLS = [
    COL_LOAN_AMNT,
    COL_INT_RATE,
    COL_FICO_AVG,
    COL_INSTALLMENT,
    COL_ANNUAL_INC,
    COL_DTI,
]

# 季节映射
SEASON_MAP = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def _generate_us_federal_holidays(start_year: int, end_year: int) -> set[str]:
    """以程序化方式生成美国联邦假日日期（2007-2018）。

    规则基于美国法定假日定义，避免了 ~120 行硬编码。
    返回 ISO 格式日期字符串集合：{"YYYY-MM-DD", ...}
    """
    holidays: set[str] = set()

    for year in range(start_year, end_year + 1):
        # 新年 (1月1日，若为周末则调休至最近工作日)
        d = date(year, 1, 1)
        if d.weekday() == 6:      # 周日 → 周一
            d = date(year, 1, 2)
        elif d.weekday() == 5:    # 周六 → 前一个周五 (上一年 12/31)
            d = date(year - 1, 12, 31)
        holidays.add(d.isoformat())

        # 马丁·路德·金纪念日 (1月第三个周一)
        d = date(year, 1, 1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        d += timedelta(weeks=2)  # 第三个周一
        holidays.add(d.isoformat())

        # 总统日 (2月第三个周一)
        d = date(year, 2, 1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        d += timedelta(weeks=2)
        holidays.add(d.isoformat())

        # 阵亡将士纪念日 (5月最后一个周一)
        d = date(year, 5, 31)
        while d.weekday() != 0:
            d -= timedelta(days=1)
        holidays.add(d.isoformat())

        # 独立日 (7月4日，周末调休)
        d = date(year, 7, 4)
        if d.weekday() == 6:
            d = date(year, 7, 5)
        elif d.weekday() == 5:
            d = date(year, 7, 3)
        holidays.add(d.isoformat())

        # 劳动节 (9月第一个周一)
        d = date(year, 9, 1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        holidays.add(d.isoformat())

        # 哥伦布日 (10月第二个周一)
        d = date(year, 10, 1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        d += timedelta(weeks=1)
        holidays.add(d.isoformat())

        # 退伍军人节 (11月11日，周末调休)
        d = date(year, 11, 11)
        if d.weekday() == 6:
            d = date(year, 11, 12)
        elif d.weekday() == 5:
            d = date(year, 11, 10)
        holidays.add(d.isoformat())

        # 感恩节 (11月第四个周四)
        d = date(year, 11, 1)
        while d.weekday() != 3:
            d += timedelta(days=1)
        d += timedelta(weeks=3)  # 第四个周四
        holidays.add(d.isoformat())

        # 圣诞节 (12月25日，周末调休)
        d = date(year, 12, 25)
        if d.weekday() == 6:
            d = date(year, 12, 26)
        elif d.weekday() == 5:
            d = date(year, 12, 24)
        holidays.add(d.isoformat())

    return holidays


# 模块级缓存：自动生成 2007-2018 年假期（覆盖 LC 数据全时间范围）
US_HOLIDAYS = _generate_us_federal_holidays(2007, 2018)


def build_time_decay_features(
    df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
    decay_lambda: float = 0.001,
) -> pd.DataFrame:
    """构建时间衰减特征：越近期的数据权重越高，公式为 exp(-λ*t) * feature"""
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
    """按日期排序后，为多个数值列同时计算滚动均值、标准差和趋势斜率。"""
    df = df.copy()

    if COL_ISSUE_DATE not in df.columns:
        df[COL_ISSUE_DATE] = pd.to_datetime(df[COL_ISSUE_D], format="%b-%Y", errors="coerce")

    df = df.sort_values(by=COL_ISSUE_DATE).reset_index(drop=True)

    # 选定实际存在的列进行滚动计算
    base_cols = [c for c in ROLLING_BASE_COLS if c in df.columns]
    if not base_cols:
        base_cols = [COL_INSTALLMENT] if COL_INSTALLMENT in df.columns else []

    for col in base_cols:
        series = df[col].fillna(0)
        for window in window_sizes:
            roll = series.rolling(window=window, min_periods=1)
            df[f"rolling_mean_{window}d_{col}"] = roll.mean()
            df[f"rolling_std_{window}d_{col}"] = roll.std().fillna(0)
            df[f"rolling_trend_{window}d_{col}"] = _rolling_trend(series, window)

    logger.info("Built rolling window features for %d cols × %d windows", len(base_cols), len(window_sizes))
    return df


def _rolling_trend(series: pd.Series, window: int) -> pd.Series:
    """向量化计算滚动窗口内的线性回归斜率（O(n) vs 原 O(n·w)）。

    利用简单线性回归斜率公式：
        slope = (n·Σxy - Σx·Σy) / (n·Σx² - (Σx)²)
    当 x = [0, 1, ..., w-1] 固定时，Σx 和 Σx² 是常量。
    Σxy 通过累积和避免逐窗重复计算。
    """
    y = series.values.astype(float)
    n = len(y)
    slopes = np.zeros(n)

    if n < 2 or window < 2:
        return pd.Series(slopes, index=series.index)

    # 固定 x 的预计算值
    w = min(window, n)
    x = np.arange(w, dtype=float)
    sum_x = x.sum()
    sum_x2 = (x * x).sum()

    # 累积和：cumsum_y[i] = Σ_{j=0}^{i-1} y[j]
    cumsum_y = np.concatenate([[0], np.cumsum(y)])
    # 累积和：cumsum_wy[i] = Σ_{j=0}^{i-1} j * y[j] （绝对位置加权）
    y_weighted = y * np.arange(n, dtype=float)
    cumsum_wy = np.concatenate([[0], np.cumsum(y_weighted)])

    for i in range(w - 1, n):
        start = i - w + 1
        sum_y = cumsum_y[i + 1] - cumsum_y[start]
        sum_xy = cumsum_wy[i + 1] - cumsum_wy[start] - start * sum_y
        denominator = w * sum_x2 - sum_x * sum_x
        slopes[i] = (w * sum_xy - sum_x * sum_y) / denominator if denominator > 0 else 0.0

    # 窗口不满的前几行：用可用数据计算
    x_partial: list[tuple[float, float]] = []
    for avail in range(2, w):
        xa = np.arange(avail, dtype=float)
        sx = xa.sum()
        sx2 = (xa * xa).sum()
        denom = avail * sx2 - sx * sx
        x_partial.append((float(avail), sx, sx2, denom))

    for i in range(1, w - 1):
        avail = i + 1
        idx = avail - 2  # map avail=2 → idx=0
        if idx < 0 or idx >= len(x_partial):
            continue
        avail_val, sx, sx2, denom = x_partial[idx]
        if denom == 0:
            continue
        y_slice = y[:i + 1]
        sum_y = y_slice.sum()
        sum_xy = (y_slice * np.arange(avail_val)).sum()
        slopes[i] = (avail_val * sum_xy - sx * sum_y) / denom

    return pd.Series(slopes, index=series.index)


def build_seasonal_holiday_features(df: pd.DataFrame) -> pd.DataFrame:
    """构建季节/节假日因子特征"""
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
    """一键构建所有时序特征"""
    logger.info("Starting temporal feature engineering...")
    df = build_seasonal_holiday_features(df)
    df = build_time_decay_features(df)
    df = build_rolling_window_features(df)
    logger.info("Completed temporal feature engineering")
    return df


def analyze_temporal_features(df: pd.DataFrame) -> None:
    """分析时序特征的统计信息"""
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

    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from common.model_data import find_lending_club_csv, _label_status
    from constant.columns import (
        COL_LOAN_STATUS, LABEL_COL, COL_FICO_AVG, COL_FICO_LOW, COL_FICO_HIGH,
        COL_INT_RATE, COL_LOAN_AMNT, COL_INSTALLMENT, COL_ISSUE_D,
    )

    csv_path = find_lending_club_csv()
    df = pd.read_csv(csv_path, usecols=[
        COL_LOAN_STATUS, COL_INT_RATE, COL_LOAN_AMNT, COL_FICO_LOW, COL_FICO_HIGH,
        COL_INSTALLMENT, COL_ISSUE_D, "annual_inc", "dti",
    ], nrows=50000, low_memory=False)

    df[LABEL_COL] = df[COL_LOAN_STATUS].apply(_label_status)
    df = df.dropna(subset=[LABEL_COL])
    df[COL_FICO_AVG] = (pd.to_numeric(df[COL_FICO_LOW], errors="coerce") +
                        pd.to_numeric(df[COL_FICO_HIGH], errors="coerce")) / 2
    df[COL_INT_RATE] = (df[COL_INT_RATE].astype(str)
                        .str.replace("%", "", regex=False).str.strip()
                        .replace({"": np.nan}).astype(float))
    df[COL_LOAN_AMNT] = pd.to_numeric(df[COL_LOAN_AMNT], errors="coerce")
    df[COL_INSTALLMENT] = pd.to_numeric(df[COL_INSTALLMENT], errors="coerce")
    df["annual_inc"] = pd.to_numeric(df["annual_inc"], errors="coerce")
    df["dti"] = pd.to_numeric(df["dti"], errors="coerce")

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
    # 多列滚动产生的特征也列出
    present = [c for c in temporal_features if c in df.columns]
    print("\nGenerated temporal features:")
    for feat in present:
        print(f"  - {feat}")
    print(f"\nTotal date-derived columns: {len(present)}")
    print(f"DataFrame shape after feature engineering: {df.shape}")
    print(f"Holiday coverage: {df[COL_IS_HOLIDAY].sum()} of {len(df)} rows ({df[COL_IS_HOLIDAY].mean():.1%})")
