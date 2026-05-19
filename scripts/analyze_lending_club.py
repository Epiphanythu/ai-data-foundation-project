from collections import Counter, defaultdict
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
MONTHS = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


def find_lending_club_csv():
    candidates = sorted(RAW.rglob("accepted_2007_to_2018Q4.csv"))
    for path in candidates:
        if path.is_file():
            return path
    for path in sorted(RAW.rglob("*.csv")):
        lower = path.name.lower()
        if path.is_file() and "accepted" in lower:
            return path
    raise FileNotFoundError("未找到 Lending Club accepted CSV，请先下载到 data/raw/lending_club/")


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
    if value is None:
        return None
    value = value.strip().replace("%", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def issue_year(value):
    if not value or "-" not in value:
        return "Unknown"
    return value.split("-")[-1]


def issue_month(value):
    if not value or "-" not in value:
        return "Unknown"
    month, year = value.split("-", 1)
    return f"{year}-{MONTHS.get(month, '??')}"


def make_bin(value, bins):
    if value is None:
        return "Unknown"
    for upper, label in bins:
        if value < upper:
            return label
    return bins[-1][1]


def outcome(status):
    if status in GOOD_STATUSES:
        return 0
    if status in BAD_STATUSES:
        return 1
    return None


def update_bucket(bucket, key, default_flag):
    bucket[key]["loans"] += 1
    bucket[key]["defaults"] += default_flag


def bucket_rows(bucket, key_name, min_loans=0, sort_by="key", order=None):
    rows = []
    for key, value in bucket.items():
        loans = value["loans"]
        if loans < min_loans:
            continue
        defaults = value["defaults"]
        rows.append(
            {
                key_name: key,
                "loan_count": loans,
                "default_count": defaults,
                "default_rate": round(defaults / loans, 4) if loans else 0,
            }
        )
    if order:
        rank = {label: i for i, label in enumerate(order)}
        rows.sort(key=lambda row: rank.get(row[key_name], len(rank)))
    elif sort_by == "default_rate_desc":
        rows.sort(key=lambda row: (-float(row["default_rate"]), -int(row["loan_count"]), str(row[key_name])))
    elif sort_by == "loan_count_desc":
        rows.sort(key=lambda row: (-int(row["loan_count"]), str(row[key_name])))
    else:
        rows.sort(key=lambda row: str(row[key_name]))
    return rows


def canvas(title):
    image = Image.new("RGB", (1000, 580), "white")
    draw = ImageDraw.Draw(image)
    draw.text((32, 22), title, fill="black")
    draw.line((80, 500, 940, 500), fill="black", width=2)
    draw.line((80, 90, 80, 500), fill="black", width=2)
    return image, draw


def draw_bar_chart(path, title, labels, values, color=(55, 120, 180)):
    image, draw = canvas(title)
    max_value = max(values) if values else 1
    width = 820 / max(len(values), 1)
    for i, (label, value) in enumerate(zip(labels, values)):
        x0 = 100 + i * width
        x1 = x0 + width * 0.62
        bar_h = 380 * (value / max_value if max_value else 0)
        y0 = 500 - bar_h
        draw.rectangle((x0, y0, x1, 500), fill=color)
        draw.text((x0, 512), str(label)[:12], fill="black")
        draw.text((x0, max(96, y0 - 18)), f"{value:.1%}" if value <= 1 else f"{value:.0f}", fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def draw_line_chart(path, title, labels, values):
    image, draw = canvas(title)
    if not values:
        image.save(path)
        return
    max_value = max(values)
    min_value = min(values)
    span = max(max_value - min_value, 0.001)
    x_step = 820 / max(len(values) - 1, 1)
    points = []
    for i, value in enumerate(values):
        x = 100 + i * x_step
        y = 480 - 360 * ((value - min_value) / span)
        points.append((x, y))
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(220, 100, 70))
    if len(points) > 1:
        draw.line(points, fill=(220, 100, 70), width=3)
    for i, label in enumerate(labels):
        if i % max(len(labels) // 8, 1) == 0:
            draw.text((92 + i * x_step, 512), str(label), fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def analyze():
    csv_path = find_lending_club_csv()
    status_counts = Counter()
    all_rows = 0
    usable_rows = 0
    skipped_rows = 0
    missing = Counter()

    by_grade = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_year = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_month = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_state = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_interest = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_income = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_dti = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_fico = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_purpose = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_home = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_term = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_verification = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_emp_length = defaultdict(lambda: {"loans": 0, "defaults": 0})
    by_loan_amount = defaultdict(lambda: {"loans": 0, "defaults": 0})

    int_order = ["<8%", "8-12%", "12-16%", "16-20%", "20-24%", ">=24%", "Unknown"]
    income_order = ["<40k", "40-60k", "60-80k", "80-120k", ">=120k", "Unknown"]
    dti_order = ["<10", "10-20", "20-30", "30-40", ">=40", "Unknown"]
    fico_order = ["<660", "660-700", "700-740", ">=740", "Unknown"]
    loan_amount_order = ["<5k", "5-10k", "10-20k", "20-30k", ">=30k", "Unknown"]
    emp_length_order = ["< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years", "6 years", "7 years", "8 years", "9 years", "10+ years", "Unknown"]
    int_bins = [(8, "<8%"), (12, "8-12%"), (16, "12-16%"), (20, "16-20%"), (24, "20-24%"), (10**9, ">=24%")]
    income_bins = [(40000, "<40k"), (60000, "40-60k"), (80000, "60-80k"), (120000, "80-120k"), (10**12, ">=120k")]
    dti_bins = [(10, "<10"), (20, "10-20"), (30, "20-30"), (40, "30-40"), (10**9, ">=40")]
    fico_bins = [(660, "<660"), (700, "660-700"), (740, "700-740"), (10**9, ">=740")]
    loan_amount_bins = [(5000, "<5k"), (10000, "5-10k"), (20000, "10-20k"), (30000, "20-30k"), (10**12, ">=30k")]

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = DictReader(f)
        columns = reader.fieldnames or []
        for row in reader:
            all_rows += 1
            for col in columns:
                if row.get(col, "") == "":
                    missing[col] += 1

            status = row.get("loan_status", "")
            status_counts[status] += 1
            default_flag = outcome(status)
            if default_flag is None:
                skipped_rows += 1
                continue
            usable_rows += 1

            update_bucket(by_grade, row.get("grade") or "Unknown", default_flag)
            update_bucket(by_year, issue_year(row.get("issue_d")), default_flag)
            update_bucket(by_month, issue_month(row.get("issue_d")), default_flag)
            update_bucket(by_state, row.get("addr_state") or "Unknown", default_flag)
            update_bucket(by_interest, make_bin(parse_float(row.get("int_rate")), int_bins), default_flag)
            update_bucket(by_income, make_bin(parse_float(row.get("annual_inc")), income_bins), default_flag)
            update_bucket(by_dti, make_bin(parse_float(row.get("dti")), dti_bins), default_flag)
            update_bucket(by_purpose, row.get("purpose") or "Unknown", default_flag)
            update_bucket(by_home, row.get("home_ownership") or "Unknown", default_flag)
            update_bucket(by_term, (row.get("term") or "Unknown").strip(), default_flag)
            update_bucket(by_verification, row.get("verification_status") or "Unknown", default_flag)
            update_bucket(by_emp_length, row.get("emp_length") or "Unknown", default_flag)
            update_bucket(by_loan_amount, make_bin(parse_float(row.get("loan_amnt")), loan_amount_bins), default_flag)

            fico_low = parse_float(row.get("fico_range_low"))
            fico_high = parse_float(row.get("fico_range_high"))
            fico = (fico_low + fico_high) / 2 if fico_low is not None and fico_high is not None else None
            update_bucket(by_fico, make_bin(fico, fico_bins), default_flag)

    overview = [
        {"metric": "source_file", "value": str(csv_path.relative_to(ROOT))},
        {"metric": "all_rows", "value": all_rows},
        {"metric": "usable_finalized_rows", "value": usable_rows},
        {"metric": "skipped_non_final_rows", "value": skipped_rows},
        {"metric": "columns", "value": len(columns)},
        {"metric": "overall_default_rate", "value": round(sum(v["defaults"] for v in by_year.values()) / usable_rows, 4) if usable_rows else 0},
    ]
    write_csv(TABLES / "lc_overview.csv", overview, ["metric", "value"])

    status_rows = [{"loan_status": k, "count": v} for k, v in status_counts.most_common()]
    write_csv(TABLES / "lc_status_distribution.csv", status_rows, ["loan_status", "count"])

    missing_rows = [
        {"column": column, "missing_rate": round(count / all_rows, 4), "missing_count": count}
        for column, count in missing.most_common(40)
    ]
    write_csv(TABLES / "lc_missing_top40.csv", missing_rows, ["column", "missing_rate", "missing_count"])

    grade_rows = bucket_rows(by_grade, "grade")
    year_rows = bucket_rows(by_year, "issue_year")
    month_rows = bucket_rows(by_month, "issue_month")
    state_rows = bucket_rows(by_state, "state", min_loans=1000, sort_by="default_rate_desc")
    interest_rows = bucket_rows(by_interest, "interest_bin", order=int_order)
    income_rows = bucket_rows(by_income, "income_bin", order=income_order)
    dti_rows = bucket_rows(by_dti, "dti_bin", order=dti_order)
    fico_rows = bucket_rows(by_fico, "fico_bin", order=fico_order)
    purpose_rows = bucket_rows(by_purpose, "purpose", min_loans=1000, sort_by="default_rate_desc")
    home_rows = bucket_rows(by_home, "home_ownership")
    term_rows = bucket_rows(by_term, "term")
    verification_rows = bucket_rows(by_verification, "verification_status")
    emp_length_rows = bucket_rows(by_emp_length, "emp_length", order=emp_length_order)
    loan_amount_rows = bucket_rows(by_loan_amount, "loan_amount_bin", order=loan_amount_order)

    write_csv(TABLES / "lc_default_by_grade.csv", grade_rows)
    write_csv(TABLES / "lc_default_by_year.csv", year_rows)
    write_csv(TABLES / "lc_default_by_month.csv", month_rows)
    write_csv(TABLES / "lc_default_by_state_min1000.csv", state_rows)
    write_csv(TABLES / "lc_default_by_interest_bin.csv", interest_rows)
    write_csv(TABLES / "lc_default_by_income_bin.csv", income_rows)
    write_csv(TABLES / "lc_default_by_dti_bin.csv", dti_rows)
    write_csv(TABLES / "lc_default_by_fico_bin.csv", fico_rows)
    write_csv(TABLES / "lc_default_by_purpose_min1000.csv", purpose_rows)
    write_csv(TABLES / "lc_default_by_home_ownership.csv", home_rows)
    write_csv(TABLES / "lc_default_by_term.csv", term_rows)
    write_csv(TABLES / "lc_default_by_verification_status.csv", verification_rows)
    write_csv(TABLES / "lc_default_by_emp_length.csv", emp_length_rows)
    write_csv(TABLES / "lc_default_by_loan_amount_bin.csv", loan_amount_rows)

    draw_bar_chart(
        FIGURES / "lc_default_rate_by_grade.png",
        "Lending Club Default Rate by Grade",
        [r["grade"] for r in grade_rows],
        [float(r["default_rate"]) for r in grade_rows],
    )
    draw_line_chart(
        FIGURES / "lc_default_rate_by_year.png",
        "Lending Club Default Rate by Issue Year",
        [r["issue_year"] for r in year_rows if r["issue_year"] != "Unknown"],
        [float(r["default_rate"]) for r in year_rows if r["issue_year"] != "Unknown"],
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_interest_bin.png",
        "Lending Club Default Rate by Interest Rate Bin",
        [r["interest_bin"] for r in interest_rows],
        [float(r["default_rate"]) for r in interest_rows],
        color=(220, 100, 70),
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_fico_bin.png",
        "Lending Club Default Rate by FICO Bin",
        [r["fico_bin"] for r in fico_rows],
        [float(r["default_rate"]) for r in fico_rows],
        color=(80, 160, 90),
    )
    top_states = state_rows[:12]
    draw_bar_chart(
        FIGURES / "lc_default_rate_top_states.png",
        "Lending Club Highest Default Rate States, min 1000 loans",
        [r["state"] for r in top_states],
        [float(r["default_rate"]) for r in top_states],
        color=(120, 90, 170),
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_purpose.png",
        "Lending Club Default Rate by Purpose, min 1000 loans",
        [r["purpose"] for r in purpose_rows[:10]],
        [float(r["default_rate"]) for r in purpose_rows[:10]],
        color=(234, 88, 12),
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_home_ownership.png",
        "Lending Club Default Rate by Home Ownership",
        [r["home_ownership"] for r in home_rows],
        [float(r["default_rate"]) for r in home_rows],
        color=(14, 165, 233),
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_loan_amount.png",
        "Lending Club Default Rate by Loan Amount Bin",
        [r["loan_amount_bin"] for r in loan_amount_rows],
        [float(r["default_rate"]) for r in loan_amount_rows],
        color=(124, 58, 237),
    )
    draw_bar_chart(
        FIGURES / "lc_default_rate_by_term.png",
        "Lending Club Default Rate by Term",
        [r["term"] for r in term_rows],
        [float(r["default_rate"]) for r in term_rows],
        color=(220, 38, 38),
    )

    findings = [
        "# Lending Club 真实数据阶段性发现",
        "",
        f"- 原始 accepted 贷款记录数：{all_rows:,}。",
        f"- 用于违约率统计的已完结记录数：{usable_rows:,}；未完结或不适合判断最终违约的记录数：{skipped_rows:,}。",
        f"- 已完结记录总体违约率：{float(overview[-1]['value']):.2%}。",
    ]
    if grade_rows:
        findings.append(f"- 贷款等级风险呈梯度差异：{grade_rows[0]['grade']} 等级违约率约 {float(grade_rows[0]['default_rate']):.2%}，{grade_rows[-1]['grade']} 等级约 {float(grade_rows[-1]['default_rate']):.2%}。")
    if interest_rows:
        low = interest_rows[0]
        high = interest_rows[-1]
        findings.append(f"- 利率越高的分箱违约率越高：{low['interest_bin']} 约 {float(low['default_rate']):.2%}，{high['interest_bin']} 约 {float(high['default_rate']):.2%}。")
    if fico_rows:
        findings.append("- FICO 分数越低，违约率通常越高，说明传统信用评分仍有明显解释力。")
    if state_rows:
        findings.append(f"- 州级违约率存在地区差异；样本量超过 1000 的州中，最高违约率州为 {state_rows[0]['state']}，约 {float(state_rows[0]['default_rate']):.2%}。")
    if purpose_rows:
        findings.append(f"- 贷款用途也存在风险差异；样本量超过 1000 的用途类别中，最高违约率用途为 {purpose_rows[0]['purpose']}，约 {float(purpose_rows[0]['default_rate']):.2%}。")
    if loan_amount_rows:
        findings.append(f"- 贷款金额分箱显示额度结构与风险相关；最高金额分箱 {loan_amount_rows[-1]['loan_amount_bin']} 的违约率约 {float(loan_amount_rows[-1]['default_rate']):.2%}。")
    if term_rows:
        high_term = max(term_rows, key=lambda row: float(row['default_rate']))
        findings.append(f"- 贷款期限与风险相关；{high_term['term']} 的违约率约 {float(high_term['default_rate']):.2%}。")
    findings.extend(
        [
            "",
            "这些发现可直接服务中期汇报的“进度汇报”和“初步洞察”部分。后续应继续把 ACS 区域经济变量和 Fed 宏观金融变量接入，验证地区与宏观环境是否能解释这些差异。",
        ]
    )
    (TABLES / "lc_findings.md").write_text("\n".join(findings), encoding="utf-8")

    print(f"Analyzed {all_rows:,} Lending Club rows from {csv_path}")
    print(f"Usable finalized rows: {usable_rows:,}; skipped: {skipped_rows:,}")
    print("Generated lc_* tables and figures.")


if __name__ == "__main__":
    analyze()
