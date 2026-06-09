"""llm/llm_decision_explainer.py 单笔贷款决策解释生成器

1. 给定 application_id，从 decision_logs.json 取出该笔贷款特征 + 模型预测概率 + 决策结果；
2. 关联全局特征重要性、反事实最小改变量证据；
3. 由 LLM 输出"为什么拒/批 + 可执行改善建议"的自然语言解释。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import SYSTEM_PROMPT_DECISION_EXPLAIN  # noqa: E402
from constant.paths import (  # noqa: E402
    COUNTERFACTUAL_MIN_CHANGE_CSV,
    DECISION_LOGS_JSON,
    MODEL_FEATURE_IMPORTANCE_CSV,
)
from common.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def load_decision_logs() -> list[dict[str, Any]]:
    """load_decision_logs 读取决策追溯日志列表"""
    if not DECISION_LOGS_JSON.exists():
        raise FileNotFoundError(f"找不到决策日志：{DECISION_LOGS_JSON}")
    return json.loads(DECISION_LOGS_JSON.read_text(encoding="utf-8"))


def list_application_ids() -> list[str]:
    """list_application_ids 返回所有可解释的 application_id 列表"""
    return [item["application_id"] for item in load_decision_logs()]


def _find_record(application_id: str, logs: list[dict[str, Any]]) -> dict[str, Any]:
    """_find_record 在日志中按 application_id 精确匹配单笔申请"""
    for record in logs:
        if record["application_id"] == application_id:
            return record
    raise KeyError(f"application_id 不存在：{application_id}")


def _top_global_importance(model: str = "xgboost", top_k: int = 6) -> pd.DataFrame:
    """_top_global_importance 取全局 Top 特征重要性，作为风险因子参考"""
    if not MODEL_FEATURE_IMPORTANCE_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(MODEL_FEATURE_IMPORTANCE_CSV)
    if "model" in df.columns:
        df = df[df["model"] == model]
    if df.empty:
        df = pd.read_csv(MODEL_FEATURE_IMPORTANCE_CSV)
    return df.sort_values("importance", ascending=False).head(top_k).reset_index(drop=True)


def _counterfactual_evidence(top_k: int = 5) -> pd.DataFrame:
    """_counterfactual_evidence 取反事实最小改变量证据"""
    if not COUNTERFACTUAL_MIN_CHANGE_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(COUNTERFACTUAL_MIN_CHANGE_CSV)
    return df.head(top_k)


def _format_features(features: dict[str, Any], max_items: int = 12) -> str:
    """_format_features 抽取关键特征拼装为可读片段，避免一次塞入过多原始字段"""
    priority = [
        "loan_amnt",
        "int_rate",
        "annual_inc",
        "dti",
        "fico_avg",
        "term_months",
        "installment",
        "revol_util",
        "delinq_2yrs",
        "grade",
        "purpose",
        "home_ownership",
        "emp_length",
        "verification_status",
    ]
    rows: list[str] = []
    for key in priority:
        if key in features and features[key] is not None:
            rows.append(f"- {key}: {features[key]}")
        if len(rows) >= max_items:
            break
    return "\n".join(rows) if rows else "（无可用特征）"


def explain(application_id: str) -> dict[str, Any]:
    """explain 生成单笔贷款的自然语言决策解释"""
    # 1. 取出决策日志中的目标申请
    logs = load_decision_logs()
    record = _find_record(application_id, logs)
    decision = record.get("decision", "")
    probability = record.get("probability", 0.0)
    threshold = record.get("threshold", 0.5)
    rules = record.get("rules", [])
    feature_text = _format_features(record.get("features", {}))
    # 2. 拼装全局特征重要性与反事实证据
    importance_df = _top_global_importance()
    cf_df = _counterfactual_evidence()
    importance_text = (
        importance_df.to_string(index=False)
        if not importance_df.empty
        else "（无全局特征重要性）"
    )
    cf_text = (
        cf_df.to_string(index=False)
        if not cf_df.empty
        else "（无反事实证据）"
    )
    # 3. 构造 prompt 并调用 LLM
    user_prompt = (
        f"# 单笔贷款审批解释\n"
        f"申请编号：{application_id}\n"
        f"模型预测违约概率：{probability:.4f}\n"
        f"风控阈值：{threshold}\n"
        f"最终决策：{decision}\n"
        f"命中规则：{rules or '无'}\n\n"
        f"## 关键特征\n{feature_text}\n\n"
        f"## 全局特征重要性（仅供参考，越大越关键）\n{importance_text}\n\n"
        f"## 反事实最小改变量证据\n{cf_text}\n"
    )
    client = LLMClient()
    text = client.chat(SYSTEM_PROMPT_DECISION_EXPLAIN, user_prompt, temperature=0.2, max_tokens=900)
    # 4. 返回结构化结果，便于 Dashboard 复用
    return {
        "application_id": application_id,
        "decision": decision,
        "probability": probability,
        "threshold": threshold,
        "rules": rules,
        "features": record.get("features", {}),
        "explanation": text.strip(),
    }


def main():
    """main CLI 入口：解释一笔指定 application_id 的决策"""
    parser = argparse.ArgumentParser()
    parser.add_argument("application_id", type=str, help="贷款申请编号，如 APP_000003")
    args = parser.parse_args()
    result = explain(args.application_id)
    print(f"=== {result['application_id']} ===")
    print(
        f"决策：{result['decision']} | 概率：{result['probability']:.4f} | "
        f"阈值：{result['threshold']}"
    )
    print(result["explanation"])


if __name__ == "__main__":
    main()
