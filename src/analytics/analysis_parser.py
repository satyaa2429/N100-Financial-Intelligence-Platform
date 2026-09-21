import re
import pandas as pd

INPUT_FILE = r"data\raw\analysis.xlsx"
OUTPUT_FILE = r"output\analysis_parsed.csv"

PERIOD_MAP = {
    "10 years": "10Y",
    "5 years": "5Y",
    "3 years": "3Y",
    "ttm": "TTM",
    "1 year": "1Y",
    "last year": "LAST_YEAR",
}

METRICS = {
    "compounded_sales_growth": "sales_growth",
    "compounded_profit_growth": "profit_growth",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

def parse_metric(value):
    """Parse a metric value from the analysis dataset."""
    if pd.isna(value):
        return None, None

    text = re.sub(r"\s+", " ", str(value)).strip()

    match = re.match(
        r"^(10 Years|5 Years|3 Years|TTM|1 Year|Last Year)\s*:?\s*(-?\d+(?:\.\d+)?)\s*%$",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(f"Could not parse: {value!r}")

    period = PERIOD_MAP[match.group(1).lower()]
    value_pct = float(match.group(2))

    return period, value_pct


df = pd.read_excel(INPUT_FILE, header=1)

rows = []

for _, row in df.iterrows():
    for source_col, metric_type in METRICS.items():

        period, value_pct = parse_metric(row[source_col])

        rows.append({
            "company_id": row["company_id"],
            "metric_type": metric_type,
            "period_years": period,
            "value_pct": value_pct,
        })

result = pd.DataFrame(rows)

result.to_csv(OUTPUT_FILE, index=False)

print("Created:", OUTPUT_FILE)
print("Rows:", len(result))
print("Companies:", result["company_id"].nunique())
print("Metric types:", result["metric_type"].nunique())
print("Missing values:", result.isna().sum().sum())

print("\nMetric counts:")
print(result["metric_type"].value_counts().to_string())

print("\nPreview:")
print(result.head(12).to_string(index=False))
