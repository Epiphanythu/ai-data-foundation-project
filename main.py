"""项目分析总入口，按依赖顺序运行数据、建模、解释性、策略和可视化脚本，并生成产物索引。"""

from pathlib import Path
import subprocess
import sys
from datetime import datetime

from constant import paths as P

ROOT = P.PROJECT_ROOT
TABLES = P.TABLES_DIR
FIGURES = P.FIGURES_DIR

SCRIPTS = [
    # ============================================
    # 阶段 1: 数据探索（无依赖，先跑）
    # ============================================
    "analysis/analyze_lending_club.py",
    "analysis/analyze_data_quality.py",
    "analysis/analyze_concept_drift.py",

    # ============================================
    # 阶段 2: 多源数据融合（产出 FRED/ERS/时序/跨源特征）
    # ============================================
    "data/build_fred_macro_features.py",
    "data/build_ers_state_features.py",
    "data/build_temporal_features.py",
    "data/build_cross_source_features.py",

    # ============================================
    # 阶段 3: 分群与宏观关联分析
    # ============================================
    "analysis/build_lc_risk_segments.py",
    "analysis/build_state_control_analysis.py",
    "analysis/build_quarterly_macro_analysis.py",

    # ============================================
    # 阶段 4: 基准模型训练（产出 .joblib + test_predictions.csv）
    # ============================================
    "modeling/train_baseline_model.py",

    # ============================================
    # 阶段 5: 策略模拟（严格依赖 test_predictions.csv）
    # ============================================
    "strategy/run_risk_strategy_simulation.py",

    # ============================================
    # 阶段 6: 可解释性分析
    # ============================================
    "explainability/run_explainability.py",
    "explainability/run_feature_ablation.py",
    "explainability/run_causal_analysis.py",
    "explainability/run_fairness_analysis.py",

    # ============================================
    # 阶段 7: 模型诊断与进阶建模
    # ============================================
    "modeling/run_model_diagnostics.py",
    "modeling/build_scorecard.py",
    "modeling/run_survival_analysis.py",
    "modeling/run_bayesian_modeling.py",

    # ============================================
    # 阶段 8: AutoML 自动调参（独立优化流程，不覆盖基准模型）
    # ============================================
    "modeling/run_automl.py",

    # ============================================
    # 阶段 9: 风控策略与情景分析
    # ============================================
    "strategy/run_dynamic_risk_strategy.py",
    "strategy/run_stress_testing.py",
    "strategy/state_aware_risk/run_state_aware_risk_analysis.py",
    "strategy/run_loan_provisioning.py",
    "strategy/run_portfolio_optimization.py",

    # ============================================
    # 阶段 10: MLOps 模型监控（最后运行，评估全链路）
    # ============================================
    "modeling/run_model_monitoring.py",

    # ============================================
    # 阶段 11: 进阶可视化
    # ============================================
    "visualization/build_advanced_visualizations.py",
]

CORE_OUTPUTS = [
    ("Lending Club 总览", P.LC_OVERVIEW_CSV),
    ("Lending Club 关键发现", P.LC_FINDINGS_MD),
    ("组合风险分层发现", P.LC_SEGMENT_FINDINGS_MD),
    ("FRED 年度宏观融合发现", P.FRED_MACRO_FINDINGS_MD),
    ("FRED 季度宏观融合发现", P.FRED_QUARTERLY_FINDINGS_MD),
    ("ERS 州级经济融合发现", P.ERS_STATE_FINDINGS_MD),
    ("州级控制变量发现", P.LC_STATE_CONTROL_FINDINGS_MD),
    ("跨源特征融合产出", P.CROSS_SOURCE_FEATURES_CSV),
    ("时序特征统计", P.TEMPORAL_FEATURES_STATS_CSV),
    ("时序季节统计", P.TEMPORAL_SEASON_STATS_CSV),
    ("时序节假日统计", P.TEMPORAL_HOLIDAY_STATS_CSV),
    ("数据质量报告", P.DATA_QUALITY_REPORT_MD),
    ("概念漂移报告", P.CONCEPT_DRIFT_REPORT_MD),
    ("特征消融结果", P.FEATURE_ABLATION_CSV),
    ("模型诊断", P.MODEL_DIAGNOSTICS_CSV),
    ("模型诊断报告", P.MODEL_DIAGNOSTICS_REPORT_MD),
    ("因果分析结果", P.CAUSAL_ANALYSIS_RESULTS_CSV),
    ("因果 DID 结果", P.CAUSAL_DID_RESULT_CSV),
    ("因果 IV 结果", P.CAUSAL_IV_RESULT_CSV),
    ("反事实最小改变量", P.COUNTERFACTUAL_MIN_CHANGE_CSV),
    ("策略对比结果", P.STRATEGY_COMPARISON_CSV),
    ("评分卡表", P.SCORECARD_CSV),
    ("IV 特征排名", P.IV_RANKING_CSV),
    ("生存分析 Cox 汇总", P.SURVIVAL_COX_SUMMARY_CSV),
    ("压力测试结果", P.STRESS_TESTING_RESULTS_CSV),
    ("公平性分析报告", P.FAIRNESS_REPORT_CSV),
    ("贝叶斯系数后验", P.BAYESIAN_COEFFICIENTS_CSV),
    ("贝叶斯不确定性标记", P.BAYESIAN_UNCERTAINTY_FLAGS_CSV),
    ("模型监控报告", P.MODEL_MONITORING_REPORT_CSV),
    ("CECL 准备金计提", P.CECL_PROVISIONING_CSV),
    ("组合有效前沿", P.PORTFOLIO_FRONTIER_CSV),
    ("组合最优权重", P.PORTFOLIO_OPTIMAL_WEIGHTS_CSV),
    ("AutoML 模型对比", P.AUTOML_MODEL_COMPARISON_CSV),
    ("AutoML 特征组消融", P.AUTOML_FEATURE_SET_COMPARISON_CSV),
    ("AutoML 业务指标", P.AUTOML_BUSINESS_METRICS_CSV),
    ("AutoML 总结报告", P.AUTOML_SUMMARY_MD),
    ("AutoML 最优参数", P.AUTOML_BEST_PARAMS_JSON),
    ("决策审计报告", P.DECISION_AUDIT_REPORT_MD),
    ("状态感知宏观风险", P.STATE_AWARE_RISK_SUMMARY_CSV),
    ("状态感知模型验证", P.STATE_AWARE_MODEL_VALIDATION_CSV),
    ("状态感知动态阈值策略", P.STATE_AWARE_DYNAMIC_STRATEGY_CSV),
    ("数据处理进度报告", P.PROGRESS_REPORT_MD),
]

KEY_FIGURES = [
    # Lending Club 单变量与组合分析
    P.LC_DEFAULT_RATE_BY_GRADE_PNG,
    P.LC_DEFAULT_RATE_BY_INTEREST_BIN_PNG,
    P.LC_DEFAULT_RATE_BY_FICO_BIN_PNG,
    P.LC_DEFAULT_RATE_TOP_STATES_PNG,
    P.LC_DEFAULT_RATE_BY_PURPOSE_PNG,
    P.LC_TOP_RISK_GRADE_PURPOSE_SEGMENTS_PNG,
    P.LC_FRED_QUARTERLY_OVERLAY_PNG,
    P.LC_STATE_DEFAULT_RESIDUAL_PNG,
    P.CAUSAL_DID_PLOT_PNG,
    P.CAUSAL_MEDIATION_PLOT_PNG,
    P.RISK_STRATEGY_PNG,
    P.STATE_AWARE_DYNAMIC_STRATEGY_PNG,
    # G0/G1 校准与一致性
    P.CALIBRATION_CURVE_PNG,
    P.CROSS_MODEL_SHAP_CONSISTENCY_PNG,
    P.AUTOML_FEATURE_SELECTION_PNG,
    P.AUTOML_TEMPORAL_IMPORTANCE_PNG,
    P.AUTOML_OPT_HISTORY_XGB_PNG,
    P.AUTOML_HYPERPARAM_IMPORTANCE_XGB_PNG,
    # 数据质量与漂移
    P.DATA_QUALITY_IMBALANCE_PNG,
    P.DATA_QUALITY_CORRELATION_PNG,
    P.DATA_QUALITY_DISTRIBUTION_PNG,
    P.CONCEPT_DRIFT_PSI_HEATMAP_PNG,
    P.CONCEPT_DRIFT_FEATURE_SHIFT_PNG,
    P.CONCEPT_DRIFT_DEFAULT_TREND_PNG,
    # 特征消融与模型诊断
    P.FEATURE_ABLATION_BAR_PNG,
    P.FEATURE_ABLATION_WATERFALL_PNG,
    P.DIAGNOSTICS_LEARNING_CURVE_PNG,
    P.DIAGNOSTICS_SUBPOP_CALIBRATION_PNG,
    P.DIAGNOSTICS_DELONG_PNG,
    P.DIAGNOSTICS_RESIDUAL_PNG,
    # G2 评分卡 + 生存分析 + 压力测试
    P.SCORECARD_COMPARISON_PNG,
    P.SURVIVAL_KM_CURVE_PNG,
    P.SURVIVAL_COX_FOREST_PNG,
    P.SURVIVAL_HAZARD_BY_GRADE_PNG,
    P.STRESS_TESTING_IMPACT_PNG,
    P.STRESS_TESTING_WATERFALL_PNG,
    # G3 贝叶斯 + MLOps + 公平性
    P.BAYESIAN_COEFFICIENT_POSTERIOR_PNG,
    P.BAYESIAN_UNCERTAINTY_BAND_PNG,
    P.BAYESIAN_VS_FREQUENTIST_PNG,
    P.MONITORING_RETRAIN_SIMULATION_PNG,
    P.MONITORING_HEALTH_DASHBOARD_PNG,
    P.FAIRNESS_DISPARITY_BAR_PNG,
    P.FAIRNESS_STATE_HEATMAP_PNG,
    # G4 CECL 准备金 + 组合优化
    P.CECL_STAGE_DISTRIBUTION_PNG,
    P.CECL_PROVISION_WATERFALL_PNG,
    P.PORTFOLIO_FRONTIER_PNG,
    P.PORTFOLIO_RISK_RETURN_PNG,
]


def run(script):
    """运行当前模块的主流程或子脚本，并把关键产物写入输出目录。"""
    print(f"\n>>> running {script}")
    result = subprocess.run([sys.executable, script], cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit(f"{script} failed with exit code {result.returncode}")


def file_size(path):
    """把文件大小格式化为易读字符串，用于产物索引。"""
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def generate_index():
    """扫描核心表格和图表，生成一份可汇报、可复现的分析产物索引。"""
    lines = [
        "# 分析产物索引",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 核心发现文档",
        "",
        "| 名称 | 路径 | 大小 |",
        "|---|---|---|",
    ]
    for name, path in CORE_OUTPUTS:
        rel = path.relative_to(ROOT)
        lines.append(f"| {name} | `{rel}` | {file_size(path)} |")

    table_files = sorted(TABLES.glob("*.csv"))
    lines.extend(["", "## CSV 统计表", "", "| 文件 | 大小 |", "|---|---| "])
    for path in table_files:
        lines.append(f"| `{path.relative_to(ROOT)}` | {file_size(path)} |")

    figure_files = sorted(FIGURES.glob("*.png"))
    lines.extend(["", "## 图表", "", "| 文件 | 大小 | 用途 |", "|---|---|---| "])
    key_set = {Path(p).resolve() for p in KEY_FIGURES}
    for path in figure_files:
        rel = path.relative_to(ROOT)
        use = "核心汇报图" if path.resolve() in key_set else "补充分析图"
        lines.append(f"| `{rel}` | {file_size(path)} | {use} |")

    lines.extend(
        [
            "",
            "## 建议汇报主线",
            "",
            "1. 先展示 Lending Club 数据规模、标签过滤和总体违约率。",
            "2. 再展示宏观状态下的违约率差异，说明非平稳环境会改变风险水平。",
            "3. 接着展示模型验证、Top Decile 捕获能力和动态阈值策略收益。",
            "4. 最后展示反事实解释、决策追溯和 LLM 问答，说明系统可解释、可审计、可交互。",
            "",
            "## 一键复现命令",
            "",
            "```bash",
            "python3 main.py",
            "```",
        ]
    )
    out = P.ANALYSIS_INDEX_MD
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {out}")


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    for script in SCRIPTS:
        run(script)
    generate_index()


if __name__ == "__main__":
    main()
