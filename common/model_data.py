"""common/model_data.py 模型数据共享工具
按用户规则 1：将常用读取/清洗逻辑集中，减少散落判空与重复。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from constant.columns import (
    BAD_STATUSES,
    COL_ADDR_STATE,
    COL_ANNUAL_INC,
    COL_DELINQ_2YRS,
    COL_DTI,
    COL_EMP_LENGTH,
    COL_FICO_AVG,
    COL_FICO_HIGH,
    COL_FICO_LOW,
    COL_GRADE,
    COL_HOME_OWNERSHIP,
    COL_INSTALLMENT,
    COL_INT_RATE,
    COL_ISSUE_D,
    COL_ISSUE_QUARTER,
    COL_ISSUE_YEAR,
    COL_LOAN_AMNT,
    COL_LOAN_STATUS,
    COL_OPEN_ACC,
    COL_PURPOSE,
    COL_REVOL_UTIL,
    COL_TERM,
    COL_TERM_MONTHS,
    COL_VERIFICATION_STATUS,
    GOOD_STATUSES,
    LABEL_COL,
)
from constant.model import (
    CATEGORICAL_FEATURES,
    CROSS_SOURCE_NUMERIC_FEATURES,
    NUMERIC_FEATURES,
    RANDOM_SEED,
    TEST_YEARS,
    TRAIN_SAMPLE_SIZE,
)
from constant.paths import LENDING_CLUB_DIR, RAW_DIR

logger = logging.getLogger(__name__)

# Lending Club CSV 中需要读入的字段（缩小内存占用）
USE_COLS = [
    COL_LOAN_STATUS,
    COL_GRADE,
    COL_INT_RATE,
    COL_LOAN_AMNT,
    COL_TERM,
    COL_ANNUAL_INC,
    COL_DTI,
    COL_FICO_LOW,
    COL_FICO_HIGH,
    COL_PURPOSE,
    COL_HOME_OWNERSHIP,
    COL_VERIFICATION_STATUS,
    COL_EMP_LENGTH,
    COL_ISSUE_D,
    COL_INSTALLMENT,
    COL_REVOL_UTIL,
    COL_OPEN_ACC,
    COL_DELINQ_2YRS,
    COL_ADDR_STATE,  # 州级特征融合需要
]


def find_lending_club_csv() -> Path:
    """find_lending_club_csv 在 data/raw 下定位 Lending Club accepted CSV"""
    for path in sorted(RAW_DIR.rglob("accepted_2007_to_2018Q4.csv")):
        if path.is_file():
            return path
    for path in sorted(RAW_DIR.rglob("*.csv")):
        if path.is_file() and "accepted" in path.name.lower():
            return path
    raise FileNotFoundError(
        f"未找到 Lending Club accepted CSV，请将文件放入 {LENDING_CLUB_DIR}"
    )


def _label_status(status: str) -> Optional[int]:
    """_label_status 将 loan_status 映射为 0/1/None 标签"""
    if status in GOOD_STATUSES:
        return 0
    if status in BAD_STATUSES:
        return 1
    return None


def _percent_to_float(series: pd.Series) -> pd.Series:
    """_percent_to_float 处理含 % 的字符串列"""
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan})
        .astype(float)
    )


def _term_to_months(series: pd.Series) -> pd.Series:
    """_term_to_months 将 ' 36 months' 解析为 36"""
    return (
        series.astype(str)
        .str.extract(r"(\d+)", expand=False)
        .astype(float)
    )


def build_training_sample(
    sample_size: int | None = TRAIN_SAMPLE_SIZE,
    seed: int = RANDOM_SEED,
    enable_macro: bool = True,
    enable_state: bool = True,
) -> pd.DataFrame:
    """build_training_sample 构造模型训练样本（不落盘缓存，避免临时数据堆积）

    参数:
        sample_size: 采样规模，None 表示全量
        seed: 随机种子
        enable_macro: 是否联入 FRED 宏观特征（默认开启）
        enable_state: 是否联入 ERS 州级特征（默认开启）
    """
    # 1. 读取原始 CSV
    csv_path = find_lending_club_csv()
    logger.info("Reading Lending Club CSV: %s", csv_path)
    df = pd.read_csv(csv_path, usecols=USE_COLS, low_memory=False)

    # 2. 标签构造与过滤
    df[LABEL_COL] = df[COL_LOAN_STATUS].map(_label_status)
    df = df.dropna(subset=[LABEL_COL])
    df[LABEL_COL] = df[LABEL_COL].astype(int)

    # 3. 数值字段清洗
    df[COL_INT_RATE] = _percent_to_float(df[COL_INT_RATE])
    df[COL_REVOL_UTIL] = _percent_to_float(df[COL_REVOL_UTIL])
    df[COL_TERM_MONTHS] = _term_to_months(df[COL_TERM])
    df[COL_FICO_AVG] = (df[COL_FICO_LOW].astype(float) + df[COL_FICO_HIGH].astype(float)) / 2

    # 4. 时间衍生字段
    issue_dt = pd.to_datetime(df[COL_ISSUE_D], format="%b-%Y", errors="coerce")
    df[COL_ISSUE_YEAR] = issue_dt.dt.year
    df[COL_ISSUE_QUARTER] = issue_dt.dt.to_period("Q").astype(str)
    df["issue_date"] = issue_dt

    # 5. 添加时序特征（滚动窗口、时间衰减、季节/节假日因子）
    from data.build_temporal_features import build_all_temporal_features
    df = build_all_temporal_features(df)

    # 6. 跨源特征融合（FRED 宏观 + ERS 州级 + 交互项）
    if enable_macro or enable_state:
        from data.build_cross_source_features import build_cross_source_features
        df = build_cross_source_features(df)
        logger.info("Cross-source features merged: %d rows x %d cols", len(df), len(df.columns))

    # 7. 类别字段空值统一
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str)

    # 8. 选择需要的列（基础数值 + 时序 + 跨源 + 类别 + 标签 + 年份）
    keep_cols = NUMERIC_FEATURES + CROSS_SOURCE_NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL_COL, COL_ISSUE_YEAR]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()

    # 9. 可选分层抽样
    if sample_size and len(df) > sample_size:
        target_total = int(sample_size)
        parts: list[pd.DataFrame] = []
        for _, group in df.groupby(LABEL_COL):
            n_take = max(1, int(round(target_total * len(group) / len(df))))
            n_take = min(n_take, len(group))
            parts.append(group.sample(n=n_take, random_state=seed))
        df = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)

    logger.info("Built training data: %d rows, %d features, default rate=%.4f",
                len(df), len(df.columns) - 2, df[LABEL_COL].mean())
    return df


def split_by_time(
    df: pd.DataFrame,
    test_years: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """split_by_time 按时序划分训练/测试集

    将指定年份的贷款作为测试集，其余作为训练集，杜绝未来信息泄漏。

    参数:
        df: 包含 issue_year 列的数据框
        test_years: 测试集年份列表，默认使用 TEST_YEARS
    返回:
        (train_df, test_df)
    """
    if test_years is None:
        test_years = TEST_YEARS

    test_mask = df[COL_ISSUE_YEAR].isin(test_years)
    train_df = df[~test_mask].copy()
    test_df = df[test_mask].copy()

    logger.info(
        "Time split: train=%d (%d-%d), test=%d (%d-%d)",
        len(train_df),
        int(train_df[COL_ISSUE_YEAR].min()) if len(train_df) > 0 else 0,
        int(train_df[COL_ISSUE_YEAR].max()) if len(train_df) > 0 else 0,
        len(test_df),
        int(test_df[COL_ISSUE_YEAR].min()) if len(test_df) > 0 else 0,
        int(test_df[COL_ISSUE_YEAR].max()) if len(test_df) > 0 else 0,
    )
    return train_df, test_df