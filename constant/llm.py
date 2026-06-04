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

# 默认模型与端点（用户使用 GLM 适配 OpenAI）
DEFAULT_MODEL = "glm-4-plus"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

# 报告生成提示词类型
REPORT_TYPE_OVERVIEW = "overview"
REPORT_TYPE_RISK = "risk"
REPORT_TYPE_MACRO = "macro"

# 问答系统模式
QA_MODE_PANDAS = "pandas"
QA_MODE_INSIGHT = "insight"

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
    return os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)


def resolve_model() -> str:
    _load_dotenv_once()
    return os.environ.get(ENV_MODEL, DEFAULT_MODEL)
