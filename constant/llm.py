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
    },
    {
        "label": "季度违约率 + FRED 宏观变量",
        "path_key": "tables",
        "filename": "lc_default_by_quarter_with_fred_macro.csv",
        "description": "适合回答季度趋势、宏观指标变化与违约率波动。",
    },
    {
        "label": "Grade × Purpose 风险分层",
        "path_key": "tables",
        "filename": "lc_segment_grade_purpose.csv",
        "description": "适合回答贷款等级、用途组合下的风险差异。",
    },
    {
        "label": "FICO × 利率风险分层",
        "path_key": "tables",
        "filename": "lc_segment_interest_fico.csv",
        "description": "适合回答信用分、利率组合下的风险分层。",
    },
    {
        "label": "模型指标对比",
        "path_key": "models",
        "filename": "model_metrics.csv",
        "description": "适合回答 LR、XGBoost 等模型的 AUC、KS、准确率等表现对比。",
    },
    {
        "label": "风控阈值策略",
        "path_key": "models",
        "filename": "risk_strategy.csv",
        "description": "适合回答审批阈值、通过率、坏账率、利润之间的权衡。",
    },
]

# 自然语言问答预设问题
LLM_QA_PRESET_QUESTIONS = [
    "违约率最高的 5 个州是哪些？请画柱状图展示，并说明图例含义",
    "不同季度的违约率有什么变化趋势？请画折线图并解释拐点",
    "哪些 Grade 和贷款用途组合风险最高？请用表格或热力图说明",
    "不同模型的 AUC 和 KS 表现如何？请画柱状图比较",
    "哪个风控阈值的利润最高？通过率和坏账率分别是多少？",
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
    _load_dotenv_once()
    return os.environ.get(ENV_API_KEY, "")


def resolve_base_url() -> str:
    _load_dotenv_once()
    return os.environ.get(ENV_BASE_URL, "")


def resolve_model() -> str:
    _load_dotenv_once()
    return os.environ.get(ENV_MODEL, "")
