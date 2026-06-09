"""scripts/build_cross_source_features.py 跨源特征融合引擎

将 FRED 宏观指标 + ERS 州级经济数据联入 Lending Club 贷款记录，
并生成跨源交互特征，捕捉"宏观环境如何调节个体风险"的非线性效应。
"""
from __future__ import annotations

import logging
from csv import DictReader
from pathlib import Path

import numpy as np
import pandas as pd

from constant.columns import (
    COL_ADDR_STATE,
    COL_FICO_AVG,
    COL_INT_RATE,
    COL_ISSUE_YEAR,
    COL_LOAN_AMNT,
    COL_FED_FUNDS_RATE,
    COL_UNEMPLOYMENT_RATE,
    COL_CPI_INFLATION,
    COL_STATE_POVERTY_PCT,
    COL_STATE_UNEMPLOYMENT,
    COL_STATE_MEDIAN_INCOME,
    COL_INTERACT_RATE_FED,
    COL_INTERACT_AMNT_UNEMP,
    COL_INTERACT_FICO_CPI,
)
from constant.paths import EXTERNAL_DIR, TABLES_DIR

logger = logging.getLogger(__name__)

FRED_ANNUAL_CSV = TABLES_DIR / "fred_macro_annual.csv"
ERS_POVERTY_CSV = EXTERNAL_DIR / "ers_poverty_2023.csv"
ERS_UNEMP_INCOME_CSV = EXTERNAL_DIR / "ers_unemployment_income_2000_2023.csv"
OUTPUT_PATH = TABLES_DIR / "cross_source_features.csv"


def _load_fred_annual() -> dict[int, dict]:
    """加载 FRED 宏观年度数据，返回 {issue_year: {fed_funds_rate, unemployment_rate, cpi_inflation}}"""
    fred = {}
    if not FRED_ANNUAL_CSV.exists():
        logger.warning("FRED 宏观数据不存在: %s", FRED_ANNUAL_CSV)
        return fred

    with FRED_ANNUAL_CSV.open(newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            try:
                year = int(float(row["issue_year"]))
            except (ValueError, KeyError):
                continue
            fred[year] = {
                COL_FED_FUNDS_RATE: _safe_float(row.get("avg_fed_funds_rate")),
                COL_UNEMPLOYMENT_RATE: _safe_float(row.get("avg_unemployment_rate")),
                COL_CPI_INFLATION: _safe_float(row.get("cpi_inflation_rate")),
            }
    logger.info("Loaded FRED annual data: %d years", len(fred))
    return fred


def _load_ers_state() -> dict[str, dict]:
    """加载 ERS 州级数据，返回 {state_abbr: {poverty_pct, unemployment_rate, median_income}}"""
    ers = {}

    # 贫困率 (poverty CSV 用 Stabr 列作为州缩写)
    if ERS_POVERTY_CSV.exists():
        with ERS_POVERTY_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
            for row in DictReader(f):
                fips = row.get("FIPS_Code", "").zfill(5)
                if not fips.endswith("000") or fips == "00000":
                    continue
                state = row.get("Stabr", "")
                if not state:
                    continue
                attr = row.get("Attribute", "")
                if attr == "PCTPOVALL_2023":
                    ers.setdefault(state, {})[COL_STATE_POVERTY_PCT] = _safe_float(row.get("Value"))

    # 失业率 + 收入中位数
    if ERS_UNEMP_INCOME_CSV.exists():
        with ERS_UNEMP_INCOME_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
            for row in DictReader(f):
                fips = row.get("FIPS_Code", "").zfill(5)
                if not fips.endswith("000") or fips == "00000":
                    continue
                state = row.get("State", "")
                if not state:
                    continue
                attr = row.get("Attribute", "")
                value = _safe_float(row.get("Value"))
                entry = ers.setdefault(state, {})
                if attr == "Unemployment_rate_2023":
                    entry[COL_STATE_UNEMPLOYMENT] = value
                elif attr == "Median_Household_Income_2022":
                    entry[COL_STATE_MEDIAN_INCOME] = value

    logger.info("Loaded ERS state data: %d states", len(ers))
    return ers


def _safe_float(value) -> float | None:
    if value in (None, "", ".", "nan", "N/A"):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def build_cross_source_features(df: pd.DataFrame) -> pd.DataFrame:
    """在主 DataFrame 上联入 FRED + ERS 特征并生成交互项。

    df 必须包含 issue_year 和 addr_state 列。
    返回在 df 基础上新增了跨源特征列的数据框（不修改原 df）。
    """
    df = df.copy()

    # --- FRED 宏观特征（按年份对齐）---
    fred = _load_fred_annual()
    if fred:
        fred_df = pd.DataFrame.from_dict(fred, orient="index")
        fred_df.index.name = COL_ISSUE_YEAR
        df = df.join(fred_df, on=COL_ISSUE_YEAR, how="left")
    else:
        for col in [COL_FED_FUNDS_RATE, COL_UNEMPLOYMENT_RATE, COL_CPI_INFLATION]:
            df[col] = np.nan

    # --- ERS 州级特征（按州缩写对齐）---
    ers = _load_ers_state()
    if ers:
        ers_df = pd.DataFrame.from_dict(ers, orient="index")
        ers_df.index.name = COL_ADDR_STATE
        df = df.join(ers_df, on=COL_ADDR_STATE, how="left")
    else:
        for col in [COL_STATE_POVERTY_PCT, COL_STATE_UNEMPLOYMENT, COL_STATE_MEDIAN_INCOME]:
            df[col] = np.nan

    # --- 跨源交互特征 ---
    if COL_INT_RATE in df and COL_FED_FUNDS_RATE in df:
        df[COL_INTERACT_RATE_FED] = df[COL_INT_RATE] * df[COL_FED_FUNDS_RATE].fillna(0)
    if COL_LOAN_AMNT in df and COL_STATE_UNEMPLOYMENT in df:
        df[COL_INTERACT_AMNT_UNEMP] = df[COL_LOAN_AMNT] * df[COL_STATE_UNEMPLOYMENT].fillna(0)
    if COL_FICO_AVG in df and COL_CPI_INFLATION in df:
        df[COL_INTERACT_FICO_CPI] = df[COL_FICO_AVG] * df[COL_CPI_INFLATION].fillna(0)

    # 填充跨源特征缺失值为中位数
    cross_source_cols = [
        COL_FED_FUNDS_RATE, COL_UNEMPLOYMENT_RATE, COL_CPI_INFLATION,
        COL_STATE_POVERTY_PCT, COL_STATE_UNEMPLOYMENT, COL_STATE_MEDIAN_INCOME,
        COL_INTERACT_RATE_FED, COL_INTERACT_AMNT_UNEMP, COL_INTERACT_FICO_CPI,
    ]
    for col in cross_source_cols:
        if col in df.columns:
            median_val = df[col].median()
            if pd.notna(median_val):
                df[col] = df[col].fillna(median_val)
            else:
                df[col] = df[col].fillna(0)

    logger.info(
        "Cross-source features built: %d rows, %d new features",
        len(df), len([c for c in cross_source_cols if c in df.columns]),
    )
    return df


def run():
    """独立运行：加载 LC 数据并输出跨源特征 CSV。"""
    from common.model_data import find_lending_club_csv, USE_COLS

    csv_path = find_lending_club_csv()
    logger.info("Loading Lending Club data: %s", csv_path)
    df = pd.read_csv(csv_path, usecols=USE_COLS + [COL_ADDR_STATE], low_memory=False)

    # 解析 issue_d 得到年份
    issue_dt = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce")
    df[COL_ISSUE_YEAR] = issue_dt.dt.year

    # 解析数值
    df[COL_INT_RATE] = (
        df[COL_INT_RATE].astype(str).str.replace("%", "", regex=False)
        .str.strip().replace({"": np.nan, "nan": np.nan}).astype(float)
    )
    df[COL_FICO_AVG] = (df["fico_range_low"].astype(float) + df["fico_range_high"].astype(float)) / 2
    df[COL_LOAN_AMNT] = pd.to_numeric(df[COL_LOAN_AMNT], errors="coerce")

    result = build_cross_source_features(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False)
    logger.info("Cross-source features saved to %s (%d rows x %d cols)", OUTPUT_PATH, len(result), len(result.columns))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
