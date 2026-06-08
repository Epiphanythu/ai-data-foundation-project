# data 数据层

`data/` 是项目的数据层，负责保存原始数据、外部数据，并生成可供分析和建模使用的融合特征。

## 职责边界

- 负责：原始数据放置、FRED 宏观特征、ERS 州级特征、时序特征构造。
- 不负责：EDA 结论、风险分层、控制变量分析，这些放在 `analysis/`。
- 不负责：图表美化和展示，这些放在 `visualization/` 和 `dashboard/`。

## 目录结构

```text
data/
├── raw/                         # 手动放置 Lending Club / Home Credit 原始数据
├── external/                    # FRED / ERS 外部数据
├── build_fred_macro_features.py # FRED 年度宏观特征
├── build_ers_state_features.py  # ERS 州级经济特征
├── build_temporal_features.py   # 时序、季节、节假日特征
└── README.md
```

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `build_fred_macro_features.py` | 下载/读取 FRED 月度数据，聚合为年度宏观变量 | `outputs/tables/fred_macro_annual.csv`、`lc_default_by_year_with_fred_macro.csv` |
| `build_ers_state_features.py` | 整理 ERS 州级贫困率、收入、失业率 | `outputs/tables/ers_state_economic_features.csv` |
| `build_temporal_features.py` | 构造滚动窗口、季节、节假日和周末统计 | `outputs/tables/temporal_*_stats.csv` |

## 原始数据放置

```text
data/raw/
├── lending_club/accepted_2007_to_2018Q4.csv
└── home_credit/application_train.csv
```

Kaggle 数据需要手动下载，本项目不自动下载需要登录授权的大文件。
