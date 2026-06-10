"""dashboard/app.py 核心 Streamlit Dashboard
启动方式：
    streamlit run dashboard/app.py

8 个核心 Tab：
1. 数据概览（含数据质量与概念漂移）
2. 模型表现（基准对比 + 模型诊断 + 状态感知验证）
3. AutoML（特征组消融、模型族对比、利润最优阈值）
4. 可解释性（SHAP/PDP + 公平性）
5. 风控策略（阈值、状态感知、压力测试、组合优化、CECL）
6. 决策追溯（反事实 + 审计链路）
7. AI 助手（自然语言问答 + 自动出图）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import LLM_QA_PRESET_QUESTIONS  # noqa: E402
from constant.paths import (  # noqa: E402
    ADV_CALIBRATION_PNG,
    ADV_CONFUSION_MATRIX_PNG,
    ADV_FICO_INTEREST_HEATMAP_PNG,
    ADV_GRADE_PURPOSE_HEATMAP_PNG,
    ADV_GRADE_RADAR_PNG,
    ADV_KS_PNG,
    ADV_LIFT_GAIN_PNG,
    ADV_PR_PNG,
    ADV_ROC_PNG,
    ADV_SHAP_BEESWARM_PNG,
    ADV_SHAP_HEATMAP_PNG,
    ADV_SHAP_INTERACTION_PNG,
    ADV_STATE_CHOROPLETH_PNG,
    AUTOML_BEST_PARAMS_JSON,
    AUTOML_BUSINESS_METRICS_CSV,
    AUTOML_FEATURE_SELECTION_PNG,
    AUTOML_FEATURE_SET_COMPARISON_CSV,
    AUTOML_HYPERPARAM_IMPORTANCE_XGB_PNG,
    AUTOML_MODEL_COMPARISON_CSV,
    AUTOML_OPT_HISTORY_XGB_PNG,
    AUTOML_SUMMARY_MD,
    AUTOML_TEMPORAL_IMPORTANCE_PNG,
    CECL_PROVISIONING_CSV,
    CECL_PROVISION_WATERFALL_PNG,
    CECL_STAGE_DISTRIBUTION_PNG,
    CONCEPT_DRIFT_DEFAULT_TREND_PNG,
    CONCEPT_DRIFT_FEATURE_SHIFT_PNG,
    CONCEPT_DRIFT_PSI_CSV,
    CONCEPT_DRIFT_PSI_HEATMAP_PNG,
    CONCEPT_DRIFT_REPORT_MD,
    DATA_QUALITY_CORRELATION_PNG,
    DATA_QUALITY_DISTRIBUTION_PNG,
    DATA_QUALITY_IMBALANCE_PNG,
    DATA_QUALITY_MISSING_CSV,
    DATA_QUALITY_REPORT_MD,
    DIAGNOSTICS_DELONG_PNG,
    DIAGNOSTICS_LEARNING_CURVE_PNG,
    DIAGNOSTICS_RESIDUAL_PNG,
    DIAGNOSTICS_SUBPOP_CALIBRATION_PNG,
    FAIRNESS_DISPARITY_BAR_PNG,
    FAIRNESS_REPORT_CSV,
    FAIRNESS_STATE_HEATMAP_PNG,
    FEATURE_ABLATION_BAR_PNG,
    FEATURE_ABLATION_CSV,
    FEATURE_ABLATION_WATERFALL_PNG,
    FIGURES_DIR,
    MODEL_DIAGNOSTICS_CSV,
    MODEL_DIAGNOSTICS_REPORT_MD,
    MODEL_FEATURE_IMPORTANCE_CSV,
    MODEL_METRICS_CSV,
    PORTFOLIO_FRONTIER_CSV,
    PORTFOLIO_FRONTIER_PNG,
    PORTFOLIO_OPTIMAL_WEIGHTS_CSV,
    PORTFOLIO_RISK_RETURN_PNG,
    RISK_STRATEGY_CSV,
    RISK_STRATEGY_PNG,
    SHAP_BAR_PNG,
    SHAP_SUMMARY_PNG,
    STATE_AWARE_DYNAMIC_STRATEGY_CSV,
    STATE_AWARE_DYNAMIC_STRATEGY_PNG,
    STATE_AWARE_MODEL_VALIDATION_CSV,
    STATE_AWARE_RISK_SUMMARY_CSV,
    STRESS_TESTING_IMPACT_PNG,
    STRESS_TESTING_RESULTS_CSV,
    STRESS_TESTING_WATERFALL_PNG,
    TABLES_DIR,
)

st.set_page_config(page_title="贷款违约风险 Dashboard", layout="wide")


# ----------------------- 公共工具 -----------------------
@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame | None:
    """load_csv 带缓存的 CSV 读取"""
    if not path.exists():
        return None
    return pd.read_csv(path)


def show_image_or_warn(path: Path, caption: str = ""):
    """show_image_or_warn 存在则显示图片，否则提示"""
    if path.exists():
        st.image(str(path), caption=caption, width="stretch")
    else:
        st.info(f"暂无：{path.name}（请先运行对应脚本）")


@st.cache_data(show_spinner=False)
def load_decision_logs(path: Path) -> list[dict]:
    """load_decision_logs 读取决策追溯日志"""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def render_metric_card(label: str, value: str, help_text: str = "") -> None:
    """render_metric_card 渲染统一口径的 Dashboard 指标卡片"""
    st.metric(label, value, help=help_text or None)


# ----------------------- 标题 -----------------------
st.title("📊 多源数据 · 个人贷款违约风险 Dashboard")
st.caption("Lending Club + FRED 宏观 + ERS 州级经济 · 模型对比 · 可解释性 · 风控策略 · AI 助手")

tab_overview, tab_model, tab_automl, tab_explain, tab_strategy, tab_trace, tab_ai = st.tabs(
    [
        "数据概览",
        "模型表现",
        "AutoML",
        "可解释性",
        "风控策略",
        "决策追溯",
        "AI 助手",
    ]
)


# ----------------------- Tab 1：数据概览 -----------------------
with tab_overview:
    st.subheader("数据规模与标签分布")
    overview = load_csv(TABLES_DIR / "lc_overview.csv")
    if overview is not None:
        cols = st.columns(len(overview))
        for col, (_, row) in zip(cols, overview.iterrows()):
            col.metric(label=str(row["metric"]), value=str(row["value"]))
    else:
        st.warning("缺失 lc_overview.csv，请先运行 analysis/analyze_lending_club.py")

    # 1. 进阶图：美国州级 Choropleth 违约率
    st.markdown("### 美国各州违约率地图")
    show_image_or_warn(ADV_STATE_CHOROPLETH_PNG, "Choropleth：颜色越深风险越高")

    # 2. 进阶图：风险二维矩阵热力图
    st.markdown("### 风险二维矩阵（热力图）")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(ADV_GRADE_PURPOSE_HEATMAP_PNG, "Grade × Purpose")
    with c2:
        show_image_or_warn(ADV_FICO_INTEREST_HEATMAP_PNG, "FICO × 利率")

    # 3. 进阶图：借款人画像雷达
    st.markdown("### 借款人画像雷达图（Grade A-G）")
    show_image_or_warn(ADV_GRADE_RADAR_PNG, "多维标准化对比")

    # 4. 单变量违约率（基础参考）
    with st.expander("基础单变量违约率图"):
        c1, c2 = st.columns(2)
        with c1:
            show_image_or_warn(FIGURES_DIR / "lc_default_rate_by_grade.png", "按等级")
            show_image_or_warn(FIGURES_DIR / "lc_default_rate_by_fico_bin.png", "按 FICO 分箱")
        with c2:
            show_image_or_warn(FIGURES_DIR / "lc_default_rate_by_interest_bin.png", "按利率分箱")
            show_image_or_warn(FIGURES_DIR / "lc_default_rate_by_purpose.png", "按贷款用途")

    st.markdown("### 多源融合：FRED 季度宏观叠加")
    show_image_or_warn(FIGURES_DIR / "lc_fred_quarterly_overlay.png", "Lending Club 季度违约率 vs FRED")

    # 5. 数据质量诊断
    st.markdown("### 数据质量诊断")
    if DATA_QUALITY_REPORT_MD.exists():
        with st.expander("查看数据质量报告"):
            st.markdown(DATA_QUALITY_REPORT_MD.read_text(encoding="utf-8"))
    quality_missing = load_csv(DATA_QUALITY_MISSING_CSV)
    if quality_missing is not None:
        st.markdown("#### 缺失率 Top 字段")
        st.dataframe(quality_missing.head(15), width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(DATA_QUALITY_IMBALANCE_PNG, "标签 × 关键维度不平衡热力图")
        show_image_or_warn(DATA_QUALITY_DISTRIBUTION_PNG, "数值特征分布")
    with c2:
        show_image_or_warn(DATA_QUALITY_CORRELATION_PNG, "数值特征相关性矩阵")

    # 6. 概念漂移
    st.markdown("### 概念漂移（PSI + 分布偏移）")
    if CONCEPT_DRIFT_REPORT_MD.exists():
        with st.expander("查看概念漂移报告"):
            st.markdown(CONCEPT_DRIFT_REPORT_MD.read_text(encoding="utf-8"))
    drift_psi = load_csv(CONCEPT_DRIFT_PSI_CSV)
    if drift_psi is not None:
        st.markdown("#### 关键特征 PSI 表")
        st.dataframe(drift_psi, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(CONCEPT_DRIFT_PSI_HEATMAP_PNG, "PSI 热力图（按年份）")
        show_image_or_warn(CONCEPT_DRIFT_DEFAULT_TREND_PNG, "违约率时序趋势")
    with c2:
        show_image_or_warn(CONCEPT_DRIFT_FEATURE_SHIFT_PNG, "特征均值年度偏移")


# ----------------------- Tab 2：模型表现 -----------------------
with tab_model:
    st.subheader("基准模型对比")
    metrics = load_csv(MODEL_METRICS_CSV)
    if metrics is not None:
        st.dataframe(metrics, width="stretch")
    else:
        st.warning("缺失 model_metrics.csv，请先运行 `python modeling/train_baseline_model.py`")

    # 1. 行业级模型评估图：ROC / PR / KS / Calibration
    st.markdown("### 模型评估曲线")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(ADV_ROC_PNG, "ROC 曲线（含 AUC）")
        show_image_or_warn(ADV_KS_PNG, "KS 曲线")
    with c2:
        show_image_or_warn(ADV_PR_PNG, "Precision-Recall 曲线")
        show_image_or_warn(ADV_CALIBRATION_PNG, "Calibration 校准曲线")

    # 2. Lift / Gain + 混淆矩阵
    st.markdown("### Lift / Gain & 混淆矩阵")
    show_image_or_warn(ADV_LIFT_GAIN_PNG, "Gain Chart + Lift Chart")
    show_image_or_warn(ADV_CONFUSION_MATRIX_PNG, "阈值=0.30 时混淆矩阵")

    st.markdown("### 特征重要性（Top 20）")
    importance = load_csv(MODEL_FEATURE_IMPORTANCE_CSV)
    if importance is not None:
        model_options = importance["model"].unique().tolist()
        chosen = st.selectbox("选择模型", model_options)
        view = importance[importance["model"] == chosen].head(20)
        st.bar_chart(view.set_index("feature")["importance"])
    else:
        st.info("尚未生成特征重要性")

    st.markdown("### 状态感知模型验证")
    state_aware_validation = load_csv(STATE_AWARE_MODEL_VALIDATION_CSV)
    if state_aware_validation is not None:
        st.dataframe(state_aware_validation, width="stretch")
        if {"model", "top_decile_bad_capture"}.issubset(state_aware_validation.columns):
            st.bar_chart(state_aware_validation.set_index("model")["top_decile_bad_capture"])
    else:
        st.info("尚未生成 状态感知模型验证，请运行 `python strategy/state_aware_risk/run_state_aware_risk_analysis.py`")

    # 模型诊断（学习曲线 / 子群体校准 / DeLong / 残差）
    st.markdown("### 模型深度诊断")
    diagnostics = load_csv(MODEL_DIAGNOSTICS_CSV)
    if diagnostics is not None:
        st.dataframe(diagnostics, width="stretch")
    if MODEL_DIAGNOSTICS_REPORT_MD.exists():
        with st.expander("查看模型诊断报告"):
            st.markdown(MODEL_DIAGNOSTICS_REPORT_MD.read_text(encoding="utf-8"))
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(DIAGNOSTICS_LEARNING_CURVE_PNG, "学习曲线：训练规模 vs AUC")
        show_image_or_warn(DIAGNOSTICS_DELONG_PNG, "DeLong 检验：模型 AUC 差异显著性")
    with c2:
        show_image_or_warn(DIAGNOSTICS_SUBPOP_CALIBRATION_PNG, "子群体校准曲线")
        show_image_or_warn(DIAGNOSTICS_RESIDUAL_PNG, "预测残差按特征分箱")

    # 特征消融
    st.markdown("### 特征消融（Cross-source 增益）")
    ablation = load_csv(FEATURE_ABLATION_CSV)
    if ablation is not None:
        st.dataframe(ablation, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(FEATURE_ABLATION_BAR_PNG, "特征消融柱状图")
    with c2:
        show_image_or_warn(FEATURE_ABLATION_WATERFALL_PNG, "Waterfall 增益分解")


# ----------------------- Tab 3：AutoML -----------------------
with tab_automl:
    st.subheader("AutoML 状态感知建模验证")
    st.caption("特征组消融 + 模型族对比 + Optuna 自动调参 + 业务指标（PR-AUC / Brier / Top Decile / 利润最优阈值）。")

    if AUTOML_SUMMARY_MD.exists():
        with st.expander("查看 AutoML 自动总结报告", expanded=True):
            st.markdown(AUTOML_SUMMARY_MD.read_text(encoding="utf-8"))
    else:
        st.info("尚未生成 AutoML 总结，请运行 `python modeling/run_automl.py`")

    # 1. 特征组消融
    st.markdown("### 特征组消融（Base / Temporal / Macro / Region / All）")
    feature_set = load_csv(AUTOML_FEATURE_SET_COMPARISON_CSV)
    if feature_set is not None:
        st.dataframe(feature_set, width="stretch")
        if {"feature_set", "auc"}.issubset(feature_set.columns):
            st.bar_chart(feature_set.set_index("feature_set")["auc"])
    else:
        st.info("缺失 feature_set_comparison.csv，请先运行 AutoML。")

    # 2. 模型族对比
    st.markdown("### 模型族对比（LR / XGBoost / LightGBM / Stacking）")
    model_compare = load_csv(AUTOML_MODEL_COMPARISON_CSV)
    if model_compare is not None:
        st.dataframe(model_compare, width="stretch")
        if {"model", "auc"}.issubset(model_compare.columns):
            st.bar_chart(model_compare.set_index("model")["auc"])
    else:
        st.info("缺失 model_comparison.csv，请先运行 AutoML。")

    # 3. 业务指标（利润最优阈值）
    st.markdown("### 业务指标 · 利润最优阈值")
    business = load_csv(AUTOML_BUSINESS_METRICS_CSV)
    if business is not None:
        st.dataframe(business, width="stretch")
        if {"model", "profit_per_loan_at_best_profit"}.issubset(business.columns):
            st.bar_chart(business.set_index("model")["profit_per_loan_at_best_profit"])
    else:
        st.info("缺失 business_metrics.csv，请先运行 AutoML。")

    # 4. Optuna 调参可视化
    st.markdown("### Optuna 自动调参")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(AUTOML_OPT_HISTORY_XGB_PNG, "XGBoost 优化历史")
        show_image_or_warn(AUTOML_FEATURE_SELECTION_PNG, "RFE 特征选择曲线")
    with c2:
        show_image_or_warn(AUTOML_HYPERPARAM_IMPORTANCE_XGB_PNG, "XGBoost 超参数重要性")
        show_image_or_warn(AUTOML_TEMPORAL_IMPORTANCE_PNG, "时序特征重要性热力图")

    # 5. 最优参数 JSON
    if AUTOML_BEST_PARAMS_JSON.exists():
        with st.expander("查看 AutoML 最优参数 JSON"):
            st.json(json.loads(AUTOML_BEST_PARAMS_JSON.read_text(encoding="utf-8")))


# ----------------------- Tab 4：可解释性 -----------------------
with tab_explain:
    st.subheader("SHAP 全局解释")
    # 1. Beeswarm 优先展示（颜色编码特征值，最直观）
    show_image_or_warn(ADV_SHAP_BEESWARM_PNG, "SHAP Beeswarm（颜色 = 特征值大小）")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(SHAP_BAR_PNG, "SHAP 全局重要性（bar）")
    with c2:
        show_image_or_warn(SHAP_SUMMARY_PNG, "SHAP summary（散点）")

    # 2. 交互效应 + Heatmap
    st.markdown("### SHAP 交互效应与样本聚类")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(ADV_SHAP_INTERACTION_PNG, "FICO × 利率 交互效应")
    with c2:
        show_image_or_warn(ADV_SHAP_HEATMAP_PNG, "SHAP Heatmap（样本聚类）")

    st.markdown("### PDP（数值特征 Top-K）")
    pdp_dir = FIGURES_DIR / "pdp"
    if pdp_dir.exists():
        pngs = sorted(pdp_dir.glob("*.png"))
        if pngs:
            grid = st.columns(2)
            for idx, png in enumerate(pngs):
                grid[idx % 2].image(str(png), caption=png.stem, width="stretch")
        else:
            st.info("PDP 目录为空，请运行 explainability/run_shap_analysis.py")
    else:
        st.info("尚未生成 PDP 图，请运行 explainability/run_shap_analysis.py")

    # 公平性分析
    st.markdown("### 公平性分析（Disparity / 州级差异）")
    fairness = load_csv(FAIRNESS_REPORT_CSV)
    if fairness is not None:
        st.dataframe(fairness, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(FAIRNESS_DISPARITY_BAR_PNG, "群体差异柱状图")
    with c2:
        show_image_or_warn(FAIRNESS_STATE_HEATMAP_PNG, "州级公平性热力图")


# ----------------------- Tab 5：风控策略 -----------------------
with tab_strategy:
    st.subheader("阈值-通过率-坏账率-利润")
    show_image_or_warn(RISK_STRATEGY_PNG, "阈值扫描")
    strategy = load_csv(RISK_STRATEGY_CSV)
    if strategy is not None:
        st.dataframe(strategy, width="stretch")
        # 1. 提供交互式阈值选择
        thr = st.slider(
            "选择审批阈值（违约概率）",
            min_value=float(strategy["threshold"].min()),
            max_value=float(strategy["threshold"].max()),
            value=0.3,
            step=0.05,
        )
        nearest = strategy.iloc[(strategy["threshold"] - thr).abs().argmin()]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("通过率", f"{nearest['approve_rate']:.2%}")
        c2.metric("放贷后坏账率", f"{nearest['bad_rate_in_approved']:.2%}")
        c3.metric("坏账拦截率", f"{nearest['bad_recall']:.2%}")
        c4.metric("单笔利润", f"{nearest['profit_per_loan']:.4f}")
    else:
        st.warning("缺失 risk_strategy.csv，请先运行 `python strategy/run_risk_strategy_simulation.py`")

    st.markdown("### 状态感知宏观风险与动态阈值")
    state_aware_risk = load_csv(STATE_AWARE_RISK_SUMMARY_CSV)
    if state_aware_risk is not None:
        st.dataframe(state_aware_risk, width="stretch")
        if {"macro_state", "weighted_default_rate"}.issubset(state_aware_risk.columns):
            st.bar_chart(state_aware_risk.set_index("macro_state")["weighted_default_rate"])
    else:
        st.info("尚未生成宏观状态风险汇总，请运行 `python strategy/state_aware_risk/run_state_aware_risk_analysis.py`")

    show_image_or_warn(STATE_AWARE_DYNAMIC_STRATEGY_PNG, "状态感知阈值策略")
    state_aware_strategy = load_csv(STATE_AWARE_DYNAMIC_STRATEGY_CSV)
    if state_aware_strategy is not None:
        st.dataframe(state_aware_strategy, width="stretch")
    else:
        st.info("尚未生成 状态感知动态阈值策略，请运行 `python strategy/state_aware_risk/run_state_aware_risk_analysis.py`")

    # 宏观压力测试（CCAR 风格情景）
    st.markdown("### 宏观压力测试（Baseline / Adverse / Severely Adverse）")
    stress = load_csv(STRESS_TESTING_RESULTS_CSV)
    if stress is not None:
        st.dataframe(stress, width="stretch")
    else:
        st.info("尚未生成压力测试结果，请运行 `python strategy/run_stress_testing.py`")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(STRESS_TESTING_IMPACT_PNG, "情景对比：违约率/利润")
    with c2:
        show_image_or_warn(STRESS_TESTING_WATERFALL_PNG, "Waterfall：冲击分解")

    # 组合优化
    st.markdown("### 组合优化（有效前沿 / 最优权重）")
    frontier = load_csv(PORTFOLIO_FRONTIER_CSV)
    weights = load_csv(PORTFOLIO_OPTIMAL_WEIGHTS_CSV)
    c1, c2 = st.columns(2)
    with c1:
        if frontier is not None:
            st.dataframe(frontier.head(20), width="stretch")
        show_image_or_warn(PORTFOLIO_FRONTIER_PNG, "有效前沿")
    with c2:
        if weights is not None:
            st.dataframe(weights, width="stretch")
        show_image_or_warn(PORTFOLIO_RISK_RETURN_PNG, "风险-收益热力图")

    # CECL 准备金
    st.markdown("### CECL 准备金计提")
    cecl = load_csv(CECL_PROVISIONING_CSV)
    if cecl is not None:
        st.dataframe(cecl, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        show_image_or_warn(CECL_STAGE_DISTRIBUTION_PNG, "Stage 分布")
    with c2:
        show_image_or_warn(CECL_PROVISION_WATERFALL_PNG, "准备金 Waterfall")


# ----------------------- Tab 6：决策追溯 -----------------------
with tab_trace:
    st.subheader("单笔贷款决策追溯")
    st.caption("对应计划中的 M1-5：把评分、阈值、审批结果、命中规则和反事实改善路径串成可审计链路。")

    decision_logs = load_decision_logs(TABLES_DIR / "decision_logs.json")
    if decision_logs:
        log_frame = pd.DataFrame(
            [
                {
                    "application_id": item.get("application_id"),
                    "decision": item.get("decision"),
                    "probability": item.get("probability"),
                    "threshold": item.get("threshold"),
                    "rule_count": len(item.get("rules", [])),
                    "timestamp": item.get("timestamp"),
                }
                for item in decision_logs
            ]
        )
        approved_count = int((log_frame["decision"] == "accept").sum())
        rejected_count = int((log_frame["decision"] == "reject").sum())
        avg_probability = float(log_frame["probability"].mean())

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("审计样本数", f"{len(log_frame):,}")
        with c2:
            render_metric_card("通过数", f"{approved_count:,}")
        with c3:
            render_metric_card("拒绝数", f"{rejected_count:,}")
        with c4:
            render_metric_card("平均违约概率", f"{avg_probability:.2%}")

        selected_app = st.selectbox(
            "选择一笔贷款查看审批链路",
            log_frame.sort_values("probability", ascending=False)["application_id"].tolist(),
        )
        selected_log = next(item for item in decision_logs if item.get("application_id") == selected_app)

        st.markdown("#### 决策链路")
        chain_cols = st.columns(4)
        chain_cols[0].metric("预测违约概率", f"{float(selected_log['probability']):.2%}")
        chain_cols[1].metric("审批阈值", f"{float(selected_log['threshold']):.2%}")
        chain_cols[2].metric("审批结果", str(selected_log["decision"]))
        chain_cols[3].metric("命中规则数", str(len(selected_log.get("rules", []))))

        rules = selected_log.get("rules", [])
        if rules:
            st.warning("命中规则：" + "、".join(map(str, rules)))
        else:
            st.success("该样本未命中人工拒绝规则，由模型概率与阈值共同决定审批结果。")

        features = pd.DataFrame(
            [{"feature": key, "value": value} for key, value in selected_log.get("features", {}).items()]
        )
        important_features = [
            "loan_amnt",
            "int_rate",
            "annual_inc",
            "dti",
            "fico_avg",
            "term_months",
            "grade",
            "purpose",
            "home_ownership",
            "season",
        ]
        st.markdown("#### 核心申请特征")
        if not features.empty:
            core_features = features[features["feature"].isin(important_features)]
            feature_view = (core_features if not core_features.empty else features.head(20)).copy()
            feature_view["value"] = feature_view["value"].astype(str)
            st.dataframe(feature_view, width="stretch")

        with st.expander("查看完整决策日志表"):
            st.dataframe(log_frame.sort_values("probability", ascending=False), width="stretch")
    else:
        st.info("尚未生成决策日志，请运行 `python explainability/run_explainability_enhancement.py`")

    st.markdown("### 反事实改善路径")
    min_change = load_csv(TABLES_DIR / "counterfactual_min_change.csv")
    counterfactual_report = load_csv(TABLES_DIR / "counterfactual_report.csv")
    if min_change is not None:
        st.markdown("#### 最小改变量")
        st.dataframe(min_change, width="stretch")
        # 1. 仅当存在非零改变量时才画柱状图，避免空图占位造成视觉错位
        if {"feature", "minimal_change"}.issubset(min_change.columns):
            chart_data = min_change.set_index("feature")["minimal_change"]
            non_zero = chart_data.fillna(0).astype(float).abs().sum()
            if non_zero > 0:
                st.bar_chart(chart_data)
            else:
                st.caption("当前样本预测已满足期望结果，无需特征改变；故不展示柱状图。")
    else:
        st.info("尚未生成 counterfactual_min_change.csv，请运行 `python explainability/run_causal_analysis.py`")

    if counterfactual_report is not None:
        st.markdown("#### 反事实情景扫描")
        feature_options = counterfactual_report["feature"].dropna().unique().tolist()
        chosen_feature = st.selectbox("选择反事实特征", feature_options)
        feature_view = counterfactual_report[counterfactual_report["feature"] == chosen_feature].copy()
        st.dataframe(feature_view, width="stretch")
        if {"counterfactual_value", "counterfactual_prediction"}.issubset(feature_view.columns):
            st.line_chart(feature_view.set_index("counterfactual_value")["counterfactual_prediction"])
    else:
        st.info("尚未生成 counterfactual_report.csv，请运行 `python explainability/run_causal_analysis.py`")

    audit_report = TABLES_DIR / "decision_audit_report.md"
    if audit_report.exists():
        with st.expander("查看决策审计报告"):
            st.markdown(audit_report.read_text(encoding="utf-8"))


# ----------------------- Tab 7：AI 助手 -----------------------
with tab_ai:
    from llm.llm_qa_system import figure_to_png_bytes, get_dataset_options, recommend_dataset, run_query

    ai_qa, ai_rag, ai_explain, ai_agent = st.tabs(
        ["自然语言问答", "证据检索 (RAG)", "决策解释", "Agent 智能助手"]
    )

    # 1. 自然语言问答（保留原有 QA + 自动出图）
    with ai_qa:
        st.subheader("自然语言问答与自动出图")
        st.caption("输入自然语言问题，系统会自动推荐数据源，现场生成安全 pandas 代码，并在适合时自动生成图表。")

        dataset_options = get_dataset_options()
        available_options = [item for item in dataset_options if item["path"].exists()]
        if not available_options:
            st.warning("未找到可用问答数据源，请先运行分析脚本生成 outputs 产物。")
        else:
            if "llm_question" not in st.session_state:
                st.session_state["llm_question"] = LLM_QA_PRESET_QUESTIONS[0]
            if "llm_history" not in st.session_state:
                st.session_state["llm_history"] = []

            # 1.1 数据源自动路由与预设问题
            auto_route = st.checkbox(
                "自动推荐数据源",
                value=True,
                help="根据问题关键词自动选择最适合的 状态感知 / 模型 / 策略 / 分层数据源。",
            )
            recommended_dataset = recommend_dataset(st.session_state["llm_question"]) if auto_route else None
            selected_index = 0
            if recommended_dataset:
                for idx, item in enumerate(available_options):
                    if item["label"] == recommended_dataset["label"]:
                        selected_index = idx
                        break
            selected_label = st.selectbox(
                "选择数据源",
                [item["label"] for item in available_options],
                index=selected_index,
                help="不同数据源决定 LLM 能回答的问题范围。",
                disabled=auto_route,
            )
            selected_dataset = next(item for item in available_options if item["label"] == selected_label)
            if auto_route and recommended_dataset:
                matched = "、".join(recommended_dataset.get("matched_keywords", [])) or "默认推荐"
                st.info(f"自动推荐：{recommended_dataset['label']}；匹配依据：{matched}")
                selected_dataset = recommended_dataset
            st.caption(selected_dataset["description"])

            st.markdown("**预设问题**")
            preset_cols = st.columns(2)
            for idx, preset in enumerate(LLM_QA_PRESET_QUESTIONS):
                if preset_cols[idx % 2].button(preset, key=f"preset_{idx}"):
                    st.session_state["llm_question"] = preset

            # 1.2 用户提问
            question = st.text_area(
                "请输入问题：",
                key="llm_question",
                height=90,
                placeholder="例如：违约率最高的 5 个州是哪些？请画柱状图展示",
            )
            action_cols = st.columns([1, 1, 4])
            submit = action_cols[0].button("提问", type="primary")
            if action_cols[1].button("清空历史"):
                st.session_state["llm_history"] = []

            # 1.3 执行问答并保存历史
            if submit and question.strip():
                try:
                    with st.spinner("正在询问 LLM..."):
                        if auto_route:
                            selected_dataset = recommend_dataset(question.strip())
                        result = run_query(
                            question.strip(),
                            dataset=selected_dataset["path"],
                            enable_chart=True,
                            dataset_label=selected_dataset["label"],
                            dataset_description=selected_dataset["description"],
                            save_chart=True,
                        )
                    if result.get("chart_figure"):
                        st.pyplot(result["chart_figure"], clear_figure=True)
                        st.caption(result.get("chart_title", "自动生成图表"))
                        if result.get("chart_note"):
                            st.info(result["chart_note"])
                        st.download_button(
                            "下载当前图表 PNG",
                            data=figure_to_png_bytes(result["chart_figure"]),
                            file_name=f"{result.get('chart_title', 'llm_chart')}.png",
                            mime="image/png",
                        )
                    st.write(result["result"])
                    with st.expander("查看 LLM 生成的安全代码"):
                        st.code(result["code"], language="python")
                    st.session_state["llm_history"].insert(0, result)
                except Exception as e:  # noqa: BLE001
                    st.error(f"问答失败：{e}")

            # 1.4 多轮历史
            if st.session_state["llm_history"]:
                st.markdown("### 最近问答历史")
                for idx, item in enumerate(st.session_state["llm_history"][:5]):
                    with st.expander(f"{idx + 1}. {item['question']}（{item.get('dataset_label', item['dataset'])}）"):
                        if item.get("chart_path") and Path(item["chart_path"]).exists():
                            st.image(str(item["chart_path"]), caption=item.get("chart_title", "自动生成图表"))
                        if item.get("chart_note"):
                            st.info(item["chart_note"])
                        st.write(item["result"])
                        st.code(item["code"], language="python")

    # 2. 证据检索 RAG：在项目分析文档中检索片段并生成带引用的回答
    with ai_rag:
        st.subheader("证据检索（RAG）")
        st.caption("在项目分析报告 / outputs 文档中检索相关片段，由 LLM 生成带 [编号] 引用的回答。")
        from llm.llm_rag import answer as rag_answer, build_index as rag_build_index

        rag_cols = st.columns([3, 1])
        rag_question = rag_cols[0].text_input(
            "请输入问题（检索式）：",
            key="rag_question",
            placeholder="例如：当前模型在压力情景下的 KS 是多少？",
        )
        if rag_cols[1].button("重建索引"):
            with st.spinner("重新扫描 outputs/ 与 AGENTS.md..."):
                docs = rag_build_index()
            st.success(f"已重建 RAG 索引，共 {len(docs)} 个片段。")
        if st.button("检索并回答", type="primary", key="rag_submit") and rag_question.strip():
            try:
                with st.spinner("检索证据并请求 LLM..."):
                    rag_result = rag_answer(rag_question.strip())
                st.markdown("#### 回答")
                st.write(rag_result["answer"])
                st.markdown("#### 检索到的证据")
                for item in rag_result.get("evidence", []):
                    with st.expander(
                        f"[{item['index']}] {item['source']}（相关度 {item['score']:.3f}）"
                    ):
                        st.code(item["snippet"], language="markdown")
                if not rag_result.get("evidence"):
                    st.warning("未检索到相关证据，建议换个关键词或先运行分析脚本生成 markdown 报告。")
            except Exception as exc:  # noqa: BLE001
                st.error(f"RAG 失败：{exc}")

    # 3. 决策解释：单笔申请 → SHAP/反事实证据 → 自然语言解释
    with ai_explain:
        st.subheader("单笔贷款决策解释")
        st.caption("选定 application_id，结合全局特征重要性与反事实最小改变量，由 LLM 输出可执行的改善建议。")
        from llm.llm_decision_explainer import explain as explain_decision, list_application_ids

        try:
            app_ids = list_application_ids()
        except FileNotFoundError as exc:
            app_ids = []
            st.warning(f"决策日志缺失：{exc}")
        if app_ids:
            chosen_id = st.selectbox("选择 application_id", app_ids, key="explain_app_id")
            if st.button("生成解释", type="primary", key="explain_submit"):
                try:
                    with st.spinner("正在生成决策解释..."):
                        result = explain_decision(chosen_id)
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("最终决策", result["decision"])
                    metric_cols[1].metric("违约概率", f"{result['probability']:.4f}")
                    metric_cols[2].metric("风控阈值", f"{result['threshold']}")
                    st.markdown("#### 自然语言解释")
                    st.write(result["explanation"])
                    if result.get("rules"):
                        st.markdown("**命中规则**：" + "、".join(result["rules"]))
                    with st.expander("查看原始特征"):
                        st.json(result.get("features", {}))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"解释失败：{exc}")

    # 4. Agent 智能助手：自动路由到 qa_table / rag_search / explain_decision
    with ai_agent:
        st.subheader("Agent 智能助手")
        st.caption(
            "由 LLM 通过 function calling 自主调度数据问答 / 文档检索 / 单笔决策解释三类工具，并展示完整推理链路。"
        )
        from llm.llm_agent import run_agent

        agent_question = st.text_area(
            "请输入问题：",
            key="agent_question",
            height=90,
            placeholder="例如：APP_000003 这笔为什么被拒？再告诉我违约率最高的 3 个州",
        )
        if st.button("启动 Agent", type="primary", key="agent_submit") and agent_question.strip():
            try:
                with st.spinner("Agent 正在思考与调用工具..."):
                    agent_result = run_agent(agent_question.strip())
                st.markdown("#### 最终回答")
                st.write(agent_result.get("answer") or "（Agent 未返回最终回答）")
                st.markdown("#### 工具调用轨迹")
                for item in agent_result.get("trace", []):
                    if item.get("type") == "tool":
                        with st.expander(
                            f"步骤 {item['step']}：调用工具 {item['tool']}"
                        ):
                            st.markdown("**参数**")
                            st.json(item.get("arguments", {}))
                            st.markdown("**返回（文本摘要）**")
                            st.code(item.get("result_text", ""), language="markdown")
                            if item.get("error"):
                                st.error(item["error"])
                    else:
                        st.info(f"步骤 {item['step']}：模型输出最终回答")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Agent 执行失败：{exc}")
