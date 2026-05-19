from collections import defaultdict
from csv import DictReader, DictWriter
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS,UNRATE,CPIAUCSL"


def write_csv(path, rows, fieldnames=None):
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value):
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def download_fred():
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "fred_macro_monthly.csv"
    with urlopen(FRED_URL, timeout=60) as response:
        out.write_bytes(response.read())
    return out


def annualize(path):
    by_year = defaultdict(lambda: {"FEDFUNDS": [], "UNRATE": [], "CPIAUCSL": []})
    with path.open(newline="", encoding="utf-8") as f:
        reader = DictReader(f)
        for row in reader:
            year = row["observation_date"][:4]
            for col in ["FEDFUNDS", "UNRATE", "CPIAUCSL"]:
                value = parse_float(row.get(col))
                if value is not None:
                    by_year[year][col].append(value)

    annual = []
    previous_cpi = None
    for year in sorted(by_year):
        values = by_year[year]
        if not values["FEDFUNDS"] or not values["UNRATE"] or not values["CPIAUCSL"]:
            continue
        cpi = sum(values["CPIAUCSL"]) / len(values["CPIAUCSL"])
        inflation = ((cpi / previous_cpi - 1) * 100) if previous_cpi else None
        annual.append(
            {
                "issue_year": year,
                "avg_fed_funds_rate": round(sum(values["FEDFUNDS"]) / len(values["FEDFUNDS"]), 4),
                "avg_unemployment_rate": round(sum(values["UNRATE"]) / len(values["UNRATE"]), 4),
                "avg_cpi": round(cpi, 4),
                "cpi_inflation_rate": round(inflation, 4) if inflation is not None else "",
            }
        )
        previous_cpi = cpi
    return annual


def read_lc_years():
    path = TABLES / "lc_default_by_year.csv"
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            if row["issue_year"] != "Unknown":
                rows.append(row)
    return rows


def merge_macro(annual_macro, lc_years):
    macro_by_year = {row["issue_year"]: row for row in annual_macro}
    merged = []
    for row in lc_years:
        year = row["issue_year"]
        macro = macro_by_year.get(year)
        if not macro:
            continue
        merged.append({**row, **macro})
    return merged


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


def canvas(title):
    image = Image.new("RGB", (1000, 580), "white")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), title, fill="black")
    draw.line((80, 500, 940, 500), fill="black", width=2)
    draw.line((80, 90, 80, 500), fill="black", width=2)
    return image, draw


def draw_multi_line(path, title, labels, series):
    image, draw = canvas(title)
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74)]
    values = [v for _, vals in series for v in vals]
    if not values:
        image.save(path)
        return
    mn, mx = min(values), max(values)
    span = max(mx - mn, 0.001)
    x_step = 820 / max(len(labels) - 1, 1)
    for idx, (name, vals) in enumerate(series):
        points = []
        for i, value in enumerate(vals):
            x = 100 + i * x_step
            y = 480 - 360 * ((value - mn) / span)
            points.append((x, y))
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=colors[idx % len(colors)])
        if len(points) > 1:
            draw.line(points, fill=colors[idx % len(colors)], width=3)
        draw.text((675, 95 + idx * 24), name, fill=colors[idx % len(colors)])
    for i, label in enumerate(labels):
        if i % max(len(labels) // 8, 1) == 0:
            draw.text((92 + i * x_step, 512), str(label), fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    fred_path = download_fred()
    annual = annualize(fred_path)
    write_csv(TABLES / "fred_macro_annual.csv", annual)

    lc_years = read_lc_years()
    merged = merge_macro(annual, lc_years)
    write_csv(TABLES / "lc_default_by_year_with_fred_macro.csv", merged)

    correlations = [
        {
            "macro_variable": "avg_fed_funds_rate",
            "correlation_with_default_rate": corr([float(r["avg_fed_funds_rate"]) for r in merged], [float(r["default_rate"]) for r in merged]),
        },
        {
            "macro_variable": "avg_unemployment_rate",
            "correlation_with_default_rate": corr([float(r["avg_unemployment_rate"]) for r in merged], [float(r["default_rate"]) for r in merged]),
        },
        {
            "macro_variable": "cpi_inflation_rate",
            "correlation_with_default_rate": corr([float(r["cpi_inflation_rate"]) for r in merged if r["cpi_inflation_rate"] != ""], [float(r["default_rate"]) for r in merged if r["cpi_inflation_rate"] != ""]),
        },
    ]
    write_csv(TABLES / "lc_fred_macro_correlations.csv", correlations)

    labels = [r["issue_year"] for r in merged]
    draw_multi_line(
        FIGURES / "lc_fred_macro_overlay.png",
        "Lending Club Default Rate vs FRED Macro Indicators",
        labels,
        [
            ("Default Rate", [float(r["default_rate"]) * 100 for r in merged]),
            ("Fed Funds", [float(r["avg_fed_funds_rate"]) for r in merged]),
            ("Unemployment", [float(r["avg_unemployment_rate"]) for r in merged]),
        ],
    )

    findings = [
        "# FRED 宏观数据融合阶段性发现",
        "",
        f"- 已下载 FRED 月度宏观数据并聚合为年度表：{fred_path.relative_to(ROOT)}。",
        "- 已将 Lending Club 年度违约率与联邦基金利率、失业率、CPI 通胀率按 issue_year 对齐。",
    ]
    for row in correlations:
        findings.append(f"- {row['macro_variable']} 与年度违约率的样本相关系数：{row['correlation_with_default_rate']}。")
    findings.append("- 该结果只是年度层面的初步相关分析，不能直接解释因果；后续需要季度级或控制变量分析。")
    (TABLES / "fred_macro_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Downloaded FRED data to {fred_path}")
    print(f"Merged {len(merged)} Lending Club years with macro indicators")


if __name__ == "__main__":
    main()
