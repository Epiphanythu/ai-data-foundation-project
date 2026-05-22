# 数据说明

## Kaggle 数据手动下载

Kaggle 数据通常需要账号登录和比赛/数据集授权，因此本项目不自动下载 Kaggle 大文件。请手动下载后放入 `data/raw/`。

### Lending Club

- 数据集：Lending Club Loan Data
- 放置路径：`data/raw/lending_club/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv`
- 典型字段：`loan_status`、`grade`、`int_rate`、`annual_inc`、`addr_state`、`issue_d`

### Home Credit Default Risk

- 数据集：Home Credit Default Risk
- 放置路径：`data/raw/home_credit/`
- 典型字段：`TARGET`、申请人收入、贷款金额、人口统计与历史信贷字段
- 当前状态：数据已下载，分析脚本待创建

## 原始文件放置路径

```text
data/raw/
├── lending_club_accepted.csv      # 可选，手动下载
└── application_train.csv          # 可选，手动下载
```

脚本会扫描 `data/raw/*.csv`，优先处理文件名中包含 `loan`、`accepted` 或 `application` 的文件。

## 处理后数据

- `outputs/tables/`：统计分析表。
- `outputs/figures/`：中期汇报可用图表。
