# modeling 建模模块

`modeling/` 负责训练个人贷款违约预测模型，并输出可复现的模型文件、预测结果和评价指标。

## 入口脚本

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `train_baseline_model.py` | 训练 Logistic Regression 和 XGBoost 基准模型 | `outputs/models/xgb.joblib`、`model_metrics.csv`、`test_predictions.csv` |

## 输入依赖

- Lending Club 原始贷款数据：`data/raw/`
- 共享建模样本构造：`common/model_data.py`
- 可选时序特征：`data/build_temporal_features.py`

## 输出用途

- `explainability/` 使用模型做 SHAP、PDP、因果和反事实解释。
- `strategy/` 使用预测概率做阈值扫描和动态策略。
- `dashboard/` 展示模型指标和预测结果。
- `llm/` 查询模型结论和指标。
