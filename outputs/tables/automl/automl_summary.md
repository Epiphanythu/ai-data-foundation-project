# AutoML 状态感知建模总结

## 1. 模块定位

本模块不是单纯调参，而是验证不同特征组、模型族和业务阈值在非平稳信贷风险场景下的表现。

## 2. 特征组消融结论

- 最优特征组：`all_state_aware`，AUC = `0.7084`，KS = `0.3017`。
- 相比 `base`，最优特征组 AUC 变化为 `+0.0089`。
- Top Decile 坏账捕获率：`0.2036`。

## 3. 模型族自动选择结论

- 最优模型：`xgboost`，AUC = `0.7083`，PR-AUC = `0.4467`。
- 校准误差 Brier Score = `0.1739`，Top Decile 捕获率 = `0.2019`。

## 4. 业务阈值结论

- 利润最优模型：`xgboost`。
- 利润最优阈值：`0.15`。
- 该阈值下通过率：`0.1925`，坏账率：`0.077`。
- 单笔利润估算：`0.0061`。

## 5. 单模型最优参数

```json
{
  "xgboost": {
    "n_estimators": 400,
    "max_depth": 3,
    "learning_rate": 0.07896186801026692,
    "subsample": 0.6682096494749166,
    "colsample_bytree": 0.6260206371941118,
    "reg_alpha": 5.55172168524472,
    "reg_lambda": 6.732248920775334
  },
  "lightgbm": {
    "n_estimators": 500,
    "num_leaves": 49,
    "learning_rate": 0.013940346079873234,
    "subsample": 0.8736932106048627,
    "colsample_bytree": 0.7760609974958405,
    "reg_alpha": 0.00040755964400728694,
    "reg_lambda": 0.02991469302130215
  },
  "logistic_regression": {
    "C": 0.0019517224641449498
  }
}
```

## 6. CASH 联合搜索结论（真正的 AutoML）

- 搜索 metric：`auc`，best CV score = `0.7136`。
- 自动选中模型族：`logistic_regression`。
- 自动选中预处理：imputer=`mean`，scaler=`robust`，cat_encoder=`ordinal`。
- 自动选中特征工程：`none`。
- 自动选中不平衡处理：`none`。
- 完整 trials 数：`20`，Top-K 配置已落盘到 `cash_best_config.json`。

**自动选中的模型超参：**

```json
{
  "C": 0.061937179416835984
}
```