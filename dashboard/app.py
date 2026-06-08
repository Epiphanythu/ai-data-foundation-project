"""dashboard/app.py 核心 Streamlit Dashboard
启动方式：
    streamlit run dashboard/app.py

5 个核心 Tab：
1. 数据概览
2. 模型表现
3. 可解释性（SHAP/PDP）
4. 风控策略
5. AI 助手（自动报告 + 自然语言问答）
"""
from __future__ import annotations

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
    FIGURES_DIR,
    LLM_AUTO_REPORT_MD,
    STATE_AWARE_DYNAMIC_STRATEGY_CSV,
    STATE_AWARE_DYNAMIC_STRATEGY_PNG,
    STATE_AWARE_MODEL_VALIDATION_CSV,
    STATE_AWARE_RISK_SUMMARY_CSV,
    MODEL_FEATURE_IMPORTANCE_CSV,
    MODEL_METRICS_CSV,
    RISK_STRATEGY_CSV,
    RISK_STRATEGY_PNG,
    SHAP_BAR_PNG,
    SHAP_SUMMARY_PNG,
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


# ----------------------- 标题 -----------------------
st.title("📊 多源数据 · 个人贷款违约风险 Dashboard")
st.caption("Lending Club + FRED 宏观 + ERS 州级经济 · 模型对比 · 可解释性 · 风控策略 · AI 助手")

tab_overview, tab_model, tab_explain, tab_strategy, tab_ai = st.tabs(
    ["数据概览", "模型表现", "可解释性", "风控策略", "AI 助手"]
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


# ----------------------- Tab 3：可解释性 -----------------------
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


# ----------------------- Tab 4：风控策略 -----------------------
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


# ----------------------- Tab 5：AI 助手 -----------------------
with tab_ai:
    st.subheader("LLM 自动分析报告")
    if LLM_AUTO_REPORT_MD.exists():
        st.markdown(LLM_AUTO_REPORT_MD.read_text(encoding="utf-8"))
    else:
        st.info("尚未生成报告。点击下方按钮可触发生成（需要配置 OPENAI_API_KEY 与 OPENAI_BASE_URL）。")

    if st.button("🔁 重新生成报告"):
        try:
            from llm.llm_auto_report import run as run_report

            with st.spinner("调用 LLM 生成报告..."):
                run_report()
            st.success("已生成，请刷新页面查看。")
        except Exception as e:  # noqa: BLE001
            st.error(f"生成失败：{e}")

    st.markdown("---")
    st.subheader("自然语言问答与自动出图")
    st.caption("输入自然语言问题，系统会自动推荐数据源，现场生成安全 pandas 代码，并在适合时自动生成图表。")

    from llm.llm_qa_system import figure_to_png_bytes, get_dataset_options, recommend_dataset, run_query

    dataset_options = get_dataset_options()
    available_options = [item for item in dataset_options if item["path"].exists()]
    if not available_options:
        st.warning("未找到可用问答数据源，请先运行分析脚本生成 outputs 产物。")
        st.stop()

    if "llm_question" not in st.session_state:
        st.session_state["llm_question"] = LLM_QA_PRESET_QUESTIONS[0]
    if "llm_history" not in st.session_state:
        st.session_state["llm_history"] = []

    # 1. 数据源自动路由与预设问题
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

    # 2. 用户提问
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

    # 3. 执行问答并保存历史
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

    # 4. 多轮历史
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
