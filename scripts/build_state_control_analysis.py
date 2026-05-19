from collections import defaultdict
from csv import DictReader, DictWriter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

GOOD_STATUSES = {"Fully Paid"}
BAD_STATUSES = {
    "Charged Off",
    "Default",
    "Late (31-120 days)",
    "Does not meet the credit policy. Status:Charged Off",
}
GRADES = list("ABCDEFG")


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


def write_csv(path, rows, fieldnames=None):
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_ers():
    path = TABLES / "ers_state_economic_features.csv"
    out = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in DictReader(f):
            out[row["state"]] = row
    return out


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


def linear_regression(xs, ys):
    rows = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(rows) < 2:
        return 0, 0
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0
    intercept = my - slope * mx
    return intercept, slope


def residualize(y_key, x_key, rows):
    xs = [parse_float(row.get(x_key)) for row in rows]
    ys = [parse_float(row.get(y_key)) for row in rows]
    intercept, slope = linear_regression(xs, ys)
    residuals = []
    for row, x, y in zip(rows, xs, ys):
        residual = None if x is None or y is None else y - (intercept + slope * x)
        residuals.append(residual)
    return residuals, intercept, slope


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
    top_labels = {p[2] for p in sorted(points, key=lambda p: p[1], reverse=True)[:5]}
    for x, y, label in points:
        px = 100 + 820 * ((x - min_x) / span_x)
        py = 480 - 360 * ((y - min_y) / span_y)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(37, 99, 235))
        if label in top_labels:
            draw.text((px + 6, py - 6), label, fill="black")
    draw.text((100, 525), x_key, fill="black")
    draw.text((24, 280), y_key, fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    csv_path = find_lending_club_csv()
    states = defaultdict(lambda: {"loan_count": 0, "default_count": 0, "interest_sum": 0.0, "interest_n": 0, "fico_sum": 0.0, "fico_n": 0, "grade_counts": defaultdict(int)})

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = DictReader(f)
        for row in reader:
            default_flag = outcome(row.get("loan_status", ""))
            if default_flag is None:
                continue
            state = row.get("addr_state") or "Unknown"
            bucket = states[state]
            bucket["loan_count"] += 1
            bucket["default_count"] += default_flag
            interest = parse_float(row.get("int_rate"))
            if interest is not None:
                bucket["interest_sum"] += interest
                bucket["interest_n"] += 1
            fico_low = parse_float(row.get("fico_range_low"))
            fico_high = parse_float(row.get("fico_range_high"))
            if fico_low is not None and fico_high is not None:
                bucket["fico_sum"] += (fico_low + fico_high) / 2
                bucket["fico_n"] += 1
            grade = row.get("grade") or "Unknown"
            if grade in GRADES:
                bucket["grade_counts"][grade] += 1

    ers = read_ers()
    rows = []
    for state, bucket in sorted(states.items()):
        if state not in ers or bucket["loan_count"] < 1000:
            continue
        loan_count = bucket["loan_count"]
        row = {
            "state": state,
            "loan_count": loan_count,
            "default_rate": round(bucket["default_count"] / loan_count, 4),
            "avg_interest_rate": round(bucket["interest_sum"] / bucket["interest_n"], 4) if bucket["interest_n"] else "",
            "avg_fico": round(bucket["fico_sum"] / bucket["fico_n"], 4) if bucket["fico_n"] else "",
        }
        for grade in GRADES:
            row[f"share_grade_{grade}"] = round(bucket["grade_counts"][grade] / loan_count, 4)
        row.update(ers[state])
        rows.append(row)

    interest_residuals, interest_intercept, interest_slope = residualize("default_rate", "avg_interest_rate", rows)
    fico_residuals, fico_intercept, fico_slope = residualize("default_rate", "avg_fico", rows)
    for row, ir, fr in zip(rows, interest_residuals, fico_residuals):
        row["default_residual_after_avg_interest"] = round(ir, 4) if ir is not None else ""
        row["default_residual_after_avg_fico"] = round(fr, 4) if fr is not None else ""

    write_csv(TABLES / "lc_state_control_features.csv", rows)

    correlation_rows = []
    for target in ["default_rate", "default_residual_after_avg_interest", "default_residual_after_avg_fico"]:
        for feature in ["ers_poverty_rate_2023", "ers_median_household_income_2022", "ers_unemployment_rate_2023", "avg_interest_rate", "avg_fico", "share_grade_A", "share_grade_G"]:
            correlation_rows.append(
                {
                    "target": target,
                    "feature": feature,
                    "correlation": corr([parse_float(row.get(feature)) for row in rows], [parse_float(row.get(target)) for row in rows]),
                }
            )
    write_csv(TABLES / "lc_state_control_correlations.csv", correlation_rows)

    draw_scatter(FIGURES / "lc_state_default_residual_interest_vs_poverty.png", "Default Residual after Interest vs Poverty", rows, "ers_poverty_rate_2023", "default_residual_after_avg_interest")
    draw_scatter(FIGURES / "lc_state_default_residual_fico_vs_poverty.png", "Default Residual after FICO vs Poverty", rows, "ers_poverty_rate_2023", "default_residual_after_avg_fico")
    draw_scatter(FIGURES / "lc_state_default_vs_avg_interest.png", "State Default Rate vs Average Interest", rows, "avg_interest_rate", "default_rate")
    draw_scatter(FIGURES / "lc_state_default_vs_avg_fico.png", "State Default Rate vs Average FICO", rows, "avg_fico", "default_rate")

    def lookup(target, feature):
        for row in correlation_rows:
            if row["target"] == target and row["feature"] == feature:
                return row["correlation"]
        return ""

    findings = [
        "# 州级控制变量分析阶段性发现",
        "",
        f"- 构建州级控制变量表，覆盖 {len(rows)} 个州；每州包含违约率、平均利率、平均 FICO、等级结构和 ERS 经济特征。",
        f"- 州级平均利率与违约率相关系数：{lookup('default_rate', 'avg_interest_rate')}。",
        f"- 州级平均 FICO 与违约率相关系数：{lookup('default_rate', 'avg_fico')}。",
        f"- 贫困率与原始州级违约率相关系数：{lookup('default_rate', 'ers_poverty_rate_2023')}。",
        f"- 控制平均利率后的违约率残差与贫困率相关系数：{lookup('default_residual_after_avg_interest', 'ers_poverty_rate_2023')}。",
        f"- 控制平均 FICO 后的违约率残差与贫困率相关系数：{lookup('default_residual_after_avg_fico', 'ers_poverty_rate_2023')}。",
        "- 该分析说明地区经济变量与违约率关系需要和贷款定价、信用质量结构一起解释，不能只看单变量相关。",
    ]
    (TABLES / "lc_state_control_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Built state control analysis for {len(rows)} states")


if __name__ == "__main__":
    main()
