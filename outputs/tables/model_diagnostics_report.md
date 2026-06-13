# 模型深度诊断报告

生成时间: 2026-06-11 11:26:13

## 模型对比
| 模型 | AUC |
|---|---|
| Logistic Regression | 0.6783 |
| XGBoost | 0.7060 |
| AUC Difference | 0.0278 |
| DeLong p-value | 0.000000 |

结论：XGBoost 与 LR 的 AUC 差异**statistically significant** (p=0.000000)。

## 诊断清单
| 诊断项 | 输出 |
|---|---|
| 学习曲线 | `outputs/figures/diagnostics_learning_curve.png` |
| 子群体校准 | `outputs/figures/diagnostics_subpopulation_calibration.png` |
| DeLong 检验 | `outputs/figures/diagnostics_delong_test.png` |
| 残差分析 | `outputs/figures/diagnostics_residual_analysis.png` |
