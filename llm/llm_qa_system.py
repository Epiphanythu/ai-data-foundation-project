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

# DENIED_METHODS 反向黑名单：除以下方法外，pandas / numpy 公共方法默认放行
# 1. IO 类：会触发文件 / 网络 / 数据库写入
# 2. 反射 / 可执行类：能塞任意 lambda 或字符串表达式逃逸沙箱
DENIED_METHODS = {
    # 1. IO / 文件 / 网络
    "to_csv", "to_excel", "to_json", "to_pickle", "to_sql", "to_parquet",
    "to_feather", "to_hdf", "to_orc", "to_stata", "to_xml", "to_clipboard",
    "read_csv", "read_excel", "read_json", "read_pickle", "read_sql",
    "read_parquet", "read_feather", "read_hdf", "read_orc", "read_stata",
    "read_xml", "read_html", "read_clipboard", "read_table",
    # 2. 反射 / 可执行
    "apply", "applymap", "pipe", "transform", "agg_apply", "eval", "query_eval",
    "map", "aggregate",
}

# DENIED_MODULE_ATTRS 模块层禁用清单：仅禁危险入口，其它 pd/np 公共属性默认放行
DENIED_MODULE_ATTRS = {
    "pd": {
        "read_csv", "read_excel", "read_json", "read_pickle", "read_sql",
        "read_parquet", "read_feather", "read_hdf", "read_orc", "read_stata",
        "read_xml", "read_html", "read_clipboard", "read_table",
        "ExcelFile", "ExcelWriter", "HDFStore",
        "eval",
    },
    "np": {
        "load", "loadtxt", "save", "savez", "savez_compressed", "savetxt",
        "fromfile", "memmap", "genfromtxt",
    },
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
    """_build_safe_locals 构造 LLM 代码执行的受控初始命名空间"""
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


# ---------------------------------------------------------------------------
# AST 黑名单：仅枚举危险结构，其它 Python 语法默认放行
# 1. 危险语句：import / def / class / yield / await / global / nonlocal / lambda
# 2. 危险上下文：with / try / async-*（open() 也通过 safe_builtins 屏蔽）
# 3. 危险属性 / 名字：以 _ 开头的 dunder 与私有属性（防止 __subclasses__ 逃逸）
# ---------------------------------------------------------------------------
FORBIDDEN_AST_NODES: tuple[type[ast.AST], ...] = (
    ast.Import,
    ast.ImportFrom,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.AsyncFor,
    ast.Try,
    ast.Raise,
    ast.Delete,
)


def _scan_ast_blocklist(tree: ast.AST) -> None:
    """_scan_ast_blocklist 遍历 AST，仅拦截黑名单节点与私有属性 / 名字
    1. 禁止任何 import / def / class / lambda / yield / await / with / try
    2. 禁止访问以 _ 开头的属性 / 名字（屏蔽 __subclasses__ 等 dunder 逃逸）
    3. 禁止调用形如 obj.method 时方法名命中 DENIED_METHODS
    """
    for node in ast.walk(tree):
        # 1. 危险语句结构
        if isinstance(node, FORBIDDEN_AST_NODES):
            raise UnsafeCodeError(f"禁止使用语法：{type(node).__name__}")
        # 2. 私有 / dunder 属性访问
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise UnsafeCodeError(f"禁止访问私有属性：{node.attr}")
        # 3. 引用 _ 开头的名字（如 __builtins__）
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise UnsafeCodeError(f"禁止访问私有名字：{node.id}")
        # 4. 模块层危险入口（pd.read_csv / np.load 等）
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            mod = node.value.id
            if mod in DENIED_MODULE_ATTRS and node.attr in DENIED_MODULE_ATTRS[mod]:
                raise UnsafeCodeError(f"模块属性已禁用：{mod}.{node.attr}")
        # 5. 方法调用反射类 / IO 类禁用名单
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in DENIED_METHODS:
                raise UnsafeCodeError(f"方法已禁用：{node.func.attr}")


# 受限 builtins：仅放行无副作用的纯函数；屏蔽 __import__ / open / eval / exec /
# compile / globals / vars / locals / getattr / setattr / delattr / __build_class__
_SAFE_BUILTINS_NAMES = {
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "int", "len", "list", "map", "max", "min",
    "print", "range", "reversed", "round", "set", "slice", "sorted", "str",
    "sum", "tuple", "type", "zip", "isinstance", "issubclass",
}


def _build_safe_builtins() -> dict[str, Any]:
    """_build_safe_builtins 构造受限 builtins 命名空间"""
    import builtins as _builtins
    return {name: getattr(_builtins, name) for name in _SAFE_BUILTINS_NAMES if hasattr(_builtins, name)}



def _run_safe_assignments(code: str, env: dict[str, Any]) -> None:
    """_run_safe_assignments 黑名单扫描后用受限 builtins exec 执行 LLM 代码
    1. AST 黑名单扫描：禁 import / def / class / lambda / yield / await / with / try / 私有属性
    2. 模块层 / 方法层禁用名单：屏蔽 pd.read_csv / df.apply / df.eval 等
    3. 受限 builtins：屏蔽 __import__ / open / eval / exec / compile / globals / getattr 等
    4. exec 在受控命名空间内执行；执行后 env 即包含 answer 等结果
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise UnsafeCodeError(f"生成代码语法不完整：{exc.msg}") from exc
    _scan_ast_blocklist(tree)
    # 1. 禁止覆盖受保护变量（df / pd / np / plot_*）
    for stmt in tree.body:
        targets: list[ast.expr] = []
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)):
            targets = [stmt.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id in PROTECTED_NAMES:
                raise UnsafeCodeError(f"禁止覆盖受保护变量：{target.id}")
    # 2. 受限命名空间执行
    sandbox_globals: dict[str, Any] = {"__builtins__": _build_safe_builtins()}
    sandbox_globals.update(env)
    exec(compile(tree, filename="<llm_qa>", mode="exec"), sandbox_globals)  # noqa: S102
    # 3. 把执行结果回写到 env（仅同步用户新增 / 修改的变量）
    for key, value in sandbox_globals.items():
        if key == "__builtins__":
            continue
        env[key] = value


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


def load_qa_dataset(dataset: Path) -> pd.DataFrame:
    """load_qa_dataset 读取 CSV/JSON 问答数据源并统一转成 DataFrame"""
    if dataset.suffix.lower() == ".json":
        raw = pd.read_json(dataset)
        if "features" in raw.columns:
            feature_frame = pd.json_normalize(raw["features"]).add_prefix("feature_")
            raw = pd.concat([raw.drop(columns=["features"]), feature_frame], axis=1)
        if "rules" in raw.columns:
            raw["rules"] = raw["rules"].apply(lambda value: "、".join(map(str, value)) if isinstance(value, list) else value)
        return raw
    return pd.read_csv(dataset)


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
    df = load_qa_dataset(dataset)

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
