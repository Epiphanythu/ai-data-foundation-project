from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

SCRIPTS = [
    "src/run_midterm_pipeline.py",
    "scripts/analyze_lending_club.py",
    "scripts/build_fred_macro_features.py",
    "scripts/build_ers_state_features.py",
    "scripts/build_lc_risk_segments.py",
    "scripts/build_state_control_analysis.py",
    "scripts/build_quarterly_macro_analysis.py",
]

CORE_OUTPUTS = [
    ("Lending Club 总览", "outputs/tables/lc_overview.csv"),
    ("Lending Club 关键发现", "outputs/tables/lc_findings.md"),
    ("组合风险分层发现", "outputs/tables/lc_segment_findings.md"),
    ("FRED 年度宏观融合发现", "outputs/tables/fred_macro_findings.md"),
    ("FRED 季度宏观融合发现", "outputs/tables/fred_quarterly_findings.md"),
    ("ERS 州级经济融合发现", "outputs/tables/ers_state_findings.md"),
    ("州级控制变量发现", "outputs/tables/lc_state_control_findings.md"),
    ("数据处理进度报告", "outputs/tables/progress_report.md"),
]

KEY_FIGURES = [
    "outputs/figures/lc_default_rate_by_grade.png",
    "outputs/figures/lc_default_rate_by_interest_bin.png",
    "outputs/figures/lc_default_rate_by_fico_bin.png",
    "outputs/figures/lc_default_rate_top_states.png",
    "outputs/figures/lc_default_rate_by_purpose.png",
    "outputs/figures/lc_top_risk_grade_purpose_segments.png",
    "outputs/figures/lc_fred_quarterly_overlay.png",
    "outputs/figures/lc_state_default_residual_interest_vs_poverty.png",
]


def run(script):
    print(f"\n>>> running {script}")
    result = subprocess.run([sys.executable, script], cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit(f"{script} failed with exit code {result.returncode}")


def file_size(path):
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def generate_index():
    lines = [
        "# 分析产物索引",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 核心发现文档",
        "",
        "| 名称 | 路径 | 大小 |",
        "|---|---|---|",
    ]
    for name, rel in CORE_OUTPUTS:
        path = ROOT / rel
        lines.append(f"| {name} | `{rel}` | {file_size(path)} |")

    table_files = sorted(TABLES.glob("*.csv"))
    lines.extend(["", "## CSV 统计表", "", "| 文件 | 大小 |", "|---|---| "])
    for path in table_files:
        lines.append(f"| `{path.relative_to(ROOT)}` | {file_size(path)} |")

    figure_files = sorted(FIGURES.glob("*.png"))
    lines.extend(["", "## 图表", "", "| 文件 | 大小 | 用途 |", "|---|---|---| "])
    key_set = {str(Path(p)) for p in KEY_FIGURES}
    for path in figure_files:
        rel = str(path.relative_to(ROOT))
        use = "核心汇报图" if rel in key_set else "补充分析图"
        lines.append(f"| `{rel}` | {file_size(path)} | {use} |")

    lines.extend(
        [
            "",
            "## 建议汇报主线",
            "",
            "1. 先展示 Lending Club 数据规模、标签过滤和总体违约率。",
            "2. 再展示等级、利率、FICO 等个体风险梯度。",
            "3. 接着展示用途、期限、组合分层，说明高风险人群可被进一步细分。",
            "4. 最后展示 FRED/ERS 多源融合，说明宏观和地区经济变量如何进入解释框架。",
            "",
            "## 一键复现命令",
            "",
            "```bash",
            "python3 scripts/run_all_analysis.py",
            "```",
        ]
    )
    out = TABLES / "analysis_index.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {out}")


def main():
    for script in SCRIPTS:
        run(script)
    generate_index()


if __name__ == "__main__":
    main()
