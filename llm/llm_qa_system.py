"""llm/llm_qa_system.py LLM 自然语言问答与自动出图
1. 用户用自然语言提问；
2. LLM 生成安全 pandas/numpy 分析代码；
3. 在受控 AST 沙箱中执行，并按需返回文字结果、图表和图表说明。
"""
from __future__ import annotations

import argparse
import ast
import logging
import re
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import (  # noqa: E402
    LLM_QA_CODE_MAX_TOKENS,
    LLM_QA_DATASETS,
    LLM_QA_MAX_RETRIES,
    SYSTEM_PROMPT_QA,
    SYSTEM_PROMPT_QA_MULTIMODAL,
)
from constant.paths import LLM_CHARTS_DIR, MODELS_DIR, TABLES_DIR  # noqa: E402
from common.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 默认问答数据集：分组聚合后的 CSV，体量小、字段清晰
DEFAULT_DATASET = TABLES_DIR / "lc_default_by_state_with_ers_features.csv"
DATASET_PATH_ROOTS = {
    "tables": TABLES_DIR,
    "models": MODELS_DIR,
}

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
    r"\bplt\b",
    r"\bsavefig\b",
    r"\bfigure\b",
]

PROTECTED_NAMES = {"df", "pd", "np", "plot_bar", "plot_line", "plot_hist", "plot_scatter", "plot_heatmap"}
ALLOWED_METHODS = {
    "abs",
    "agg",
    "assign",
    "copy",
    "corr",
    "count",
    "dropna",
    "fillna",
    "groupby",
    "head",
    "idxmax",
    "idxmin",
    "max",
    "mean",
    "median",
    "min",
    "nlargest",
    "nsmallest",
    "pivot_table",
    "query",
    "rename",
    "reset_index",
    "round",
    "set_index",
    "sort_index",
    "sort_values",
    "sum",
    "tail",
    "to_frame",
    "value_counts",
}
ALLOWED_MODULE_ATTRS = {
    "pd": {"DataFrame", "Series", "crosstab", "pivot_table"},
    "np": {"abs", "clip", "log", "mean", "median", "round", "sqrt", "where"},
}


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
    if not re.search(r"(^|\n)\s*answer\s*=", code):
        raise UnsafeCodeError("生成代码缺少 answer 变量赋值")
    tree = ast.parse(code, mode="exec")
    if not tree.body:
        raise UnsafeCodeError("生成代码为空")
    first_stmt = tree.body[0]
    if (
        not isinstance(first_stmt, ast.Assign)
        or len(first_stmt.targets) != 1
        or not isinstance(first_stmt.targets[0], ast.Name)
        or first_stmt.targets[0].id != "answer"
    ):
        raise UnsafeCodeError("第一条赋值语句必须是 answer = ...")


def get_dataset_options() -> list[dict[str, Any]]:
    """get_dataset_options 返回 Dashboard 可选择的问答数据源"""
    options = []
    for item in LLM_QA_DATASETS:
        root = DATASET_PATH_ROOTS[item["path_key"]]
        options.append({**item, "path": root / item["filename"]})
    return options


def recommend_dataset(question: str, available_only: bool = True) -> dict[str, Any]:
    """recommend_dataset 根据自然语言问题推荐最匹配的数据源"""
    # 1. 使用显式关键词做轻量路由，避免预设问题落到错误数据源
    normalized = question.lower()
    options = get_dataset_options()
    if available_only:
        options = [item for item in options if item["path"].exists()]
    if not options:
        raise FileNotFoundError("未找到可用问答数据源，请先生成 outputs 产物")

    best_item = options[0]
    best_score = -1
    best_matches: list[str] = []
    for item in options:
        keywords = item.get("routing_keywords", [])
        searchable = f"{item['label']} {item['description']} {' '.join(keywords)}".lower()
        matches = [keyword for keyword in keywords if keyword.lower() in normalized]
        score = len(matches) * 10
        score += sum(1 for token in re.split(r"\W+", normalized) if token and token in searchable)
        if score > best_score:
            best_item = item
            best_score = score
            best_matches = matches

    # 2. 低置信度时回退到默认州级数据源，保证 CLI 与旧行为兼容
    if best_score <= 0:
        for item in options:
            if item["path"] == DEFAULT_DATASET:
                best_item = item
                break
    return {**best_item, "route_score": best_score, "matched_keywords": best_matches}


def figure_to_png_bytes(fig: Any) -> bytes:
    """figure_to_png_bytes 将 matplotlib Figure 转为 PNG 字节"""
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    return buffer.getvalue()


def save_chart_figure(fig: Any, title: str = "") -> Path:
    """save_chart_figure 保存 LLM 自动生成图表并返回路径"""
    LLM_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", title).strip("_") or "llm_chart"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LLM_CHARTS_DIR / f"{timestamp}_{safe_title[:30]}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path


def build_prompt(
    df: pd.DataFrame,
    question: str,
    enable_chart: bool = False,
    dataset_description: str = "",
) -> str:
    """build_prompt 拼装包含 schema 的 user prompt"""
    schema = "\n".join(f"- {col}: {df[col].dtype}" for col in df.columns)
    sample = df.head(3).to_string(index=False)
    if enable_chart:
        chart_instruction = (
            "请输出安全 Python 代码，可多行，但只能包含：\n"
            "1. 第一行必须是 `answer = ...`：pandas/numpy 分析结果；\n"
            "2. 如适合画图，`chart_title = \"...\"`；\n"
            "3. 如适合画图，`chart_note = \"...\"`，用一句中文解释图中最重要的信息；\n"
            "4. 如适合画图，`chart = plot_bar(...)` / `plot_line(...)` / `plot_hist(...)` / "
            "`plot_scatter(...)` / `plot_heatmap(...)`，可通过 `legend=\"...\"` 设置图例说明。\n"
            "图表选择规则：趋势用 plot_line，对比用 plot_bar，分布用 plot_hist，"
            "两个数值变量关系用 plot_scatter，二维交叉表用 plot_heatmap。\n"
            "answer 必须尽量保留关键指标列，chart_note 必须包含至少一个量化数字或排序结论。"
        )
    else:
        chart_instruction = "请输出形如 `answer = df.xxx` 的单条赋值代码，仅一行，answer 必须包含可核验的指标值。"
    return (
        f"当前数据源说明：{dataset_description or '未提供'}\n\n"
        f"DataFrame `df` 的字段如下：\n{schema}\n\n"
        f"前 3 行预览：\n{sample}\n\n"
        f"用户问题：{question}\n\n"
        f"{chart_instruction}"
    )


def _as_dataframe(data: Any) -> pd.DataFrame:
    """_as_dataframe 将 Series/DataFrame/标量统一转为可绘图 DataFrame"""
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, pd.Series):
        return data.reset_index()
    return pd.DataFrame({"value": [data]})


def _plot_bar(
    data: Any = None,
    x: Any = None,
    y: Any = None,
    title: str = "",
    legend: str | None = None,
):
    """_plot_bar 绘制柱状图"""
    if x is not None and not isinstance(x, str):
        # 1. 兼容 plot_bar(answer.index, answer.values) 与 plot_bar(x=..., y=...)
        labels = x if y is not None else data
        values = y if y is not None else x
        frame = pd.DataFrame({"label": pd.Series(labels).to_list(), "value": pd.Series(values).to_list()})
        x = "label"
        y = "value"
    elif x is None and y is None and isinstance(data, pd.Series):
        frame = data.reset_index()
        x = frame.columns[0]
        y = frame.columns[1]
    else:
        frame = _as_dataframe(data)
    plot_frame = frame.set_index(x) if x else frame
    values = plot_frame[y] if y else plot_frame.select_dtypes(include=[np.number])
    fig, ax = plt.subplots(figsize=(8, 4))
    values.plot(kind="bar", ax=ax, label=legend or y or "value", legend=True)
    ax.set_title(title)
    ax.set_xlabel(x or "")
    ax.set_ylabel(legend or y or "value")
    ax.legend(title="指标说明")
    ax.tick_params(axis="x", rotation=35)
    plt.tight_layout()
    return fig


def _plot_line(
    data: Any = None,
    x: Any = None,
    y: Any = None,
    title: str = "",
    legend: str | None = None,
):
    """_plot_line 绘制折线图"""
    if x is not None and not isinstance(x, str):
        # 1. 兼容 plot_line(answer.index, answer.values) 与 plot_line(x=..., y=...)
        labels = x if y is not None else data
        values = y if y is not None else x
        frame = pd.DataFrame({"label": pd.Series(labels).to_list(), "value": pd.Series(values).to_list()})
        x = "label"
        y = "value"
    elif x is None and y is None and isinstance(data, pd.Series):
        frame = data.reset_index()
        x = frame.columns[0]
        y = frame.columns[1]
    else:
        frame = _as_dataframe(data)
    plot_frame = frame.set_index(x) if x else frame
    values = plot_frame[y] if y else plot_frame.select_dtypes(include=[np.number])
    fig, ax = plt.subplots(figsize=(8, 4))
    values.plot(kind="line", ax=ax, marker="o", label=legend or y or "value")
    ax.set_title(title)
    ax.set_xlabel(x or "")
    ax.set_ylabel(legend or y or "value")
    ax.legend(title="指标说明")
    plt.tight_layout()
    return fig


def _plot_hist(
    data: Any,
    column: str | None = None,
    bins: int = 20,
    title: str = "",
    legend: str | None = None,
):
    """_plot_hist 绘制直方图"""
    frame = _as_dataframe(data)
    series = frame[column] if column else frame.select_dtypes(include=[np.number]).iloc[:, 0]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(series.dropna(), bins=bins, color="#4C78A8", alpha=0.85, label=legend or column or series.name)
    ax.set_title(title)
    ax.set_xlabel(column or str(series.name))
    ax.set_ylabel("样本数量")
    ax.legend(title="分布说明")
    plt.tight_layout()
    return fig


def _plot_scatter(data: Any = None, x: Any = None, y: Any = None, title: str = "", legend: str | None = None):
    """_plot_scatter 绘制散点图"""
    if x is not None and y is not None and not isinstance(x, str):
        frame = pd.DataFrame({"x": pd.Series(x).to_list(), "y": pd.Series(y).to_list()})
        x = "x"
        y = "y"
    elif x is not None and y is None and not isinstance(x, str):
        frame = pd.DataFrame({"x": pd.Series(data).to_list(), "y": pd.Series(x).to_list()})
        x = "x"
        y = "y"
    else:
        frame = _as_dataframe(data)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(frame[x], frame[y], s=28, alpha=0.7, label=legend or f"{x} vs {y}")
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(title)
    ax.legend(title="关系说明")
    plt.tight_layout()
    return fig


def _plot_heatmap(data: Any, title: str = ""):
    """_plot_heatmap 绘制二维矩阵热力图"""
    frame = _as_dataframe(data)
    numeric = frame.select_dtypes(include=[np.number])
    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(numeric.values, aspect="auto", cmap="YlOrRd")
    ax.set_title(title)
    ax.set_xticks(range(len(numeric.columns)))
    ax.set_xticklabels(numeric.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(numeric.index)))
    ax.set_yticklabels(numeric.index)
    fig.colorbar(image, ax=ax)
    plt.tight_layout()
    return fig


def _build_safe_locals(df: pd.DataFrame) -> dict[str, Any]:
    """_build_safe_locals 构造 LLM 代码执行白名单环境"""
    return {
        "df": df,
        "pd": pd,
        "np": np,
        "plot_bar": _plot_bar,
        "plot_line": _plot_line,
        "plot_hist": _plot_hist,
        "plot_scatter": _plot_scatter,
        "plot_heatmap": _plot_heatmap,
    }


def _eval_slice(node: ast.AST, env: dict[str, Any]) -> Any:
    """_eval_slice 解释下标切片表达式"""
    if isinstance(node, ast.Slice):
        lower = _eval_node(node.lower, env) if node.lower else None
        upper = _eval_node(node.upper, env) if node.upper else None
        step = _eval_node(node.step, env) if node.step else None
        return slice(lower, upper, step)
    return _eval_node(node, env)


def _eval_attribute(node: ast.Attribute, env: dict[str, Any]) -> Any:
    """_eval_attribute 解释安全属性访问"""
    if node.attr.startswith("_"):
        raise UnsafeCodeError(f"禁止访问私有属性：{node.attr}")
    if isinstance(node.value, ast.Name) and node.value.id in ALLOWED_MODULE_ATTRS:
        if node.attr not in ALLOWED_MODULE_ATTRS[node.value.id]:
            raise UnsafeCodeError(f"模块属性不在白名单：{node.value.id}.{node.attr}")
    return getattr(_eval_node(node.value, env), node.attr)


def _call_plot_function(name: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    """_call_plot_function 调用受控绘图函数"""
    if name == "plot_bar":
        return _plot_bar(*args, **kwargs)
    if name == "plot_line":
        return _plot_line(*args, **kwargs)
    if name == "plot_hist":
        return _plot_hist(*args, **kwargs)
    if name == "plot_scatter":
        return _plot_scatter(*args, **kwargs)
    if name == "plot_heatmap":
        return _plot_heatmap(*args, **kwargs)
    raise UnsafeCodeError(f"函数不在白名单：{name}")


def _call_allowed_method(obj: Any, name: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    """_call_allowed_method 调用 pandas/numpy 白名单方法"""
    if obj is pd and name == "DataFrame":
        return pd.DataFrame(*args, **kwargs)
    if obj is pd and name == "Series":
        return pd.Series(*args, **kwargs)
    if obj is pd and name == "crosstab":
        return pd.crosstab(*args, **kwargs)
    if obj is pd and name == "pivot_table":
        return pd.pivot_table(*args, **kwargs)
    if obj is np and name == "abs":
        return np.abs(*args, **kwargs)
    if obj is np and name == "clip":
        return np.clip(*args, **kwargs)
    if obj is np and name == "log":
        return np.log(*args, **kwargs)
    if obj is np and name == "mean":
        return np.mean(*args, **kwargs)
    if obj is np and name == "median":
        return np.median(*args, **kwargs)
    if obj is np and name == "round":
        return np.round(*args, **kwargs)
    if obj is np and name == "sqrt":
        return np.sqrt(*args, **kwargs)
    if obj is np and name == "where":
        return np.where(*args, **kwargs)
    if name == "abs":
        return obj.abs(*args, **kwargs)
    if name == "agg":
        return obj.agg(*args, **kwargs)
    if name == "assign":
        return obj.assign(*args, **kwargs)
    if name == "copy":
        return obj.copy(*args, **kwargs)
    if name == "corr":
        return obj.corr(*args, **kwargs)
    if name == "count":
        return obj.count(*args, **kwargs)
    if name == "dropna":
        return obj.dropna(*args, **kwargs)
    if name == "fillna":
        return obj.fillna(*args, **kwargs)
    if name == "groupby":
        return obj.groupby(*args, **kwargs)
    if name == "head":
        return obj.head(*args, **kwargs)
    if name == "idxmax":
        return obj.idxmax(*args, **kwargs)
    if name == "idxmin":
        return obj.idxmin(*args, **kwargs)
    if name == "max":
        return obj.max(*args, **kwargs)
    if name == "mean":
        return obj.mean(*args, **kwargs)
    if name == "median":
        return obj.median(*args, **kwargs)
    if name == "min":
        return obj.min(*args, **kwargs)
    if name == "nlargest":
        return obj.nlargest(*args, **kwargs)
    if name == "nsmallest":
        return obj.nsmallest(*args, **kwargs)
    if name == "pivot_table":
        return obj.pivot_table(*args, **kwargs)
    if name == "query":
        return obj.query(*args, **kwargs)
    if name == "rename":
        return obj.rename(*args, **kwargs)
    if name == "reset_index":
        return obj.reset_index(*args, **kwargs)
    if name == "round":
        return obj.round(*args, **kwargs)
    if name == "set_index":
        return obj.set_index(*args, **kwargs)
    if name == "sort_index":
        return obj.sort_index(*args, **kwargs)
    if name == "sort_values":
        return obj.sort_values(*args, **kwargs)
    if name == "sum":
        return obj.sum(*args, **kwargs)
    if name == "tail":
        return obj.tail(*args, **kwargs)
    if name == "to_frame":
        return obj.to_frame(*args, **kwargs)
    if name == "value_counts":
        return obj.value_counts(*args, **kwargs)
    raise UnsafeCodeError(f"方法不在白名单：{name}")


def _eval_call(node: ast.Call, env: dict[str, Any]) -> Any:
    """_eval_call 解释安全函数或方法调用"""
    args = [_eval_node(arg, env) for arg in node.args]
    kwargs = {kw.arg: _eval_node(kw.value, env) for kw in node.keywords if kw.arg is not None}
    if isinstance(node.func, ast.Attribute):
        if not isinstance(node.func.value, ast.Name) and node.func.attr not in ALLOWED_METHODS:
            raise UnsafeCodeError(f"方法不在白名单：{node.func.attr}")
        obj = _eval_node(node.func.value, env)
        return _call_allowed_method(obj, node.func.attr, args, kwargs)
    elif isinstance(node.func, ast.Name):
        if node.func.id not in env or not node.func.id.startswith("plot_"):
            raise UnsafeCodeError(f"函数不在白名单：{node.func.id}")
        return _call_plot_function(node.func.id, args, kwargs)
    else:
        raise UnsafeCodeError("禁止复杂函数调用")


def _eval_compare(node: ast.Compare, env: dict[str, Any]) -> Any:
    """_eval_compare 解释比较表达式"""
    left = _eval_node(node.left, env)
    for op, comparator in zip(node.ops, node.comparators):
        right = _eval_node(comparator, env)
        if isinstance(op, ast.Eq):
            left = left == right
        elif isinstance(op, ast.NotEq):
            left = left != right
        elif isinstance(op, ast.Gt):
            left = left > right
        elif isinstance(op, ast.GtE):
            left = left >= right
        elif isinstance(op, ast.Lt):
            left = left < right
        elif isinstance(op, ast.LtE):
            left = left <= right
        else:
            raise UnsafeCodeError("比较运算不在白名单")
    return left


def _eval_binop(node: ast.BinOp, env: dict[str, Any]) -> Any:
    """_eval_binop 解释基础二元运算"""
    left = _eval_node(node.left, env)
    right = _eval_node(node.right, env)
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Mult):
        return left * right
    if isinstance(node.op, ast.Div):
        return left / right
    if isinstance(node.op, ast.BitAnd):
        return left & right
    if isinstance(node.op, ast.BitOr):
        return left | right
    raise UnsafeCodeError("二元运算不在白名单")


def _eval_node(node: ast.AST | None, env: dict[str, Any]) -> Any:
    """_eval_node 递归解释白名单 AST 节点"""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise UnsafeCodeError(f"变量不在白名单：{node.id}")
        return env[node.id]
    if isinstance(node, ast.List):
        return [_eval_node(item, env) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(item, env) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {_eval_node(k, env): _eval_node(v, env) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Attribute):
        return _eval_attribute(node, env)
    if isinstance(node, ast.Subscript):
        return _eval_node(node.value, env)[_eval_slice(node.slice, env)]
    if isinstance(node, ast.Call):
        return _eval_call(node, env)
    if isinstance(node, ast.Compare):
        return _eval_compare(node, env)
    if isinstance(node, ast.BinOp):
        return _eval_binop(node, env)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, env)
    raise UnsafeCodeError(f"表达式类型不在白名单：{type(node).__name__}")


def _run_safe_assignments(code: str, env: dict[str, Any]) -> None:
    """_run_safe_assignments 执行仅包含赋值语句的白名单 AST"""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise UnsafeCodeError(f"生成代码语法不完整：{exc.msg}") from exc
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            raise UnsafeCodeError("仅允许简单赋值语句")
        target = stmt.targets[0].id
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", target) or target in PROTECTED_NAMES:
            raise UnsafeCodeError(f"赋值目标不在白名单：{target}")
        env[target] = _eval_node(stmt.value, env)


def _generate_safe_code(
    client: LLMClient,
    df: pd.DataFrame,
    question: str,
    system_prompt: str,
    enable_chart: bool,
    dataset_description: str = "",
) -> str:
    """_generate_safe_code 调用 LLM 并在代码不合规时自动重试"""
    user_prompt = build_prompt(df, question, enable_chart, dataset_description)
    last_error = ""
    last_code = ""
    for _ in range(LLM_QA_MAX_RETRIES):
        prompt = user_prompt
        if last_error:
            prompt += (
                "\n\n上一次输出不合规，请重新输出完整 Python 代码。"
                f"\n错误信息：{last_error}"
                f"\n上一次输出：\n{last_code}"
                "\n要求：必须包含 `answer = ...`，不要解释，不要省略，不要截断。"
            )
        raw = client.chat(system_prompt, prompt, temperature=0.0, max_tokens=LLM_QA_CODE_MAX_TOKENS)
        code = _strip_code_fence(raw)
        try:
            _validate(code)
            return code
        except (UnsafeCodeError, SyntaxError) as exc:
            last_error = str(exc)
            last_code = code
    raise UnsafeCodeError(f"LLM 连续生成不合规代码：{last_error}")


def run_query(
    question: str,
    dataset: Path | None = DEFAULT_DATASET,
    enable_chart: bool = False,
    dataset_label: str = "",
    dataset_description: str = "",
    save_chart: bool = False,
) -> dict[str, Any]:
    """run_query 单次问答主流程
    1. 加载数据集；
    2. 调用 LLM；
    3. 校验并执行代码；
    4. 返回 question/code/result/chart。
    """
    # 1. 自动路由或加载指定数据源
    routed_dataset: dict[str, Any] | None = None
    if dataset is None:
        routed_dataset = recommend_dataset(question)
        dataset = routed_dataset["path"]
        dataset_label = routed_dataset["label"]
        dataset_description = routed_dataset["description"]
    if not dataset.exists():
        raise FileNotFoundError(f"未找到问答数据集：{dataset}")
    df = pd.read_csv(dataset)

    # 2. 调用 LLM 生成安全代码并执行
    client = LLMClient()
    system_prompt = SYSTEM_PROMPT_QA_MULTIMODAL if enable_chart else SYSTEM_PROMPT_QA
    code = _generate_safe_code(client, df, question, system_prompt, enable_chart, dataset_description)
    safe_locals = _build_safe_locals(df)
    _run_safe_assignments(code, safe_locals)
    chart_figure = safe_locals.get("chart")
    chart_title = safe_locals.get("chart_title", "自动生成图表")
    chart_path = save_chart_figure(chart_figure, chart_title) if save_chart and chart_figure else None
    return {
        "question": question,
        "code": code,
        "result": safe_locals.get("answer"),
        "chart_figure": chart_figure,
        "chart_title": chart_title,
        "chart_note": safe_locals.get("chart_note", ""),
        "chart_path": chart_path,
        "dataset": dataset.name,
        "dataset_label": dataset_label or dataset.name,
        "dataset_route_score": routed_dataset.get("route_score") if routed_dataset else None,
        "matched_keywords": routed_dataset.get("matched_keywords", []) if routed_dataset else [],
    }


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    parser = argparse.ArgumentParser(description="LLM 自然语言问答与自动出图")
    parser.add_argument("question", help="用户问题，如：违约率最高的 5 个州是哪些？")
    parser.add_argument("--dataset", type=Path, default=None, help="不传则按问题自动推荐数据源")
    parser.add_argument("--chart", action="store_true", help="允许 LLM 调用受控绘图函数并返回自动图表")
    args = parser.parse_args()
    out = run_query(args.question, args.dataset, enable_chart=args.chart, save_chart=args.chart)
    print(f"\n>>> 生成代码：\n{out['code']}\n")
    print(f">>> 执行结果：\n{out['result']}")
    if out.get("chart_figure"):
        print(">>> 已生成图表（Dashboard 中可直接展示）")
    if out.get("chart_path"):
        print(f">>> 图表路径：{out['chart_path']}")
    if out.get("chart_note"):
        print(f">>> 图表说明：{out['chart_note']}")


if __name__ == "__main__":
    main()
