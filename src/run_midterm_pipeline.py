from collections import Counter, defaultdict
from csv import DictReader, DictWriter
from pathlib import Path
import sqlite3

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("请先运行：python3 -m pip install pillow") from exc

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SAMPLE = ROOT / "data" / "sample"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"


def ensure_dirs():
    for path in [RAW, SAMPLE, PROCESSED, FIGURES, TABLES]:
        path.mkdir(parents=True, exist_ok=True)


def write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_sample_data():
    loans = [
        {"loan_id": 1, "state": "CA", "issue_year": 2019, "grade": "A", "interest_rate": 7.1, "annual_income": 92000, "default": 0},
        {"loan_id": 2, "state": "CA", "issue_year": 2020, "grade": "B", "interest_rate": 9.4, "annual_income": 78000, "default": 0},
        {"loan_id": 3, "state": "NY", "issue_year": 2020, "grade": "C", "interest_rate": 12.3, "annual_income": 65000, "default": 0},
        {"loan_id": 4, "state": "TX", "issue_year": 2021, "grade": "D", "interest_rate": 18.2, "annual_income": 54000, "default": 1},
        {"loan_id": 5, "state": "TX", "issue_year": 2022, "grade": "C", "interest_rate": 13.4, "annual_income": 61000, "default": 0},
        {"loan_id": 6, "state": "FL", "issue_year": 2022, "grade": "E", "interest_rate": 22.1, "annual_income": 48000, "default": 1},
        {"loan_id": 7, "state": "IL", "issue_year": 2021, "grade": "B", "interest_rate": 10.2, "annual_income": 72000, "default": 0},
        {"loan_id": 8, "state": "WA", "issue_year": 2023, "grade": "A", "interest_rate": 6.8, "annual_income": 110000, "default": 0},
        {"loan_id": 9, "state": "GA", "issue_year": 2023, "grade": "D", "interest_rate": 17.5, "annual_income": 52000, "default": 1},
        {"loan_id": 10, "state": "OH", "issue_year": 2024, "grade": "C", "interest_rate": 14.1, "annual_income": 59000, "default": 0},
        {"loan_id": 11, "state": "PA", "issue_year": 2024, "grade": "B", "interest_rate": 9.9, "annual_income": 76000, "default": 0},
        {"loan_id": 12, "state": "NC", "issue_year": 2025, "grade": "E", "interest_rate": 21.3, "annual_income": 50000, "default": 1},
    ]
    region = [
        {"state": "CA", "median_income": 91500, "poverty_rate": 11.5, "unemployment_rate": 4.2},
        {"state": "NY", "median_income": 82000, "poverty_rate": 13.8, "unemployment_rate": 4.5},
        {"state": "TX", "median_income": 76000, "poverty_rate": 14.0, "unemployment_rate": 4.1},
        {"state": "FL", "median_income": 69000, "poverty_rate": 12.7, "unemployment_rate": 3.9},
        {"state": "IL", "median_income": 78000, "poverty_rate": 12.1, "unemployment_rate": 4.8},
        {"state": "WA", "median_income": 90000, "poverty_rate": 9.9, "unemployment_rate": 4.0},
        {"state": "GA", "median_income": 67000, "poverty_rate": 13.2, "unemployment_rate": 4.2},
        {"state": "OH", "median_income": 65000, "poverty_rate": 13.4, "unemployment_rate": 4.6},
        {"state": "PA", "median_income": 72000, "poverty_rate": 11.8, "unemployment_rate": 4.3},
        {"state": "NC", "median_income": 68000, "poverty_rate": 12.9, "unemployment_rate": 4.1},
    ]
    macro = [
        {"issue_year": 2019, "fed_funds_rate": 2.16, "inflation_rate": 1.8},
        {"issue_year": 2020, "fed_funds_rate": 0.38, "inflation_rate": 1.2},
        {"issue_year": 2021, "fed_funds_rate": 0.08, "inflation_rate": 4.7},
        {"issue_year": 2022, "fed_funds_rate": 1.68, "inflation_rate": 8.0},
        {"issue_year": 2023, "fed_funds_rate": 5.02, "inflation_rate": 4.1},
        {"issue_year": 2024, "fed_funds_rate": 5.33, "inflation_rate": 3.0},
        {"issue_year": 2025, "fed_funds_rate": 4.50, "inflation_rate": 2.6},
    ]
    write_csv(SAMPLE / "sample_loans.csv", loans)
    write_csv(SAMPLE / "sample_region.csv", region)
    write_csv(SAMPLE / "sample_macro.csv", macro)
    return loans, region, macro


def integrate_sample(loans, region, macro):
    region_by_state = {row["state"]: row for row in region}
    macro_by_year = {row["issue_year"]: row for row in macro}
    merged = []
    for loan in loans:
        row = dict(loan)
        row.update(region_by_state.get(loan["state"], {}))
        row.update(macro_by_year.get(loan["issue_year"], {}))
        merged.append(row)
    write_csv(PROCESSED / "sample_integrated_credit_risk.csv", merged)
    return merged


def average(values):
    return sum(values) / len(values) if values else 0


def write_tables(merged, macro):
    write_csv(TABLES / "sample_macro_summary.csv", macro)

    by_grade = defaultdict(list)
    for row in merged:
        by_grade[row["grade"]].append(row)

    grade_summary = []
    for grade, rows in sorted(by_grade.items()):
        grade_summary.append(
            {
                "grade": grade,
                "default_rate": round(average([r["default"] for r in rows]), 4),
                "avg_interest_rate": round(average([r["interest_rate"] for r in rows]), 2),
            }
        )

    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            """
            CREATE TABLE integrated (
                state TEXT,
                loan_id INTEGER,
                default_flag INTEGER,
                median_income REAL,
                poverty_rate REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO integrated VALUES (:state, :loan_id, :default, :median_income, :poverty_rate)",
            merged,
        )
        region_summary = [
            {
                "state": state,
                "loan_count": loan_count,
                "default_rate": round(default_rate, 4),
                "median_income": round(median_income, 2),
                "poverty_rate": round(poverty_rate, 2),
            }
            for state, loan_count, default_rate, median_income, poverty_rate in conn.execute(
                """
                SELECT
                    state,
                    COUNT(*) AS loan_count,
                    AVG(default_flag) AS default_rate,
                    AVG(median_income) AS median_income,
                    AVG(poverty_rate) AS poverty_rate
                FROM integrated
                GROUP BY state
                ORDER BY state
                """
            )
        ]

    write_csv(TABLES / "sample_region_risk_summary.csv", region_summary)
    write_csv(TABLES / "sample_grade_risk_summary.csv", grade_summary)
    return region_summary, grade_summary


def canvas(title):
    image = Image.new("RGB", (900, 520), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 20), title, fill="black")
    draw.line((70, 450, 850, 450), fill="black", width=2)
    draw.line((70, 80, 70, 450), fill="black", width=2)
    return image, draw


def draw_bar_chart(path, title, labels, values, color=(55, 120, 180)):
    image, draw = canvas(title)
    max_value = max(values) if values else 1
    width = 700 / max(len(values), 1)
    for i, (label, value) in enumerate(zip(labels, values)):
        x0 = 95 + i * width
        x1 = x0 + width * 0.6
        bar_h = 330 * (value / max_value if max_value else 0)
        y0 = 450 - bar_h
        draw.rectangle((x0, y0, x1, 450), fill=color)
        draw.text((x0, 460), str(label), fill="black")
        draw.text((x0, max(85, y0 - 18)), f"{value:.2f}", fill="black")
    image.save(path)


def draw_line_chart(path, title, x_labels, series):
    image, draw = canvas(title)
    colors = [(55, 120, 180), (220, 100, 70), (80, 160, 90)]
    all_values = [v for _, values in series for v in values]
    max_value = max(all_values) if all_values else 1
    min_value = min(all_values) if all_values else 0
    span = max(max_value - min_value, 1)
    x_step = 700 / max(len(x_labels) - 1, 1)
    for idx, (name, values) in enumerate(series):
        points = []
        for i, value in enumerate(values):
            x = 100 + i * x_step
            y = 430 - 320 * ((value - min_value) / span)
            points.append((x, y))
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colors[idx % len(colors)])
        if len(points) > 1:
            draw.line(points, fill=colors[idx % len(colors)], width=3)
        draw.text((650, 90 + idx * 22), name, fill=colors[idx % len(colors)])
    for i, label in enumerate(x_labels):
        draw.text((92 + i * x_step, 460), str(label), fill="black")
    image.save(path)


def plot_sample_outputs(macro, region_summary, grade_summary):
    draw_bar_chart(
        FIGURES / "sample_default_rate_by_grade.png",
        "Sample Default Rate by Loan Grade",
        [row["grade"] for row in grade_summary],
        [float(row["default_rate"]) for row in grade_summary],
    )
    draw_line_chart(
        FIGURES / "sample_macro_trends.png",
        "Sample Macro Financial Indicators",
        [row["issue_year"] for row in macro],
        [
            ("Fed Funds Rate", [float(row["fed_funds_rate"]) for row in macro]),
            ("Inflation Rate", [float(row["inflation_rate"]) for row in macro]),
        ],
    )
    sorted_regions = sorted(region_summary, key=lambda row: float(row["default_rate"]), reverse=True)
    draw_bar_chart(
        FIGURES / "sample_region_risk.png",
        "Sample State-level Default Risk",
        [row["state"] for row in sorted_regions],
        [float(row["default_rate"]) for row in sorted_regions],
        color=(80, 160, 90),
    )


def find_loan_csv():
    for path in RAW.glob("*.csv"):
        lower = path.name.lower()
        if "loan" in lower or "accepted" in lower or "application" in lower:
            return path
    return None


def process_optional_loan_csv(path):
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = DictReader(f)
        columns = reader.fieldnames or []
        rows = 0
        missing = Counter()
        status_col = next((c for c in ["loan_status", "TARGET", "target", "default"] if c in columns), None)
        status_counts = Counter()
        for row in reader:
            rows += 1
            for column in columns:
                if row.get(column, "") == "":
                    missing[column] += 1
            if status_col:
                status_counts[row.get(status_col, "")] += 1
            if rows >= 200000:
                break

    write_csv(TABLES / "loan_overview.csv", [{"metric": "rows", "value": rows}, {"metric": "columns", "value": len(columns)}])
    missing_rows = [
        {"column": column, "missing_rate": round(count / rows, 4) if rows else 0}
        for column, count in missing.most_common(30)
    ]
    if missing_rows:
        write_csv(TABLES / "loan_missing_top30.csv", missing_rows)
    if status_col and status_counts:
        status_rows = [{status_col: key, "count": value} for key, value in status_counts.most_common(12)]
        write_csv(TABLES / "loan_status_distribution.csv", status_rows, [status_col, "count"])
        draw_bar_chart(
            FIGURES / "loan_status_distribution.png",
            "Loan Status / Default Label Distribution",
            [row[status_col][:12] for row in status_rows],
            [float(row["count"]) for row in status_rows],
            color=(220, 100, 70),
        )


def main():
    ensure_dirs()
    loans, region, macro = build_sample_data()
    merged = integrate_sample(loans, region, macro)
    region_summary, grade_summary = write_tables(merged, macro)
    plot_sample_outputs(macro, region_summary, grade_summary)

    loan_csv = find_loan_csv()
    if loan_csv:
        process_optional_loan_csv(loan_csv)
        print(f"Detected loan CSV and generated optional EDA: {loan_csv}")
    else:
        print("No Kaggle loan CSV found. Generated sample multi-source pipeline outputs.")


if __name__ == "__main__":
    main()
