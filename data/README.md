# 数据说明

## Kaggle 数据手动下载

Kaggle 数据通常需要账号登录和比赛/数据集授权，因此本项目不自动下载 Kaggle 大文件。请手动下载后放入 `data/raw/`。

### Lending Club

- 数据集：Lending Club Loan Data
- 建议文件名：`lending_club_accepted.csv` 或包含 `loan` / `accepted` 的 CSV 文件名
- 放置路径：`data/raw/lending_club_accepted.csv`
- 典型字段：`loan_status`、`grade`、`int_rate`、`annual_inc`、`addr_state`、`issue_d`

### Home Credit Default Risk

- 数据集：Home Credit Default Risk
- 建议文件名：`application_train.csv`
- 放置路径：`data/raw/application_train.csv`
- 典型字段：`TARGET`、申请人收入、贷款金额、人口统计与历史信贷字段

## 原始文件放置路径

```text
data/raw/
├── lending_club_accepted.csv      # 可选，手动下载
└── application_train.csv          # 可选，手动下载
```

脚本会扫描 `data/raw/*.csv`，优先处理文件名中包含 `loan`、`accepted` 或 `application` 的文件。

## 外部宏观/区域样例数据

中期演示脚本会自动生成三个小型样例表：

- `data/sample/sample_loans.csv`：样例贷款记录
- `data/sample/sample_region.csv`：样例州级区域经济指标
- `data/sample/sample_macro.csv`：样例年度宏观金融指标

这些样例用于证明多源数据融合与可视化流程可运行。最终阶段应替换为真实 ACS 和 Fed 数据。

## 处理后数据

- `data/processed/sample_integrated_credit_risk.csv`：样例贷款、区域经济、宏观金融融合后的数据。
- `outputs/tables/`：统计分析表。
- `outputs/figures/`：中期汇报可用图表。
