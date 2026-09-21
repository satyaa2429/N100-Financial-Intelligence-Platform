import os
import sqlite3
import pandas as pd

DB_PATH = r"data\nifty100.db"
OUTPUT_PATH = r"output\pros_cons_generated.csv"

os.makedirs("output", exist_ok=True)

con = sqlite3.connect(DB_PATH)

ratios = pd.read_sql_query(
    """
    SELECT *
    FROM financial_ratios
    WHERE UPPER(year) <> 'TTM'
    """,
    con,
)

sectors = pd.read_sql_query(
    "SELECT company_id, broad_sector FROM sectors",
    con,
)

con.close()

ratios["year_num"] = pd.to_numeric(
    ratios["year"].astype(str).str[:4],
    errors="coerce",
)

ratios = ratios.sort_values(
    ["company_id", "year_num"]
)

latest = (
    ratios.groupby("company_id", as_index=False)
    .tail(1)
    .merge(sectors, on="company_id", how="left")
)

results = []


def valid(value):
    """Return whether a candidate value is valid and usable."""
    return pd.notna(value)


def add(company_id, signal_type, rule, text, confidence):
    """Add a generated pro or con when its condition is satisfied."""
    results.append(
        {
            "company_id": company_id,
            "type": signal_type,
            "rule_triggered": rule,
            "text": text,
            "confidence_pct": confidence,
        }
    )


for _, row in latest.iterrows():

    company = row["company_id"]
    sector = row["broad_sector"]
    financial = sector == "Financials"

    hist = ratios[
        ratios["company_id"] == company
    ].sort_values("year_num")

    # ======================================================
    # 12 PRO RULES
    # ======================================================

    if valid(row["return_on_equity_pct"]) and row["return_on_equity_pct"] > 20:
        add(
            company, "pro", "PRO_01_STRONG_ROE",
            f"Strong ROE of {row['return_on_equity_pct']:.1f}%.",
            90,
        )

    if (
        valid(row["return_on_capital_employed_pct"])
        and row["return_on_capital_employed_pct"] > 20
    ):
        add(
            company, "pro", "PRO_02_STRONG_ROCE",
            f"Strong ROCE of {row['return_on_capital_employed_pct']:.1f}%.",
            90,
        )

    if (
        not financial
        and valid(row["debt_to_equity"])
        and row["debt_to_equity"] <= 0.10
    ):
        add(
            company, "pro", "PRO_03_LOW_DEBT",
            f"Very low debt-to-equity ratio of {row['debt_to_equity']:.2f}.",
            90,
        )

    if (
        not financial
        and valid(row["interest_coverage"])
        and row["interest_coverage"] > 10
    ):
        add(
            company, "pro", "PRO_04_STRONG_ICR",
            f"Strong interest coverage of {row['interest_coverage']:.1f}x.",
            85,
        )

    fcf5 = hist["free_cash_flow_cr"].dropna().tail(5)

    if len(fcf5) == 5 and (fcf5 > 0).all():
        add(
            company, "pro", "PRO_05_POSITIVE_FCF_5Y",
            "Free cash flow remained positive in each of the last 5 annual periods.",
            95,
        )

    if valid(row["revenue_cagr_5yr"]) and row["revenue_cagr_5yr"] > 15:
        add(
            company, "pro", "PRO_06_REVENUE_GROWTH",
            f"Strong 5-year revenue CAGR of {row['revenue_cagr_5yr']:.1f}%.",
            85,
        )

    if valid(row["pat_cagr_5yr"]) and row["pat_cagr_5yr"] > 15:
        add(
            company, "pro", "PRO_07_PAT_GROWTH",
            f"Healthy 5-year PAT CAGR of {row['pat_cagr_5yr']:.1f}%.",
            85,
        )

    if valid(row["eps_cagr_5yr"]) and row["eps_cagr_5yr"] > 12:
        add(
            company, "pro", "PRO_08_EPS_GROWTH",
            f"Healthy 5-year EPS CAGR of {row['eps_cagr_5yr']:.1f}%.",
            85,
        )

    if valid(row["cfo_pat_ratio"]) and row["cfo_pat_ratio"] > 1:
        add(
            company, "pro", "PRO_09_HIGH_CFO_QUALITY",
            f"Strong cash earnings quality with CFO/PAT of {row['cfo_pat_ratio']:.2f}x.",
            90,
        )

    if valid(row["capex_intensity_pct"]) and row["capex_intensity_pct"] < 3:
        add(
            company, "pro", "PRO_10_ASSET_LIGHT",
            f"Low CapEx intensity of {row['capex_intensity_pct']:.1f}%.",
            75,
        )

    if valid(row["fcf_conversion_pct"]) and row["fcf_conversion_pct"] > 60:
        add(
            company, "pro", "PRO_11_FCF_CONVERSION",
            f"Strong FCF conversion of {row['fcf_conversion_pct']:.1f}%.",
            85,
        )

    if (
        valid(row["dividend_payout_ratio_pct"])
        and 30 <= row["dividend_payout_ratio_pct"] <= 60
    ):
        add(
            company, "pro", "PRO_12_BALANCED_DIVIDEND",
            f"Balanced dividend payout ratio of {row['dividend_payout_ratio_pct']:.1f}%.",
            75,
        )

    # ======================================================
    # 12 CON RULES
    # ======================================================

    if valid(row["return_on_equity_pct"]) and row["return_on_equity_pct"] < 10:
        add(
            company, "con", "CON_01_LOW_ROE",
            f"Low ROE of {row['return_on_equity_pct']:.1f}%.",
            85,
        )

    if (
        valid(row["return_on_capital_employed_pct"])
        and row["return_on_capital_employed_pct"] < 10
    ):
        add(
            company, "con", "CON_02_LOW_ROCE",
            f"Low ROCE of {row['return_on_capital_employed_pct']:.1f}%.",
            85,
        )

    if (
        not financial
        and valid(row["debt_to_equity"])
        and row["debt_to_equity"] > 2
    ):
        add(
            company, "con", "CON_03_HIGH_DEBT",
            f"High debt-to-equity ratio of {row['debt_to_equity']:.2f}.",
            90,
        )

    if (
        not financial
        and valid(row["interest_coverage"])
        and row["interest_coverage"] < 1.5
    ):
        add(
            company, "con", "CON_04_LOW_ICR",
            f"Weak interest coverage of {row['interest_coverage']:.2f}x.",
            95,
        )

    fcf3 = hist["free_cash_flow_cr"].dropna().tail(3)

    if len(fcf3) == 3 and (fcf3 < 0).all():
        add(
            company, "con", "CON_05_NEGATIVE_FCF_3Y",
            "Free cash flow remained negative for 3 consecutive annual periods.",
            95,
        )

    if valid(row["revenue_cagr_5yr"]) and row["revenue_cagr_5yr"] < 5:
        add(
            company, "con", "CON_06_WEAK_REVENUE_GROWTH",
            f"Weak 5-year revenue CAGR of {row['revenue_cagr_5yr']:.1f}%.",
            80,
        )

    if valid(row["pat_cagr_5yr"]) and row["pat_cagr_5yr"] < 5:
        add(
            company, "con", "CON_07_WEAK_PAT_GROWTH",
            f"Weak 5-year PAT CAGR of {row['pat_cagr_5yr']:.1f}%.",
            80,
        )

    if valid(row["eps_cagr_5yr"]) and row["eps_cagr_5yr"] < 5:
        add(
            company, "con", "CON_08_WEAK_EPS_GROWTH",
            f"Weak 5-year EPS CAGR of {row['eps_cagr_5yr']:.1f}%.",
            80,
        )

    if valid(row["cfo_pat_ratio"]) and row["cfo_pat_ratio"] < 0.5:
        add(
            company, "con", "CON_09_ACCRUAL_RISK",
            f"Low CFO/PAT ratio of {row['cfo_pat_ratio']:.2f}x.",
            90,
        )

    if valid(row["capex_intensity_pct"]) and row["capex_intensity_pct"] > 8:
        add(
            company, "con", "CON_10_CAPITAL_INTENSIVE",
            f"High CapEx intensity of {row['capex_intensity_pct']:.1f}%.",
            75,
        )

    if valid(row["fcf_conversion_pct"]) and row["fcf_conversion_pct"] < 30:
        add(
            company, "con", "CON_11_LOW_FCF_CONVERSION",
            f"Weak FCF conversion of {row['fcf_conversion_pct']:.1f}%.",
            85,
        )

    opm = (
        hist["operating_profit_margin_pct"]
        .dropna()
        .tail(3)
        .tolist()
    )

    if len(opm) == 3 and opm[0] > opm[1] > opm[2]:
        add(
            company, "con", "CON_12_DECLINING_OPM",
            "Operating profit margin declined in each of the last 3 annual periods.",
            85,
        )


result = pd.DataFrame(results)

result = result.sort_values(
    ["company_id", "type", "rule_triggered"]
).reset_index(drop=True)

result.to_csv(
    OUTPUT_PATH,
    index=False,
)

all_companies = set(latest["company_id"])
covered = set(result["company_id"])
missing = sorted(all_companies - covered)

print("Created:", OUTPUT_PATH)
print("Generated rows:", len(result))
print("Companies covered:", result["company_id"].nunique())
print(
    "Pro rules triggered:",
    result[result["type"] == "pro"]["rule_triggered"].nunique(),
)
print(
    "Con rules triggered:",
    result[result["type"] == "con"]["rule_triggered"].nunique(),
)
print("Minimum confidence:", result["confidence_pct"].min())

print("\nCompanies without a generated signal:")
print(missing if missing else "None")