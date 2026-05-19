from collections import defaultdict
from csv import DictReader, DictWriter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "external"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

GOOD_STATUSES = {"Fully Paid"}
BAD_STATUSES = {
    "Charged Off",
    "Default",
    "Late (31-120 days)",
    "Does not meet the credit policy. Status:Charged Off",
}
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def find_lending_club_csv():
    for path in sorted(RAW.rglob("accepted_2007_to_2018Q4.csv")):
        if path.is_file():
            return path
    raise FileNotFoundError("未找到 Lending Club accepted CSV")


def parse_float(value):
    if value in (None, "", "."):
        return None
    try:
        return float(str(value).replace("%", ""))
    except ValueError:
        return None


def outcome(status):
    if status in GOOD_STATUSES:
        return 0
    if status in BAD_STATUSES:
        return 1
    return None


def issue_quarter(value):
    if not value or "-" not in value:
        return None
    month, year = value.split("-", 1)
    m = MONTHS.get(month)
    if not m:
        return None
    q = (m - 1) // 3 + 1
    return f"{year}-Q{q}"


def obs_quarter(value):
    year, month, _ = value.split("-")
    q = (int(month) - 1) // 3 + 1
    return f"{year}-Q{q}"


def write_csv(path, rows, fieldnames=None):
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def corr(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 2:
        return ""
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = sum((x - mx) ** 2 for x in xs) ** 0.5
    deny = sum((y - my) ** 2 for y in ys) ** 0.5
    return round(num / (denx * deny), 4) if denx and deny else ""


def lc_quarterly():
    buckets = defaultdict(lambda: {"loan_count": 0, "default_count": 0})
    path = find_lending_club_csv()
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in DictReader(f):
            default_flag = outcome(row.get("loan_status", ""))
            if default_flag is None:
                continue
            quarter = issue_quarter(row.get("issue_d"))
            if not quarter:
                continue
            buckets[quarter]["loan_count"] += 1
            buckets[quarter]["default_count"] += default_flag
    rows = []
    for quarter, value in sorted(buckets.items()):
        rows.append(
            {
                "issue_quarter": quarter,
                "loan_count": value["loan_count"],
                "default_count": value["default_count"],
                "default_rate": round(value["default_count"] / value["loan_count"], 4),
            }
        )
    return rows


def fred_quarterly():
    path = DATA / "fred_macro_monthly.csv"
    if not path.exists():
        raise FileNotFoundError("缺少 FRED 月度数据，请先运行 scripts/build_fred_macro_features.py")
    buckets = defaultdict(lambda: {"FEDFUNDS": [], "UNRATE": [], "CPIAUCSL": []})
    with path.open(newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            quarter = obs_quarter(row["observation_date"])
            for col in ["FEDFUNDS", "UNRATE", "CPIAUCSL"]:
                value = parse_float(row.get(col))
                if value is not None:
                    buckets[quarter][col].append(value)
    rows = []
    previous_cpi = None
    for quarter in sorted(buckets):
        bucket = buckets[quarter]
        if not bucket["FEDFUNDS"] or not bucket["UNRATE"] or not bucket["CPIAUCSL"]:
            continue
        cpi = sum(bucket["CPIAUCSL"]) / len(bucket["CPIAUCSL"])
        inflation = ((cpi / previous_cpi - 1) * 100) if previous_cpi else None
        rows.append(
            {
                "issue_quarter": quarter,
                "avg_fed_funds_rate": round(sum(bucket["FEDFUNDS"]) / len(bucket["FEDFUNDS"]), 4),
                "avg_unemployment_rate": round(sum(bucket["UNRATE"]) / len(bucket["UNRATE"]), 4),
                "avg_cpi": round(cpi, 4),
                "quarterly_cpi_inflation_rate": round(inflation, 4) if inflation is not None else "",
            }
        )
        previous_cpi = cpi
    return rows


def draw_multi_line(path, title, labels, series):
    image = Image.new("RGB", (1100, 640), "white")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), title, fill="black")
    draw.line((90, 550, 1040, 550), fill="black", width=2)
    draw.line((90, 90, 90, 550), fill="black", width=2)
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74)]
    values = [v for _, vals in series for v in vals]
    if not values:
        image.save(path)
        return
    mn, mx = min(values), max(values)
    span = max(mx - mn, 0.001)
    x_step = 920 / max(len(labels) - 1, 1)
    for idx, (name, vals) in enumerate(series):
        points = []
        for i, value in enumerate(vals):
            x = 100 + i * x_step
            y = 530 - 420 * ((value - mn) / span)
            points.append((x, y))
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=colors[idx % len(colors)])
        if len(points) > 1:
            draw.line(points, fill=colors[idx % len(colors)], width=2)
        draw.text((795, 100 + idx * 24), name, fill=colors[idx % len(colors)])
    for i, label in enumerate(labels):
        if i % max(len(labels) // 8, 1) == 0:
            draw.text((92 + i * x_step, 562), label, fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    lc_rows = lc_quarterly()
    fred_rows = fred_quarterly()
    write_csv(TABLES / "lc_default_by_quarter.csv", lc_rows)
    write_csv(TABLES / "fred_macro_quarterly.csv", fred_rows)

    fred_by_quarter = {row["issue_quarter"]: row for row in fred_rows}
    merged = []
    for row in lc_rows:
        macro = fred_by_quarter.get(row["issue_quarter"])
        if macro:
            merged.append({**row, **macro})
    write_csv(TABLES / "lc_default_by_quarter_with_fred_macro.csv", merged)

    correlations = []
    for feature in ["avg_fed_funds_rate", "avg_unemployment_rate", "quarterly_cpi_inflation_rate"]:
        correlations.append(
            {
                "macro_variable": feature,
                "correlation_with_quarterly_default_rate": corr(
                    [parse_float(row.get(feature)) for row in merged],
                    [parse_float(row.get("default_rate")) for row in merged],
                ),
            }
        )
    write_csv(TABLES / "lc_fred_quarterly_correlations.csv", correlations)

    draw_multi_line(
        FIGURES / "lc_fred_quarterly_overlay.png",
        "Quarterly Lending Club Default Rate vs FRED Macro Indicators",
        [row["issue_quarter"] for row in merged],
        [
            ("Default Rate", [float(row["default_rate"]) * 100 for row in merged]),
            ("Fed Funds", [float(row["avg_fed_funds_rate"]) for row in merged]),
            ("Unemployment", [float(row["avg_unemployment_rate"]) for row in merged]),
        ],
    )

    findings = [
        "# 季度级 FRED 宏观融合阶段性发现",
        "",
        f"- 已将 Lending Club 违约率按 issue_d 聚合到季度，得到 {len(lc_rows)} 个季度。",
        f"- 已与 FRED 季度宏观指标对齐，匹配 {len(merged)} 个季度。",
    ]
    for row in correlations:
        findings.append(f"- {row['macro_variable']} 与季度违约率的相关系数：{row['correlation_with_quarterly_default_rate']}。")
    findings.append("- 季度级分析比年度分析拥有更多时间点，但仍需要进一步控制贷款结构变化。")
    (TABLES / "fred_quarterly_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Merged {len(merged)} Lending Club quarters with FRED macro indicators")


if __name__ == "__main__":
    main()
