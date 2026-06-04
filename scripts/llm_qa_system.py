"""scripts/llm_qa_system.py LLM 自然语言问答（Text-to-Pandas）
1. 用户用自然语言提问；
2. LLM 生成单行 pandas 表达式赋值给 answer；
3. 在受限的安全环境中执行并返回结果。
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import SYSTEM_PROMPT_QA  # noqa: E402
from constant.paths import TABLES_DIR  # noqa: E402
from scripts._llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 默认问答数据集：分组聚合后的 CSV，体量小、字段清晰
DEFAULT_DATASET = TABLES_DIR / "lc_default_by_state_with_ers_features.csv"

# 代码安全黑名单：禁止任何 IO/反射/执行类调用
FORBIDDEN_PATTERNS = [
    r"\bimport\b",
    r"\bopen\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__\w+__",
    r"\bos\b",
    r"\bsys\b",
    r"\bsubprocess\b",
    r"\bPath\b",
    r"\brequests\b",
]


class UnsafeCodeError(RuntimeError):
    """UnsafeCodeError 检测到不允许的 LLM 输出代码"""


def _strip_code_fence(text: str) -> str:
    """_strip_code_fence 去掉 ```python ... ``` 代码块包装"""
    text = text.strip()
    fence = re.match(r"^```(?:python)?\s*(.*?)```\s*$", text, re.DOTALL)
    return fence.group(1).strip() if fence else text


def _validate(code: str) -> None:
    """_validate 校验生成的代码无危险调用"""
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, code):
            raise UnsafeCodeError(f"生成代码触发安全规则：{pat}")
    if "answer" not in code:
        raise UnsafeCodeError("生成代码缺少 answer 变量赋值")


def build_prompt(df: pd.DataFrame, question: str) -> str:
    """build_prompt 拼装包含 schema 的 user prompt"""
    schema = "\n".join(f"- {col}: {df[col].dtype}" for col in df.columns)
    sample = df.head(3).to_markdown(index=False)
    return (
        f"DataFrame `df` 的字段如下：\n{schema}\n\n"
        f"前 3 行预览：\n{sample}\n\n"
        f"用户问题：{question}\n\n"
        "请输出形如 `answer = df.xxx` 的单条赋值代码，仅一行。"
    )


def run_query(question: str, dataset: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """run_query 单次问答主流程
    1. 加载数据集；
    2. 调用 LLM；
    3. 校验并执行代码；
    4. 返回 question/code/result。
    """
    if not dataset.exists():
        raise FileNotFoundError(f"未找到问答数据集：{dataset}")
    df = pd.read_csv(dataset)
    client = LLMClient()
    raw = client.chat(SYSTEM_PROMPT_QA, build_prompt(df, question), temperature=0.0, max_tokens=300)
    code = _strip_code_fence(raw)
    _validate(code)
    safe_globals = {"__builtins__": {"len": len, "min": min, "max": max, "round": round}}
    safe_locals: dict[str, Any] = {"df": df, "pd": pd, "np": np}
    exec(code, safe_globals, safe_locals)  # noqa: S102 已通过黑名单校验
    return {
        "question": question,
        "code": code,
        "result": safe_locals.get("answer"),
        "dataset": dataset.name,
    }


def main():
    parser = argparse.ArgumentParser(description="LLM 自然语言问答（Text-to-Pandas）")
    parser.add_argument("question", help="用户问题，如：违约率最高的 5 个州是哪些？")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    out = run_query(args.question, args.dataset)
    print(f"\n>>> 生成代码：\n{out['code']}\n")
    print(f">>> 执行结果：\n{out['result']}")


if __name__ == "__main__":
    main()
