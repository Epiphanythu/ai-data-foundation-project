"""llm.py LLM 集成常量"""
import os
from pathlib import Path

# 项目根目录（用于定位 .env）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

# 通过 OpenAI SDK 适配 GLM 时使用的环境变量
ENV_API_KEY = "OPENAI_API_KEY"
ENV_BASE_URL = "OPENAI_BASE_URL"
ENV_MODEL = "OPENAI_MODEL"

# 报告生成提示词类型
REPORT_TYPE_OVERVIEW = "overview"
REPORT_TYPE_RISK = "risk"
REPORT_TYPE_MACRO = "macro"

# 问答系统模式
QA_MODE_PANDAS = "pandas"
QA_MODE_INSIGHT = "insight"

# 自然语言问答生成控制
LLM_QA_MAX_RETRIES = 3
LLM_QA_CODE_MAX_TOKENS = 1500

# 自然语言问答可选数据源
LLM_QA_DATASETS = [
    {
        "label": "州级违约率 + ERS 经济变量",
        "path_key": "tables",
        "filename": "lc_default_by_state_with_ers_features.csv",
        "description": "适合回答哪些州违约率高、州级经济变量与违约风险的关系。",
        "routing_keywords": ["州", "state", "地区", "ERS", "贫困率", "收入", "违约率最高"],
    },
    {
        "label": "季度违约率 + FRED 宏观变量",
        "path_key": "tables",
        "filename": "lc_default_by_quarter_with_fred_macro.csv",
        "description": "适合回答季度趋势、宏观指标变化与违约率波动。",
        "routing_keywords": ["季度", "趋势", "FRED", "宏观", "失业率", "利率", "CPI", "拐点"],
    },
    {
        "label": "Grade × Purpose 风险分层",
        "path_key": "tables",
        "filename": "lc_segment_grade_purpose.csv",
        "description": "适合回答贷款等级、用途组合下的风险差异。",
        "routing_keywords": ["Grade", "grade", "等级", "用途", "purpose", "组合风险"],
    },
    {
        "label": "FICO × 利率风险分层",
        "path_key": "tables",
        "filename": "lc_segment_interest_fico.csv",
        "description": "适合回答信用分、利率组合下的风险分层。",
        "routing_keywords": ["FICO", "fico", "信用分", "利率分层", "利率组合"],
    },
    {
        "label": "模型指标对比",
        "path_key": "models",
        "filename": "model_metrics.csv",
        "description": "适合回答 LR、XGBoost 等模型的 AUC、KS、准确率等表现对比。",
        "routing_keywords": ["模型", "AUC", "KS", "准确率", "precision", "recall", "LR", "XGBoost"],
    },
    {
        "label": "风控阈值策略",
        "path_key": "models",
        "filename": "risk_strategy.csv",
        "description": "适合回答审批阈值、通过率、坏账率、利润之间的权衡。",
        "routing_keywords": ["风控", "阈值", "审批", "通过率", "坏账率", "利润", "固定阈值"],
    },
    {
        "label": "状态感知宏观风险",
        "path_key": "tables",
        "filename": "state_aware_risk_summary.csv",
        "description": "适合回答正常期、观察期、压力期下的违约率、宏观压力和贷款量差异。",
        "routing_keywords": ["宏观状态", "状态", "正常期", "观察期", "压力期", "状态风险"],
    },
    {
        "label": "状态感知模型验证",
        "path_key": "models",
        "filename": "state_aware_model_validation_summary.csv",
        "description": "适合回答模型 AUC、KS、校准误差、Top Decile 坏账捕获能力。",
        "routing_keywords": ["模型验证", "Top Decile", "坏账捕获", "校准", "brier", "消融"],
    },
    {
        "label": "状态感知动态阈值策略",
        "path_key": "models",
        "filename": "state_aware_dynamic_threshold_strategy.csv",
        "description": "适合回答固定阈值与状态感知阈值在利润、坏账率、通过率上的差异。",
        "routing_keywords": [
            "动态阈值",
            "状态感知阈值",
            "状态感知",
            "策略收益",
            "利润提升",
            "固定阈值",
            "坏账率",
            "利润",
            "通过率",
        ],
    },
    {
        "label": "反事实最小改善路径",
        "path_key": "tables",
        "filename": "counterfactual_min_change.csv",
        "description": "适合回答单笔贷款需要调整哪些特征，才能达到期望审批或风险结果。",
        "routing_keywords": ["反事实", "改善", "最小改变量", "怎样通过", "拒绝原因", "counterfactual"],
    },
    {
        "label": "决策追溯日志",
        "path_key": "tables",
        "filename": "decision_logs.json",
        "description": "适合回答单笔申请的预测概率、阈值、审批结果和命中规则。",
        "routing_keywords": ["决策追溯", "审计", "单笔", "审批链路", "命中规则", "decision"],
    },
    {
        "label": "AutoML 特征组消融",
        "path_key": "tables",
        "filename": "automl/feature_set_comparison.csv",
        "description": "适合回答 Base、Temporal、Macro、All 等特征组对模型和业务指标的影响。",
        "routing_keywords": ["AutoML", "automl", "消融", "特征组", "Temporal", "Macro", "状态感知建模"],
    },
    {
        "label": "AutoML 模型业务指标",
        "path_key": "tables",
        "filename": "automl/business_metrics.csv",
        "description": "适合回答 AutoML 模型在利润最优阈值下的通过率、坏账率和利润。",
        "routing_keywords": ["AutoML", "automl", "业务指标", "利润最优", "调参", "模型选择"],
    },
]

# 自然语言问答预设问题
LLM_QA_PRESET_QUESTIONS = [
    "违约率最高的 5 个州是哪些？请画柱状图展示，并说明图例含义",
    "不同季度的违约率有什么变化趋势？请画折线图并解释拐点",
    "哪些 Grade 和贷款用途组合风险最高？请用表格或热力图说明",
    "不同模型的 AUC 和 KS 表现如何？请画柱状图比较",
    "哪个风控阈值的利润最高？通过率和坏账率分别是多少？",
    "不同宏观状态下的违约率有什么差异？请画柱状图说明",
    "XGBoost 和逻辑回归的 Top Decile 坏账捕获能力哪个更强？",
    "状态感知阈值相比固定阈值，在利润和坏账率上有什么变化？",
    "单笔贷款如果要降低风险，最小需要改变哪些特征？",
    "AutoML 选择的最优特征组和最优模型是什么？业务指标是否提升？",
]

# 系统提示
SYSTEM_PROMPT_REPORT = (
    "你是一名金融风险数据分析师，擅长基于 Lending Club、FRED 宏观、ERS 州级数据"
    "进行违约风险洞察。请基于给定的数据指标给出**客观、量化、有结论**的分析报告，"
    "用简洁中文输出，必要时使用 Markdown 列表。"
)

SYSTEM_PROMPT_QA = (
    "你是一名数据分析助手。给定 Lending Club 违约率数据集（pandas DataFrame `df`）的列名，"
    "请将用户问题转化为**单条可执行的 pandas 表达式**，赋值给变量 `answer`。"
    "禁止使用 import、文件 IO、网络访问、循环和 exec/eval；仅使用 pandas/numpy 内置能力。"
    "只输出代码，不要任何解释。"
)

SYSTEM_PROMPT_QA_MULTIMODAL = (
    "你是一名数据分析助手。给定 Lending Club 违约率数据集（pandas DataFrame `df`）的列名，"
    "请将用户问题转化为安全的 pandas 分析代码。第一条结果赋值必须是 `answer = ...`，"
    "且最终返回结果变量也必须叫 `answer`。如果需要临时变量，必须在 `answer = ...` 之后定义。"
    "如果问题适合可视化，"
    "再调用一个受控绘图函数赋值给 `chart`，设置 `chart_title`，并用 `chart_note` 用一句中文说明图表含义。"
    "只能使用 pandas/numpy 与以下绘图函数：plot_bar、plot_line、plot_hist、plot_scatter、plot_heatmap。"
    "禁止使用 import、文件 IO、网络访问、循环、plt、exec/eval。只输出代码，不要任何解释。"
)

# RAG 配置：用于检索 outputs/tables/*.md 等发现文档
LLM_RAG_TOP_K = 4
LLM_RAG_CHUNK_SIZE = 380
LLM_RAG_CHUNK_OVERLAP = 60
LLM_RAG_DOC_SUFFIXES = (".md",)
SYSTEM_PROMPT_RAG = (
    "你是一名风控分析助手，必须严格基于给定证据片段回答用户问题。"
    "回答时必须遵循：1) 用简洁中文给出结论；2) 在每个关键结论后用方括号标注引用编号，如 [1][2]；"
    "3) 不允许使用证据外的事实；4) 如果证据不足以回答，请直接回答“证据不足”。"
    "回答末尾不要复述证据原文。"
)

# Agent function calling 配置
SYSTEM_PROMPT_AGENT = (
    "你是一名风控决策助手，可以调用三类工具来回答用户问题："
    "1) qa_table：当用户想从结构化数据里查具体数字、画图时调用，返回 pandas 计算结果；"
    "2) rag_search：当用户想了解项目结论、方法、发现时调用，返回项目文档证据；"
    "3) explain_decision：当用户想知道某笔贷款（含 application_id）为什么被拒/被批、怎么改才能过时调用。"
    "请根据用户问题选择最合适的工具。每次只调用一个工具。最终回答必须使用工具结果，不要凭空生成。"
)
LLM_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "qa_table",
            "description": "在结构化数据集（CSV/JSON）上执行 pandas 查询并可选返回图表，适合统计/对比/趋势类问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "用户原始问题或改写后的更精确问法"},
                    "enable_chart": {"type": "boolean", "description": "是否需要自动出图"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "在项目分析文档（findings.md / 报告）中检索证据并基于引用作答，适合方法论/结论类问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "需要在文档中检索的问题"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_decision",
            "description": "解释单笔贷款的审批结果及反事实改善建议，输入应包含 application_id（如 APP_000003）",
            "parameters": {
                "type": "object",
                "properties": {
                    "application_id": {"type": "string", "description": "贷款申请编号，如 APP_000003"},
                },
                "required": ["application_id"],
            },
        },
    },
]

# 决策解释器
SYSTEM_PROMPT_DECISION_EXPLAIN = (
    "你是一名风控审批分析师。请基于给定的单笔贷款特征、模型预测概率、阈值、决策结果"
    "以及全局特征重要性、反事实最小改变量证据，用中文写一段简洁、专业的解释，结构如下："
    "1) 一句话给出决策结论；2) 列出 3 条主要风险因子并说明原因；3) 如果是拒绝，再给 1-2 条可执行的改善建议。"
    "不允许编造证据外的特征。"
)



def _load_dotenv_once() -> None:
    """_load_dotenv_once 优先从 .env 加载 LLM 配置；不存在则跳过"""
    # 1. 已经加载过则直接返回
    if getattr(_load_dotenv_once, "_loaded", False):
        return
    if _ENV_FILE.exists():
        try:
            from dotenv import load_dotenv  # 延迟导入，避免无依赖环境报错

            load_dotenv(_ENV_FILE, override=False)
        except ImportError:
            # 兜底：手动解析 KEY=VALUE
            for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _load_dotenv_once._loaded = True  # type: ignore[attr-defined]


def resolve_api_key() -> str:
    """按优先级解析 LLM API Key，支持环境变量和默认配置。"""
    _load_dotenv_once()
    return os.environ.get(ENV_API_KEY, "")


def resolve_base_url() -> str:
    """解析 LLM 服务地址，便于本地和不同部署环境切换。"""
    _load_dotenv_once()
    return os.environ.get(ENV_BASE_URL, "")


def resolve_model() -> str:
    """解析实际调用的 LLM 模型名称。"""
    _load_dotenv_once()
    return os.environ.get(ENV_MODEL, "")
