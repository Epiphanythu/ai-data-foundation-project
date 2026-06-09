"""llm/llm_agent.py LLM Agent 智能助手

1. 通过 OpenAI function calling 协议自动选择三类工具：
   - qa_table：在结构化数据集上做 pandas 查询/出图；
   - rag_search：在项目分析文档中检索证据并引用作答；
   - explain_decision：解释单笔贷款审批结果及改善建议；
2. 由 LLM 自主路由，最多迭代 max_steps 轮；
3. 返回完整的工具调用轨迹，便于 Dashboard 可视化展示推理链路。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import LLM_AGENT_TOOLS, SYSTEM_PROMPT_AGENT  # noqa: E402
from common.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

AGENT_MAX_STEPS = 4


def _serialize_qa_result(qa_result: dict[str, Any]) -> str:
    """_serialize_qa_result 将问答结果压缩成 LLM 可消费的纯文本"""
    pieces: list[str] = []
    pieces.append(f"数据源：{qa_result.get('dataset_label') or qa_result.get('dataset')}")
    pieces.append(f"生成代码：\n{qa_result.get('code', '')}")
    answer = qa_result.get("result")
    if hasattr(answer, "to_string"):
        pieces.append(f"answer 输出：\n{answer.to_string()}")
    else:
        pieces.append(f"answer 输出：{answer}")
    if qa_result.get("chart_note"):
        pieces.append(f"图表说明：{qa_result['chart_note']}")
    return "\n\n".join(pieces)


def _serialize_rag_result(rag_result: dict[str, Any]) -> str:
    """_serialize_rag_result 将 RAG 答案 + 证据列表压缩为纯文本"""
    pieces: list[str] = [f"RAG 回答：{rag_result.get('answer', '')}"]
    for item in rag_result.get("evidence", []):
        snippet = item["snippet"][:300].replace("\n", " ")
        pieces.append(f"[{item['index']}] {item['source']} (score={item['score']:.3f}): {snippet}")
    return "\n".join(pieces)


def _serialize_explain_result(explain_result: dict[str, Any]) -> str:
    """_serialize_explain_result 将单笔决策解释结果序列化"""
    head = (
        f"申请编号 {explain_result['application_id']} | 决策 {explain_result['decision']} | "
        f"概率 {explain_result['probability']:.4f} | 阈值 {explain_result['threshold']}"
    )
    return f"{head}\n\n{explain_result.get('explanation', '')}"


def _execute_tool(name: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """_execute_tool 路由具体工具执行并返回 (LLM 用文本, 原始结构化结果)"""
    # 1. 结构化查询/出图
    if name == "qa_table":
        from llm.llm_qa_system import run_query

        question = arguments.get("question", "")
        enable_chart = bool(arguments.get("enable_chart", False))
        result = run_query(
            question=question,
            dataset=None,
            enable_chart=enable_chart,
            save_chart=False,
        )
        # 2. 图表对象不能 JSON 序列化，提供文本摘要给 LLM，结构化结果保留给 Dashboard
        return _serialize_qa_result(result), result
    # 2. 文档检索
    if name == "rag_search":
        from llm.llm_rag import answer as rag_answer

        question = arguments.get("question", "")
        result = rag_answer(question)
        return _serialize_rag_result(result), result
    # 3. 单笔决策解释
    if name == "explain_decision":
        from llm.llm_decision_explainer import explain

        application_id = arguments.get("application_id", "")
        result = explain(application_id)
        return _serialize_explain_result(result), result
    raise ValueError(f"未知工具：{name}")


def run_agent(question: str, max_steps: int = AGENT_MAX_STEPS) -> dict[str, Any]:
    """run_agent 多轮 function calling 编排，返回最终回答与工具轨迹"""
    # 1. 初始化对话上下文
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT_AGENT},
        {"role": "user", "content": question},
    ]
    client = LLMClient()
    trace: list[dict[str, Any]] = []
    final_text = ""
    # 2. 多轮迭代直到模型给出最终回答或达到上限
    for step in range(max_steps):
        message = client.chat_with_tools(
            messages=messages,
            tools=LLM_AGENT_TOOLS,
            temperature=0.1,
            max_tokens=900,
        )
        tool_calls = getattr(message, "tool_calls", None) or []
        # 2.1 没有工具调用则视为最终回答
        if not tool_calls:
            final_text = (message.content or "").strip()
            trace.append({"step": step, "type": "final", "content": final_text})
            messages.append({"role": "assistant", "content": final_text})
            break
        # 2.2 把当前 assistant 消息（含 tool_calls）追加进上下文
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            }
        )
        # 2.3 串行执行每一个工具调用
        for call in tool_calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            try:
                tool_text, tool_payload = _execute_tool(name, arguments)
                error = ""
            except Exception as exc:  # noqa: BLE001
                tool_text = f"工具执行失败：{exc}"
                tool_payload = {"error": str(exc)}
                error = str(exc)
            trace.append(
                {
                    "step": step,
                    "type": "tool",
                    "tool": name,
                    "arguments": arguments,
                    "result_text": tool_text,
                    "result_payload": tool_payload,
                    "error": error,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": tool_text,
                }
            )
    else:
        # 3. 达到 max_steps 仍未收敛时强制让 LLM 给一个总结
        message = client.chat_with_tools(
            messages=messages + [
                {"role": "user", "content": "请基于以上工具结果给出最终中文回答，不要再调用工具。"}
            ],
            tools=LLM_AGENT_TOOLS,
            tool_choice="none",
            temperature=0.1,
            max_tokens=600,
        )
        final_text = (message.content or "").strip()
        trace.append({"step": max_steps, "type": "final", "content": final_text})
    return {
        "question": question,
        "answer": final_text,
        "trace": trace,
    }


def main():
    """main CLI 入口，便于命令行单次调用 Agent"""
    parser = argparse.ArgumentParser()
    parser.add_argument("question", type=str, help="自然语言问题")
    parser.add_argument("--max-steps", type=int, default=AGENT_MAX_STEPS)
    args = parser.parse_args()
    result = run_agent(args.question, max_steps=args.max_steps)
    print("Q:", result["question"])
    print("A:", result["answer"])
    print("\nTrace:")
    for item in result["trace"]:
        if item["type"] == "tool":
            print(f"  [{item['step']}] tool={item['tool']} args={item['arguments']}")
        else:
            print(f"  [{item['step']}] final")


if __name__ == "__main__":
    main()
