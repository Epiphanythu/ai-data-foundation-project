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

# 状态感知动态风控产物
STATE_AWARE_MACRO_FEATURES_CSV = TABLES_DIR / "state_aware_macro_features.csv"
STATE_AWARE_RISK_SUMMARY_CSV = TABLES_DIR / "state_aware_risk_summary.csv"
STATE_AWARE_MODEL_VALIDATION_CSV = MODELS_DIR / "state_aware_model_validation_summary.csv"
STATE_AWARE_DYNAMIC_STRATEGY_CSV = MODELS_DIR / "state_aware_dynamic_threshold_strategy.csv"
STATE_AWARE_DYNAMIC_STRATEGY_PNG = FIGURES_DIR / "state_aware_dynamic_threshold_strategy.png"

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

# LLM 产物
LLM_CHARTS_DIR = FIGURES_DIR / "llm_charts"
LLM_RAG_INDEX_DIR = OUTPUTS_DIR / "llm_rag_index"
LLM_RAG_INDEX_NPZ = LLM_RAG_INDEX_DIR / "tfidf_index.npz"
LLM_RAG_DOCS_JSON = LLM_RAG_INDEX_DIR / "docs.json"
DECISION_LOGS_JSON = TABLES_DIR / "decision_logs.json"
COUNTERFACTUAL_MIN_CHANGE_CSV = TABLES_DIR / "counterfactual_min_change.csv"

# AutoML 产物
AUTOML_DIR = TABLES_DIR / "automl"
AUTOML_FEATURE_SET_COMPARISON_CSV = AUTOML_DIR / "feature_set_comparison.csv"
AUTOML_BUSINESS_METRICS_CSV = AUTOML_DIR / "business_metrics.csv"
AUTOML_MODEL_COMPARISON_CSV = AUTOML_DIR / "model_comparison.csv"
AUTOML_BEST_PARAMS_JSON = AUTOML_DIR / "best_params.json"
AUTOML_SUMMARY_MD = AUTOML_DIR / "automl_summary.md"
AUTOML_FEATURE_SELECTION_PNG = FIGURES_DIR / "feature_selection_curve.png"
AUTOML_TEMPORAL_IMPORTANCE_PNG = FIGURES_DIR / "temporal_importance_heatmap.png"
AUTOML_OPT_HISTORY_XGB_PNG = FIGURES_DIR / "optimization_history_xgboost.png"
AUTOML_HYPERPARAM_IMPORTANCE_XGB_PNG = FIGURES_DIR / "hyperparameter_importance_xgboost.png"

# 数据质量与概念漂移
DATA_QUALITY_REPORT_MD = TABLES_DIR / "data_quality_report.md"
DATA_QUALITY_MISSING_CSV = TABLES_DIR / "data_quality_missing_rate.csv"
DATA_QUALITY_OUTLIER_CSV = TABLES_DIR / "data_quality_outliers.csv"
DATA_QUALITY_IMBALANCE_PNG = FIGURES_DIR / "data_quality_imbalance_heatmap.png"
DATA_QUALITY_CORRELATION_PNG = FIGURES_DIR / "data_quality_correlation_heatmap.png"
DATA_QUALITY_DISTRIBUTION_PNG = FIGURES_DIR / "data_quality_distributions.png"
CONCEPT_DRIFT_REPORT_MD = TABLES_DIR / "concept_drift_report.md"
CONCEPT_DRIFT_PSI_CSV = TABLES_DIR / "concept_drift_psi.csv"
CONCEPT_DRIFT_PSI_HEATMAP_PNG = FIGURES_DIR / "concept_drift_psi_heatmap.png"
CONCEPT_DRIFT_FEATURE_SHIFT_PNG = FIGURES_DIR / "concept_drift_feature_mean_shift.png"
CONCEPT_DRIFT_DEFAULT_TREND_PNG = FIGURES_DIR / "concept_drift_default_trend.png"

# 模型诊断与特征消融
MODEL_DIAGNOSTICS_CSV = TABLES_DIR / "model_diagnostics.csv"
MODEL_DIAGNOSTICS_REPORT_MD = TABLES_DIR / "model_diagnostics_report.md"
DIAGNOSTICS_LEARNING_CURVE_PNG = FIGURES_DIR / "diagnostics_learning_curve.png"
DIAGNOSTICS_SUBPOP_CALIBRATION_PNG = FIGURES_DIR / "diagnostics_subpopulation_calibration.png"
DIAGNOSTICS_DELONG_PNG = FIGURES_DIR / "diagnostics_delong_test.png"
DIAGNOSTICS_RESIDUAL_PNG = FIGURES_DIR / "diagnostics_residual_analysis.png"
FEATURE_ABLATION_CSV = TABLES_DIR / "feature_ablation.csv"
FEATURE_ABLATION_BAR_PNG = FIGURES_DIR / "feature_ablation_bar.png"
FEATURE_ABLATION_WATERFALL_PNG = FIGURES_DIR / "feature_ablation_waterfall.png"

# 公平性、压力测试、组合优化、CECL
FAIRNESS_REPORT_CSV = TABLES_DIR / "fairness_report.csv"
FAIRNESS_DISPARITY_BAR_PNG = FIGURES_DIR / "fairness_disparity_bar.png"
FAIRNESS_STATE_HEATMAP_PNG = FIGURES_DIR / "fairness_state_heatmap.png"
STRESS_TESTING_RESULTS_CSV = TABLES_DIR / "stress_testing_results.csv"
STRESS_TESTING_IMPACT_PNG = FIGURES_DIR / "stress_testing_impact.png"
STRESS_TESTING_WATERFALL_PNG = FIGURES_DIR / "stress_testing_waterfall.png"
PORTFOLIO_FRONTIER_CSV = TABLES_DIR / "portfolio_efficient_frontier.csv"
PORTFOLIO_OPTIMAL_WEIGHTS_CSV = TABLES_DIR / "portfolio_optimal_weights.csv"
PORTFOLIO_FRONTIER_PNG = FIGURES_DIR / "portfolio_efficient_frontier.png"
PORTFOLIO_RISK_RETURN_PNG = FIGURES_DIR / "portfolio_risk_return_heatmap.png"
CECL_PROVISIONING_CSV = TABLES_DIR / "cecl_provisioning.csv"
CECL_STAGE_DISTRIBUTION_PNG = FIGURES_DIR / "cecl_stage_distribution.png"
CECL_PROVISION_WATERFALL_PNG = FIGURES_DIR / "cecl_provision_waterfall.png"

# Lending Club 分析产物
LC_OVERVIEW_CSV = TABLES_DIR / "lc_overview.csv"
LC_FINDINGS_MD = TABLES_DIR / "lc_findings.md"
LC_SEGMENT_FINDINGS_MD = TABLES_DIR / "lc_segment_findings.md"
LC_STATE_CONTROL_FINDINGS_MD = TABLES_DIR / "lc_state_control_findings.md"

# 多源数据融合产出
FRED_MACRO_FINDINGS_MD = TABLES_DIR / "fred_macro_findings.md"
FRED_QUARTERLY_FINDINGS_MD = TABLES_DIR / "fred_quarterly_findings.md"
ERS_STATE_FINDINGS_MD = TABLES_DIR / "ers_state_findings.md"
CROSS_SOURCE_FEATURES_CSV = TABLES_DIR / "cross_source_features.csv"
TEMPORAL_FEATURES_STATS_CSV = TABLES_DIR / "temporal_features_stats.csv"
TEMPORAL_SEASON_STATS_CSV = TABLES_DIR / "temporal_season_stats.csv"
TEMPORAL_HOLIDAY_STATS_CSV = TABLES_DIR / "temporal_holiday_stats.csv"

# 因果分析产物
CAUSAL_ANALYSIS_RESULTS_CSV = TABLES_DIR / "causal_analysis_results.csv"
CAUSAL_DID_RESULT_CSV = TABLES_DIR / "causal_did_result.csv"
CAUSAL_IV_RESULT_CSV = TABLES_DIR / "causal_iv_result.csv"
CAUSAL_DID_PLOT_PNG = FIGURES_DIR / "causal_did_plot.png"
CAUSAL_MEDIATION_PLOT_PNG = FIGURES_DIR / "causal_mediation_plot.png"

# 策略对比与评分卡
STRATEGY_COMPARISON_CSV = TABLES_DIR / "strategy_comparison.csv"
SCORECARD_CSV = TABLES_DIR / "scorecard.csv"
SCORECARD_COMPARISON_PNG = FIGURES_DIR / "scorecard_comparison.png"
IV_RANKING_CSV = TABLES_DIR / "iv_ranking.csv"

# 生存分析产物
SURVIVAL_COX_SUMMARY_CSV = TABLES_DIR / "survival_cox_summary.csv"
SURVIVAL_KM_CURVE_PNG = FIGURES_DIR / "survival_km_curve.png"
SURVIVAL_COX_FOREST_PNG = FIGURES_DIR / "survival_cox_forest.png"
SURVIVAL_HAZARD_BY_GRADE_PNG = FIGURES_DIR / "survival_hazard_by_grade.png"

# 贝叶斯建模产物
BAYESIAN_COEFFICIENTS_CSV = TABLES_DIR / "bayesian_coefficients.csv"
BAYESIAN_UNCERTAINTY_FLAGS_CSV = TABLES_DIR / "bayesian_uncertainty_flags.csv"
BAYESIAN_COEFFICIENT_POSTERIOR_PNG = FIGURES_DIR / "bayesian_coefficient_posterior.png"
BAYESIAN_UNCERTAINTY_BAND_PNG = FIGURES_DIR / "bayesian_uncertainty_band.png"
BAYESIAN_VS_FREQUENTIST_PNG = FIGURES_DIR / "bayesian_vs_frequentist.png"

# MLOps 监控产物
MODEL_MONITORING_REPORT_CSV = TABLES_DIR / "model_monitoring_report.csv"
MONITORING_RETRAIN_SIMULATION_PNG = FIGURES_DIR / "monitoring_retrain_simulation.png"
MONITORING_HEALTH_DASHBOARD_PNG = FIGURES_DIR / "monitoring_health_dashboard.png"

# 决策审计与进度报告
DECISION_AUDIT_REPORT_MD = TABLES_DIR / "decision_audit_report.md"
PROGRESS_REPORT_MD = TABLES_DIR / "progress_report.md"
ANALYSIS_INDEX_MD = TABLES_DIR / "analysis_index.md"

# Lending Club 关键图表
LC_DEFAULT_RATE_BY_GRADE_PNG = FIGURES_DIR / "lc_default_rate_by_grade.png"
LC_DEFAULT_RATE_BY_INTEREST_BIN_PNG = FIGURES_DIR / "lc_default_rate_by_interest_bin.png"
LC_DEFAULT_RATE_BY_FICO_BIN_PNG = FIGURES_DIR / "lc_default_rate_by_fico_bin.png"
LC_DEFAULT_RATE_TOP_STATES_PNG = FIGURES_DIR / "lc_default_rate_top_states.png"
LC_DEFAULT_RATE_BY_PURPOSE_PNG = FIGURES_DIR / "lc_default_rate_by_purpose.png"
LC_TOP_RISK_GRADE_PURPOSE_SEGMENTS_PNG = FIGURES_DIR / "lc_top_risk_grade_purpose_segments.png"
LC_FRED_QUARTERLY_OVERLAY_PNG = FIGURES_DIR / "lc_fred_quarterly_overlay.png"
LC_STATE_DEFAULT_RESIDUAL_PNG = FIGURES_DIR / "lc_state_default_residual_interest_vs_poverty.png"

# 校准与跨模型一致性
CALIBRATION_CURVE_PNG = FIGURES_DIR / "calibration_curve.png"
CROSS_MODEL_SHAP_CONSISTENCY_PNG = FIGURES_DIR / "cross_model_shap_consistency.png"
