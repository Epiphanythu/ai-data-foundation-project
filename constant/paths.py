"""paths.py 项目路径常量统一管理"""
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EXTERNAL_DIR = DATA_DIR / "external"

# Lending Club 原始数据
LENDING_CLUB_DIR = RAW_DIR / "lending_club"
LENDING_CLUB_CSV_NAME = "accepted_2007_to_2018Q4.csv"

# 输出目录
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
MODELS_DIR = OUTPUTS_DIR / "models"
REPORTS_DIR = OUTPUTS_DIR / "reports"

# 模型相关产物
MODEL_METRICS_CSV = MODELS_DIR / "model_metrics.csv"
MODEL_FEATURE_IMPORTANCE_CSV = MODELS_DIR / "feature_importance.csv"
MODEL_LR_PATH = MODELS_DIR / "logistic_regression.joblib"
MODEL_XGB_PATH = MODELS_DIR / "xgboost_model.joblib"
MODEL_PIPELINE_PATH = MODELS_DIR / "preprocess_pipeline.joblib"
MODEL_TEST_PREDICTIONS_CSV = MODELS_DIR / "test_predictions.csv"

# SHAP/策略产物
SHAP_VALUES_NPZ = MODELS_DIR / "shap_values.npz"
SHAP_SUMMARY_PNG = FIGURES_DIR / "shap_summary.png"
SHAP_BAR_PNG = FIGURES_DIR / "shap_bar.png"
PDP_DIR = FIGURES_DIR / "pdp"
RISK_STRATEGY_CSV = MODELS_DIR / "risk_strategy.csv"
RISK_STRATEGY_PNG = FIGURES_DIR / "risk_strategy.png"

# 进阶可视化产物
ADVANCED_FIGURES_DIR = FIGURES_DIR / "advanced"
ADV_STATE_CHOROPLETH_PNG = ADVANCED_FIGURES_DIR / "state_choropleth.png"
ADV_GRADE_PURPOSE_HEATMAP_PNG = ADVANCED_FIGURES_DIR / "heatmap_grade_purpose.png"
ADV_FICO_INTEREST_HEATMAP_PNG = ADVANCED_FIGURES_DIR / "heatmap_fico_interest.png"
ADV_ROC_PNG = ADVANCED_FIGURES_DIR / "roc_curves.png"
ADV_PR_PNG = ADVANCED_FIGURES_DIR / "pr_curves.png"
ADV_KS_PNG = ADVANCED_FIGURES_DIR / "ks_curves.png"
ADV_CALIBRATION_PNG = ADVANCED_FIGURES_DIR / "calibration_curves.png"
ADV_LIFT_GAIN_PNG = ADVANCED_FIGURES_DIR / "lift_gain.png"
ADV_CONFUSION_MATRIX_PNG = ADVANCED_FIGURES_DIR / "confusion_matrix.png"
ADV_GRADE_RADAR_PNG = ADVANCED_FIGURES_DIR / "grade_radar.png"
ADV_SHAP_BEESWARM_PNG = ADVANCED_FIGURES_DIR / "shap_beeswarm.png"
ADV_SHAP_INTERACTION_PNG = ADVANCED_FIGURES_DIR / "shap_interaction_fico_intrate.png"
ADV_SHAP_HEATMAP_PNG = ADVANCED_FIGURES_DIR / "shap_heatmap.png"

# LLM 报告
LLM_AUTO_REPORT_MD = REPORTS_DIR / "llm_auto_report.md"
LLM_CHARTS_DIR = FIGURES_DIR / "llm_charts"
