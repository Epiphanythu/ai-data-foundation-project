"""项目分析总入口，按依赖顺序运行数据、建模、解释性、策略和可视化脚本，并生成产物索引。"""

from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

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
    ("Lending Club 总览", "outputs/tables/lc_overview.csv"),
    ("Lending Club 关键发现", "outputs/tables/lc_findings.md"),
    ("组合风险分层发现", "outputs/tables/lc_segment_findings.md"),
    ("FRED 年度宏观融合发现", "outputs/tables/fred_macro_findings.md"),
    ("FRED 季度宏观融合发现", "outputs/tables/fred_quarterly_findings.md"),
    ("ERS 州级经济融合发现", "outputs/tables/ers_state_findings.md"),
    ("州级控制变量发现", "outputs/tables/lc_state_control_findings.md"),
    ("跨源特征融合产出", "outputs/tables/cross_source_features.csv"),
    ("时序特征统计", "outputs/tables/temporal_features_stats.csv"),
    ("时序季节统计", "outputs/tables/temporal_season_stats.csv"),
    ("时序节假日统计", "outputs/tables/temporal_holiday_stats.csv"),
    ("数据质量报告", "outputs/tables/data_quality_report.md"),
    ("概念漂移报告", "outputs/tables/concept_drift_report.md"),
    ("特征消融结果", "outputs/tables/feature_ablation.csv"),
    ("模型诊断", "outputs/tables/model_diagnostics.csv"),
    ("模型诊断报告", "outputs/tables/model_diagnostics_report.md"),
    ("因果分析结果", "outputs/tables/causal_analysis_results.csv"),
    ("因果 DID 结果", "outputs/tables/causal_did_result.csv"),
    ("因果 IV 结果", "outputs/tables/causal_iv_result.csv"),
    ("反事实最小改变量", "outputs/tables/counterfactual_min_change.csv"),
    ("策略对比结果", "outputs/tables/strategy_comparison.csv"),
    ("评分卡表", "outputs/tables/scorecard.csv"),
    ("IV 特征排名", "outputs/tables/iv_ranking.csv"),
    ("生存分析 Cox 汇总", "outputs/tables/survival_cox_summary.csv"),
    ("压力测试结果", "outputs/tables/stress_testing_results.csv"),
    ("公平性分析报告", "outputs/tables/fairness_report.csv"),
    ("贝叶斯系数后验", "outputs/tables/bayesian_coefficients.csv"),
    ("贝叶斯不确定性标记", "outputs/tables/bayesian_uncertainty_flags.csv"),
    ("模型监控报告", "outputs/tables/model_monitoring_report.csv"),
    ("CECL 准备金计提", "outputs/tables/cecl_provisioning.csv"),
    ("组合有效前沿", "outputs/tables/portfolio_efficient_frontier.csv"),
    ("组合最优权重", "outputs/tables/portfolio_optimal_weights.csv"),
    ("AutoML 模型对比", "outputs/tables/automl/model_comparison.csv"),
    ("AutoML 特征组消融", "outputs/tables/automl/feature_set_comparison.csv"),
    ("AutoML 业务指标", "outputs/tables/automl/business_metrics.csv"),
    ("AutoML 总结报告", "outputs/tables/automl/automl_summary.md"),
    ("AutoML 最优参数", "outputs/tables/automl/best_params.json"),
    ("决策审计报告", "outputs/tables/decision_audit_report.md"),
    ("状态感知宏观风险", "outputs/tables/state_aware_risk_summary.csv"),
    ("状态感知模型验证", "outputs/models/state_aware_model_validation_summary.csv"),
    ("状态感知动态阈值策略", "outputs/models/state_aware_dynamic_threshold_strategy.csv"),
    ("数据处理进度报告", "outputs/tables/progress_report.md"),
]

KEY_FIGURES = [
    "outputs/figures/lc_default_rate_by_grade.png",
    "outputs/figures/lc_default_rate_by_interest_bin.png",
    "outputs/figures/lc_default_rate_by_fico_bin.png",
    "outputs/figures/lc_default_rate_top_states.png",
    "outputs/figures/lc_default_rate_by_purpose.png",
    "outputs/figures/lc_top_risk_grade_purpose_segments.png",
    "outputs/figures/lc_fred_quarterly_overlay.png",
    "outputs/figures/lc_state_default_residual_interest_vs_poverty.png",
    "outputs/figures/causal_did_plot.png",
    "outputs/figures/causal_mediation_plot.png",
    "outputs/figures/risk_strategy.png",
    "outputs/figures/state_aware_dynamic_threshold_strategy.png",
    # G0/G1 新增
    "outputs/figures/calibration_curve.png",
    "outputs/figures/cross_model_shap_consistency.png",
    "outputs/figures/feature_selection_curve.png",
    "outputs/figures/temporal_importance_heatmap.png",
    "outputs/figures/optimization_history_xgboost.png",
    "outputs/figures/hyperparameter_importance_xgboost.png",
    # 数据质量与漂移
    "outputs/figures/data_quality_imbalance_heatmap.png",
    "outputs/figures/data_quality_correlation_heatmap.png",
    "outputs/figures/data_quality_distributions.png",
    "outputs/figures/concept_drift_psi_heatmap.png",
    "outputs/figures/concept_drift_feature_mean_shift.png",
    "outputs/figures/concept_drift_default_trend.png",
    # 特征消融与模型诊断
    "outputs/figures/feature_ablation_bar.png",
    "outputs/figures/feature_ablation_waterfall.png",
    "outputs/figures/diagnostics_learning_curve.png",
    "outputs/figures/diagnostics_subpopulation_calibration.png",
    "outputs/figures/diagnostics_delong_test.png",
    "outputs/figures/diagnostics_residual_analysis.png",
    # G2 评分卡 + 生存分析 + 压力测试
    "outputs/figures/scorecard_comparison.png",
    "outputs/figures/survival_km_curve.png",
    "outputs/figures/survival_cox_forest.png",
    "outputs/figures/survival_hazard_by_grade.png",
    "outputs/figures/stress_testing_impact.png",
    "outputs/figures/stress_testing_waterfall.png",
    # G3 贝叶斯 + MLOps + 公平性
    "outputs/figures/bayesian_coefficient_posterior.png",
    "outputs/figures/bayesian_uncertainty_band.png",
    "outputs/figures/bayesian_vs_frequentist.png",
    "outputs/figures/monitoring_retrain_simulation.png",
    "outputs/figures/monitoring_health_dashboard.png",
    "outputs/figures/fairness_disparity_bar.png",
    "outputs/figures/fairness_state_heatmap.png",
    # G4 CECL 准备金 + 组合优化
    "outputs/figures/cecl_stage_distribution.png",
    "outputs/figures/cecl_provision_waterfall.png",
    "outputs/figures/portfolio_efficient_frontier.png",
    "outputs/figures/portfolio_risk_return_heatmap.png",
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
    for name, rel in CORE_OUTPUTS:
        path = ROOT / rel
        lines.append(f"| {name} | `{rel}` | {file_size(path)} |")

    table_files = sorted(TABLES.glob("*.csv"))
    lines.extend(["", "## CSV 统计表", "", "| 文件 | 大小 |", "|---|---| "])
    for path in table_files:
        lines.append(f"| `{path.relative_to(ROOT)}` | {file_size(path)} |")

    figure_files = sorted(FIGURES.glob("*.png"))
    lines.extend(["", "## 图表", "", "| 文件 | 大小 | 用途 |", "|---|---|---| "])
    key_set = {str(Path(p)) for p in KEY_FIGURES}
    for path in figure_files:
        rel = str(path.relative_to(ROOT))
        use = "核心汇报图" if rel in key_set else "补充分析图"
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
    out = TABLES / "analysis_index.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {out}")


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    for script in SCRIPTS:
        run(script)
    generate_index()


if __name__ == "__main__":
    main()
