import os
import sqlite3
import pandas as pd

PARSED_FILE = r"output\analysis_parsed.csv"
DB_PATH = r"data\nifty100.db"
OUTPUT_FILE = r"output\cross_validation.csv"

os.makedirs("output", exist_ok=True)

parsed = pd.read_csv(PARSED_FILE)

con = sqlite3.connect(DB_PATH)

ratios = pd.read_sql_query(
    """
    SELECT
        company_id,
        year,
        revenue_cagr_3yr,
        revenue_cagr_5yr,
        revenue_cagr_10yr,
        pat_cagr_3yr,
        pat_cagr_5yr,
        pat_cagr_10yr
    FROM financial_ratios
    WHERE UPPER(year) <> 'TTM'
    """,
    con,
)

con.close()

ratios["year_num"] = pd.to_numeric(
    ratios["year"].astype(str).str[:4],
    errors="coerce",
)

latest = (
    ratios.sort_values(["company_id", "year_num"])
    .groupby("company_id", as_index=False)
    .tail(1)
)

COLUMN_MAP = {
    ("sales_growth", "3Y"): "revenue_cagr_3yr",
    ("sales_growth", "5Y"): "revenue_cagr_5yr",
    ("sales_growth", "10Y"): "revenue_cagr_10yr",
    ("profit_growth", "3Y"): "pat_cagr_3yr",
    ("profit_growth", "5Y"): "pat_cagr_5yr",
    ("profit_growth", "10Y"): "pat_cagr_10yr",
}

latest_lookup = latest.set_index("company_id")

rows = []

for _, row in parsed.iterrows():

    key = (
        row["metric_type"],
        row["period_years"],
    )

    if key not in COLUMN_MAP:
        continue

    company = row["company_id"]
    ratio_column = COLUMN_MAP[key]
    source_value = row["value_pct"]

    if company not in latest_lookup.index:
        computed_value = None
    else:
        computed_value = latest_lookup.loc[
            company,
            ratio_column,
        ]

    if pd.isna(computed_value):
        difference = None
        status = "MISSING"
    else:
        difference = abs(
            float(source_value) - float(computed_value)
        )

        status = (
            "FLAG"
            if difference > 5
            else "PASS"
        )

    rows.append(
        {
            "company_id": company,
            "metric_type": row["metric_type"],
            "period_years": row["period_years"],
            "analysis_value_pct": source_value,
            "ratio_engine_value_pct": computed_value,
            "difference_pct_points": difference,
            "status": status,
        }
    )

result = pd.DataFrame(rows)

result.to_csv(
    OUTPUT_FILE,
    index=False,
)

print("Created:", OUTPUT_FILE)
print("Validation rows:", len(result))
print("Companies:", result["company_id"].nunique())

print("\nStatus counts:")
print(result["status"].value_counts().to_string())

valid_diff = result["difference_pct_points"].dropna()

if not valid_diff.empty:
    print(
        "\nMaximum divergence:",
        round(valid_diff.max(), 2),
        "percentage points",
    )

flags = result[result["status"] == "FLAG"]

print("\nRows flagged above 5 percentage points:")
if flags.empty:
    print("None")
else:
    print(flags.to_string(index=False))