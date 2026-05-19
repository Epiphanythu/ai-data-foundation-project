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


def find_lending_club_csv():
    for path in sorted(RAW.rglob("accepted_2007_to_2018Q4.csv")):
        if path.is_file():
            return path
    raise FileNotFoundError("未找到 Lending Club accepted CSV")


def outcome(status):
    if status in GOOD_STATUSES:
        return 0
    if status in BAD_STATUSES:
        return 1
    return None


def parse_float(value):
    if value in (None, "", "."):
        return None
    try:
        return float(str(value).replace("%", ""))
    except ValueError:
        return None


def make_bin(value, bins):
    if value is None:
        return "Unknown"
    for upper, label in bins:
        if value < upper:
            return label
    return bins[-1][1]


def update(bucket, key, default_flag):
    bucket[key]["loan_count"] += 1
    bucket[key]["default_count"] += default_flag


def rows_from_bucket(bucket, key_names, min_loans=1000, limit=None):
    rows = []
    for key, value in bucket.items():
        if value["loan_count"] < min_loans:
            continue
        key = key if isinstance(key, tuple) else (key,)
        row = {name: part for name, part in zip(key_names, key)}
        row["loan_count"] = value["loan_count"]
        row["default_count"] = value["default_count"]
        row["default_rate"] = round(value["default_count"] / value["loan_count"], 4)
        rows.append(row)
    rows.sort(key=lambda row: (-row["default_rate"], -row["loan_count"], tuple(str(row[n]) for n in key_names)))
    return rows[:limit] if limit else rows


def write_csv(path, rows, fieldnames=None):
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def canvas(title):
    image = Image.new("RGB", (1100, 640), "white")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), title, fill="black")
    draw.line((120, 550, 1040, 550), fill="black", width=2)
    draw.line((120, 90, 120, 550), fill="black", width=2)
    return image, draw


def draw_horizontal_bar(path, title, rows, label_cols):
    image, draw = canvas(title)
    values = [float(row["default_rate"]) for row in rows]
    max_value = max(values) if values else 1
    for i, row in enumerate(rows[:12]):
        y = 105 + i * 36
        value = float(row["default_rate"])
        width = 760 * value / max_value if max_value else 0
        label = " / ".join(str(row[col]) for col in label_cols)
        draw.text((18, y + 8), label[:24], fill="black")
        draw.rectangle((120, y, 120 + width, y + 22), fill=(37, 99, 235))
        draw.text((130 + width, y + 4), f"{value:.1%} ({row['loan_count']})", fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    csv_path = find_lending_club_csv()
    by_grade_term = defaultdict(lambda: {"loan_count": 0, "default_count": 0})
    by_grade_purpose = defaultdict(lambda: {"loan_count": 0, "default_count": 0})
    by_interest_fico = defaultdict(lambda: {"loan_count": 0, "default_count": 0})
    by_state_grade = defaultdict(lambda: {"loan_count": 0, "default_count": 0})
    by_home_term = defaultdict(lambda: {"loan_count": 0, "default_count": 0})

    int_bins = [(8, "<8%"), (12, "8-12%"), (16, "12-16%"), (20, "16-20%"), (24, "20-24%"), (10**9, ">=24%")]
    fico_bins = [(660, "<660"), (700, "660-700"), (740, "700-740"), (10**9, ">=740")]

    total = usable = 0
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = DictReader(f)
        for row in reader:
            total += 1
            default_flag = outcome(row.get("loan_status", ""))
            if default_flag is None:
                continue
            usable += 1
            grade = row.get("grade") or "Unknown"
            term = (row.get("term") or "Unknown").strip()
            purpose = row.get("purpose") or "Unknown"
            state = row.get("addr_state") or "Unknown"
            home = row.get("home_ownership") or "Unknown"
            interest_bin = make_bin(parse_float(row.get("int_rate")), int_bins)
            fico_low = parse_float(row.get("fico_range_low"))
            fico_high = parse_float(row.get("fico_range_high"))
            fico = (fico_low + fico_high) / 2 if fico_low is not None and fico_high is not None else None
            fico_bin = make_bin(fico, fico_bins)

            update(by_grade_term, (grade, term), default_flag)
            update(by_grade_purpose, (grade, purpose), default_flag)
            update(by_interest_fico, (interest_bin, fico_bin), default_flag)
            update(by_state_grade, (state, grade), default_flag)
            update(by_home_term, (home, term), default_flag)

    grade_term = rows_from_bucket(by_grade_term, ["grade", "term"], min_loans=1000)
    grade_purpose = rows_from_bucket(by_grade_purpose, ["grade", "purpose"], min_loans=1000)
    interest_fico = rows_from_bucket(by_interest_fico, ["interest_bin", "fico_bin"], min_loans=1000)
    state_grade = rows_from_bucket(by_state_grade, ["state", "grade"], min_loans=1000)
    home_term = rows_from_bucket(by_home_term, ["home_ownership", "term"], min_loans=1000)

    write_csv(TABLES / "lc_segment_grade_term.csv", grade_term)
    write_csv(TABLES / "lc_segment_grade_purpose.csv", grade_purpose)
    write_csv(TABLES / "lc_segment_interest_fico.csv", interest_fico)
    write_csv(TABLES / "lc_segment_state_grade.csv", state_grade)
    write_csv(TABLES / "lc_segment_home_term.csv", home_term)

    draw_horizontal_bar(FIGURES / "lc_top_risk_grade_term_segments.png", "Top Grade × Term Risk Segments", grade_term[:12], ["grade", "term"])
    draw_horizontal_bar(FIGURES / "lc_top_risk_grade_purpose_segments.png", "Top Grade × Purpose Risk Segments", grade_purpose[:12], ["grade", "purpose"])
    draw_horizontal_bar(FIGURES / "lc_top_risk_interest_fico_segments.png", "Top Interest × FICO Risk Segments", interest_fico[:12], ["interest_bin", "fico_bin"])
    draw_horizontal_bar(FIGURES / "lc_top_risk_state_grade_segments.png", "Top State × Grade Risk Segments", state_grade[:12], ["state", "grade"])

    findings = [
        "# Lending Club 组合风险分层发现",
        "",
        f"- 输入 accepted 记录数：{total:,}；已完结可用于分层统计记录数：{usable:,}。",
    ]
    if grade_term:
        top = grade_term[0]
        findings.append(f"- Grade × Term 最高风险组合：{top['grade']} / {top['term']}，违约率 {float(top['default_rate']):.2%}，样本数 {top['loan_count']:,}。")
    if grade_purpose:
        top = grade_purpose[0]
        findings.append(f"- Grade × Purpose 最高风险组合：{top['grade']} / {top['purpose']}，违约率 {float(top['default_rate']):.2%}，样本数 {top['loan_count']:,}。")
    if interest_fico:
        top = interest_fico[0]
        findings.append(f"- Interest × FICO 最高风险组合：{top['interest_bin']} / {top['fico_bin']}，违约率 {float(top['default_rate']):.2%}，样本数 {top['loan_count']:,}。")
    if state_grade:
        top = state_grade[0]
        findings.append(f"- State × Grade 最高风险组合：{top['state']} / {top['grade']}，违约率 {float(top['default_rate']):.2%}，样本数 {top['loan_count']:,}。")
    findings.append("- 组合分层比单变量统计更适合解释高风险人群，可作为后续建模或风控规则的候选特征。")
    (TABLES / "lc_segment_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Built risk segments from {usable:,} finalized loans")


if __name__ == "__main__":
    main()
