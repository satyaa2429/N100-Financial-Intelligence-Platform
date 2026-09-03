import sqlite3
from pathlib import Path

import pandas as pd


DB = Path("data/nifty100.db")
OUT = Path("output/sprint2_manual_spotcheck.csv")

COMPANIES = [
    "TCS",
    "RELIANCE",
    "INFY",
]


def year_number(value):
    try:
        text = str(value).strip()

        if text.upper() == "TTM":
            return None

        return int(text[:4])

    except Exception:
        return None


results = []


with sqlite3.connect(DB) as conn:

    pnl = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            sales,
            net_profit
        FROM profitandloss
        """,
        conn,
    )

    bs = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            equity_capital,
            reserves
        FROM balancesheet
        """,
        conn,
    )

    ratios = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            return_on_equity_pct,
            revenue_cagr_5yr
        FROM financial_ratios
        """,
        conn,
    )


for df in [pnl, bs, ratios]:

    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["year"] = (
        df["year"]
        .astype(str)
        .str.strip()
    )

    df["_year"] = (
        df["year"]
        .apply(year_number)
    )


for company in COMPANIES:

    cp = pnl[
        pnl["company_id"] == company
    ].copy()

    cb = bs[
        bs["company_id"] == company
    ].copy()

    cr = ratios[
        ratios["company_id"] == company
    ].copy()

    merged = (
        cr.merge(
            cp[
                [
                    "company_id",
                    "year",
                    "_year",
                    "sales",
                    "net_profit",
                ]
            ],
            on=[
                "company_id",
                "year",
            ],
            how="left",
        )
        .merge(
            cb[
                [
                    "company_id",
                    "year",
                    "equity_capital",
                    "reserves",
                ]
            ],
            on=[
                "company_id",
                "year",
            ],
            how="left",
        )
    )

    sales_lookup = {
        int(row["_year"]): float(row["sales"])
        for _, row in cp.dropna(
            subset=[
                "_year",
                "sales",
            ]
        ).iterrows()
    }

    # Restore one year helper column after pandas merge suffixing.
    if "_year" not in merged.columns:

        if "_year_x" in merged.columns:
            merged["_year"] = merged["_year_x"]

        elif "_year_y" in merged.columns:
            merged["_year"] = merged["_year_y"]

        else:
            merged["_year"] = merged["year"].apply(
                year_number
            )

    merged = merged.sort_values(
        "_year",
        ascending=False,
    )

    selected = None

    for _, row in merged.iterrows():

        if pd.isna(row["_year"]):
            continue

        if pd.isna(
            row["return_on_equity_pct"]
        ):
            continue

        if pd.isna(
            row["revenue_cagr_5yr"]
        ):
            continue

        if pd.isna(
            row["net_profit"]
        ):
            continue

        if pd.isna(
            row["equity_capital"]
        ):
            continue

        if pd.isna(
            row["reserves"]
        ):
            continue

        equity = (
            float(row["equity_capital"])
            + float(row["reserves"])
        )

        if equity <= 0:
            continue

        end_year = int(
            row["_year"]
        )

        start_year = (
            end_year - 5
        )

        if (
            start_year
            not in sales_lookup
        ):
            continue

        if (
            end_year
            not in sales_lookup
        ):
            continue

        start_sales = sales_lookup[
            start_year
        ]

        end_sales = sales_lookup[
            end_year
        ]

        if (
            start_sales <= 0
            or end_sales <= 0
        ):
            continue

        selected = (
            row,
            start_year,
            end_year,
            start_sales,
            end_sales,
        )

        break


    if selected is None:
        raise RuntimeError(
            f"No valid spot-check row for {company}"
        )


    (
        row,
        start_year,
        end_year,
        start_sales,
        end_sales,
    ) = selected


    # --------------------------------------------------------
    # MANUAL ROE
    # --------------------------------------------------------

    manual_roe = (
        float(row["net_profit"])
        / (
            float(
                row["equity_capital"]
            )
            + float(
                row["reserves"]
            )
        )
        * 100
    )

    stored_roe = float(
        row[
            "return_on_equity_pct"
        ]
    )

    roe_difference = abs(
        manual_roe
        - stored_roe
    )


    # --------------------------------------------------------
    # MANUAL 5-YEAR REVENUE CAGR
    # --------------------------------------------------------

    manual_cagr = (
        (
            end_sales
            / start_sales
        )
        ** (1 / 5)
        - 1
    ) * 100

    stored_cagr = float(
        row[
            "revenue_cagr_5yr"
        ]
    )

    cagr_difference = abs(
        manual_cagr
        - stored_cagr
    )


    results.append(
        {
            "company_id":
                company,

            "year":
                row["year"],

            "manual_roe_pct":
                manual_roe,

            "stored_roe_pct":
                stored_roe,

            "roe_difference_pp":
                roe_difference,

            "roe_pass":
                roe_difference <= 0.1,

            "cagr_start_year":
                start_year,

            "cagr_end_year":
                end_year,

            "manual_revenue_cagr_5yr":
                manual_cagr,

            "stored_revenue_cagr_5yr":
                stored_cagr,

            "cagr_difference_pp":
                cagr_difference,

            "cagr_pass":
                cagr_difference <= 0.1,
        }
    )


result = pd.DataFrame(
    results
)

OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

result.to_csv(
    OUT,
    index=False,
)


print()
print("=" * 70)
print("SPRINT 2 MANUAL VALIDATION")
print("=" * 70)


for _, row in result.iterrows():

    print()
    print(
        row["company_id"],
        "| Year:",
        row["year"],
    )

    print(
        "ROE:",
        round(
            row["manual_roe_pct"],
            4,
        ),
        "vs",
        round(
            row["stored_roe_pct"],
            4,
        ),
        "| Diff:",
        round(
            row["roe_difference_pp"],
            6,
        ),
        "|",
        "PASS"
        if row["roe_pass"]
        else "FAIL",
    )

    print(
        "Revenue CAGR 5Y:",
        round(
            row[
                "manual_revenue_cagr_5yr"
            ],
            4,
        ),
        "vs",
        round(
            row[
                "stored_revenue_cagr_5yr"
            ],
            4,
        ),
        "| Diff:",
        round(
            row[
                "cagr_difference_pp"
            ],
            6,
        ),
        "|",
        "PASS"
        if row["cagr_pass"]
        else "FAIL",
    )


overall = bool(
    result[
        [
            "roe_pass",
            "cagr_pass",
        ]
    ]
    .all()
    .all()
)


print()
print(
    "Validation file:",
    OUT.resolve(),
)

print()

print(
    "3-COMPANY MANUAL VALIDATION:",
    "PASS"
    if overall
    else "FAIL",
)
