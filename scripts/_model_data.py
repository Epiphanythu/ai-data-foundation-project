"""scripts/_model_data.py 模型数据共享工具
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
    NUMERIC_FEATURES,
    RANDOM_SEED,
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
) -> pd.DataFrame:
    """build_training_sample 构造模型训练样本（不落盘缓存，避免临时数据堆积）
    1. 读取原始 CSV；
    2. 过滤可用标签；
    3. 衍生字段；
    4. 可选分层抽样。
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
    from .build_temporal_features import build_all_temporal_features
    df = build_all_temporal_features(df)

    # 6. 类别字段空值统一
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].fillna("Unknown").astype(str)

    # 7. 选择需要的列
    keep_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL_COL, COL_ISSUE_YEAR]
    df = df[keep_cols].copy()

    # 8. 可选分层抽样
    if sample_size and len(df) > sample_size:
        target_total = int(sample_size)
        parts: list[pd.DataFrame] = []
        for _, group in df.groupby(LABEL_COL):
            n_take = max(1, int(round(target_total * len(group) / len(df))))
            n_take = min(n_take, len(group))
            parts.append(group.sample(n=n_take, random_state=seed))
        df = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)

    logger.info("Built training data: %d rows, default rate=%.4f", len(df), df[LABEL_COL].mean())
    return df