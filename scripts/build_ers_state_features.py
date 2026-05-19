from collections import defaultdict
from csv import DictReader, DictWriter
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
UNEMP_URL = "https://www.ers.usda.gov/media/5497/unemployment-and-median-household-income-for-the-united-states-states-and-counties-2000-23.csv?v=46182"
POVERTY_URL = "https://www.ers.usda.gov/media/5496/poverty-estimates-for-the-united-states-states-and-counties-2023.csv?v=19369"


def write_csv(path, rows, fieldnames=None):
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def download(url, name):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    with urlopen(url, timeout=120) as response:
        path.write_bytes(response.read())
    return path


def parse_float(value):
    if value in (None, "", "."):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def read_state_unemployment(path):
    state_rows = defaultdict(dict)
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in DictReader(f):
            fips = row["FIPS_Code"].zfill(5)
            if not fips.endswith("000") or fips == "00000":
                continue
            state = row["State"]
            attr = row["Attribute"]
            value = parse_float(row["Value"])
            if attr == "Unemployment_rate_2023":
                state_rows[state]["ers_unemployment_rate_2023"] = value
            elif attr == "Median_Household_Income_2022":
                state_rows[state]["ers_median_household_income_2022"] = value
            elif attr == "Median_Household_Income_2023":
                state_rows[state]["ers_median_household_income_2023"] = value
            state_rows[state]["state"] = state
            state_rows[state]["state_name"] = row["Area_Name"]
    return state_rows


def read_state_poverty(path, state_rows):
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in DictReader(f):
            fips = row["FIPS_Code"].zfill(5)
            if not fips.endswith("000") or fips == "00000":
                continue
            state = row["Stabr"]
            attr = row["Attribute"]
            value = parse_float(row["Value"])
            if attr == "PCTPOVALL_2023":
                state_rows[state]["ers_poverty_rate_2023"] = value
            state_rows[state]["state"] = state
            state_rows[state]["state_name"] = row["Area_Name"]
    return state_rows


def read_lc_state():
    rows = []
    path = TABLES / "lc_default_by_state_min1000.csv"
    with path.open(newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            rows.append(row)
    return rows


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


def draw_scatter(path, title, rows, x_key, y_key, label_key="state"):
    image, draw = canvas(title)
    points = []
    for row in rows:
        x = parse_float(row.get(x_key))
        y = parse_float(row.get(y_key))
        if x is not None and y is not None:
            points.append((x, y, row.get(label_key, "")))
    if not points:
        image.save(path)
        return
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x = max(max_x - min_x, 0.001)
    span_y = max(max_y - min_y, 0.001)
    for x, y, label in points:
        px = 100 + 820 * ((x - min_x) / span_x)
        py = 480 - 360 * ((y - min_y) / span_y)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(37, 99, 235))
        if y >= sorted([p[1] for p in points])[-5]:
            draw.text((px + 6, py - 6), label, fill="black")
    draw.text((100, 525), x_key, fill="black")
    draw.text((24, 280), y_key, fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    unemp_path = download(UNEMP_URL, "ers_unemployment_income_2000_2023.csv")
    poverty_path = download(POVERTY_URL, "ers_poverty_2023.csv")
    state_rows = read_state_unemployment(unemp_path)
    state_rows = read_state_poverty(poverty_path, state_rows)
    ers_rows = sorted(state_rows.values(), key=lambda row: row["state"])
    write_csv(TABLES / "ers_state_economic_features.csv", ers_rows)

    lc_rows = read_lc_state()
    merged = []
    by_state = {row["state"]: row for row in ers_rows}
    for row in lc_rows:
        external = by_state.get(row["state"])
        if external:
            merged.append({**row, **external})
    write_csv(TABLES / "lc_default_by_state_with_ers_features.csv", merged)

    correlations = []
    for key in ["ers_unemployment_rate_2023", "ers_median_household_income_2022", "ers_poverty_rate_2023"]:
        correlations.append(
            {
                "state_feature": key,
                "correlation_with_state_default_rate": corr(
                    [parse_float(row.get(key)) for row in merged],
                    [parse_float(row.get("default_rate")) for row in merged],
                ),
            }
        )
    write_csv(TABLES / "lc_ers_state_correlations.csv", correlations)

    draw_scatter(
        FIGURES / "lc_state_default_vs_poverty.png",
        "State Default Rate vs ERS Poverty Rate",
        merged,
        "ers_poverty_rate_2023",
        "default_rate",
    )
    draw_scatter(
        FIGURES / "lc_state_default_vs_income.png",
        "State Default Rate vs ERS Median Household Income",
        merged,
        "ers_median_household_income_2022",
        "default_rate",
    )
    draw_scatter(
        FIGURES / "lc_state_default_vs_unemployment.png",
        "State Default Rate vs ERS Unemployment Rate",
        merged,
        "ers_unemployment_rate_2023",
        "default_rate",
    )

    findings = [
        "# ERS 州级经济数据融合阶段性发现",
        "",
        f"- 已下载 USDA ERS 州/县级经济数据：{unemp_path.relative_to(ROOT)} 与 {poverty_path.relative_to(ROOT)}。",
        f"- 已提取州级收入、贫困率、失业率，并与 Lending Club 州级违约率融合，匹配州数量：{len(merged)}。",
    ]
    for row in correlations:
        findings.append(f"- {row['state_feature']} 与州级违约率的样本相关系数：{row['correlation_with_state_default_rate']}。")
    findings.append("- 该结果为州级横截面相关分析；下一步可进一步控制贷款等级、利率和 FICO 后再判断地区经济变量的边际解释力。")
    (TABLES / "ers_state_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Merged {len(merged)} states with ERS state features")


if __name__ == "__main__":
    main()
