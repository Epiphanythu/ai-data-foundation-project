"""llm/llm_auto_report.py LLM 自动生成分析报告
1. 读取核心分析产物（lc_overview、各维度违约率、模型指标、宏观相关性）；
2. 拼装结构化 Prompt 喂给 LLM；
3. 落盘生成报告 markdown。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constant.llm import SYSTEM_PROMPT_REPORT  # noqa: E402
from constant.paths import (  # noqa: E402
    LLM_AUTO_REPORT_MD,
    STATE_AWARE_DYNAMIC_STRATEGY_CSV,
    STATE_AWARE_MODEL_VALIDATION_CSV,
    STATE_AWARE_RISK_SUMMARY_CSV,
    MODEL_METRICS_CSV,
    REPORTS_DIR,
    TABLES_DIR,
)
from common.llm_client import LLMClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 报告所需的关键数据文件
REPORT_INPUTS = {
    "总览": TABLES_DIR / "lc_overview.csv",
    "各等级违约率": TABLES_DIR / "lc_default_by_grade.csv",
    "各利率分箱违约率": TABLES_DIR / "lc_default_by_interest_bin.csv",
    "FICO 分箱违约率": TABLES_DIR / "lc_default_by_fico_bin.csv",
    "各贷款用途违约率": TABLES_DIR / "lc_default_by_purpose_min1000.csv",
    "组合风险（Grade×Purpose）": TABLES_DIR / "lc_segment_grade_purpose.csv",
    "FRED 季度相关性": TABLES_DIR / "lc_fred_quarterly_correlations.csv",
    "ERS 州级相关性": TABLES_DIR / "lc_ers_state_correlations.csv",
    "状态感知宏观风险": STATE_AWARE_RISK_SUMMARY_CSV,
    "状态感知模型验证": STATE_AWARE_MODEL_VALIDATION_CSV,
    "状态感知动态阈值策略": STATE_AWARE_DYNAMIC_STRATEGY_CSV,
}


def load_table_snippet(path: Path, max_rows: int = 12) -> str:
    """load_table_snippet 读取 CSV 头部并转为纯文本表格"""
    if not path.exists():
        return f"_缺失：{path.name}_"
    df = pd.read_csv(path).head(max_rows)
    return df.to_string(index=False)


def build_user_prompt() -> str:
    """build_user_prompt 拼装用于 LLM 的输入上下文"""
    sections: list[str] = ["以下是分析结果汇总，请基于这些指标撰写报告：", ""]
    for title, path in REPORT_INPUTS.items():
        sections.append(f"### {title}（来源：{path.name}）")
        sections.append(load_table_snippet(path))
        sections.append("")
    if MODEL_METRICS_CSV.exists():
        sections.append("### 模型基准指标")
        sections.append(load_table_snippet(MODEL_METRICS_CSV))
        sections.append("")
    sections.extend(
        [
            "### 报告要求",
            "1. 分五节：① 数据概览 ② 个体风险特征 ③ 宏观状态风险 ④ 模型验证 ⑤ 动态策略建议；",
            "2. 每节给出 2-4 条带量化数字的核心结论；",
            "3. 重点说明宏观状态、模型增益、动态阈值和坏账/利润权衡；",
            "4. 末尾给出 3 条可执行的风控/产品建议；",
            "5. 不要编造未提供的数字。",
        ]
    )
    return "\n".join(sections)


def run(output_path: Path = LLM_AUTO_REPORT_MD):
    """run 生成自动报告主流程"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    user_prompt = build_user_prompt()
    logger.info("Sending prompt to LLM (%d chars) ...", len(user_prompt))
    client = LLMClient()
    content = client.chat(SYSTEM_PROMPT_REPORT, user_prompt, temperature=0.2, max_tokens=6000)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Saved %s (%d chars)", output_path, len(content))
    return content


def main():
    """脚本入口函数，按预定顺序调度当前文件的完整处理流程。"""
    parser = argparse.ArgumentParser(description="LLM 自动生成项目分析报告")
    parser.add_argument("--output", type=Path, default=LLM_AUTO_REPORT_MD)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
