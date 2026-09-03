
"""Repair CAGR numeric values and flags in financial_ratios."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.cagr import calculate_cagr_with_flag


DB = Path("data/nifty100.db")
OUT = Path("output/cagr_population_validation.csv")


def year_number(value):
    """Convert normalized FY value to calendar year."""

    if value is None:
        return None

    text = str(value).strip()

    if text.upper() == "TTM":
        return None

    try:
        return int(text[:4])
    except (TypeError, ValueError):
        return None


def numeric(value):
    """Return finite float or None."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not np.isfinite(result):
        return None

    return result


# Detect whether the existing CAGR engine returns:
# 0.10 or 10.0 for a 10% CAGR.
probe_value, probe_flag = calculate_cagr_with_flag(
    100.0,
    161.051,
    5,
)

if probe_value is None:
    raise RuntimeError(
        "CAGR engine probe unexpectedly returned None."
    )

probe_value = float(probe_value)

if abs(probe_value - 0.10) < 0.02:
    SCALE = 100.0

elif abs(probe_value - 10.0) < 1.0:
    SCALE = 1.0

else:
    raise RuntimeError(
        f"Unable to determine CAGR scale. Probe={probe_value}"
    )


print(
    "Detected CAGR engine scale:",
    "fraction -> percent"
    if SCALE == 100.0
    else "already percent",
)


with sqlite3.connect(DB) as conn:

    pnl = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            sales,
            net_profit,
            eps
        FROM profitandloss
        """,
        conn,
    )

    ratios = pd.read_sql_query(
        """
        SELECT
            company_id,
            year
        FROM financial_ratios
        """,
        conn,
    )


for df in [pnl, ratios]:

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


pnl["_year_number"] = pnl[
    "year"
].apply(
    year_number
)


valid_pnl = pnl[
    pnl["_year_number"].notna()
].copy()

valid_pnl["_year_number"] = valid_pnl[
    "_year_number"
].astype(int)


valid_pnl = (
    valid_pnl
    .sort_values(
        [
            "company_id",
            "_year_number",
            "year",
        ]
    )
    .drop_duplicates(
        subset=[
            "company_id",
            "_year_number",
        ],
        keep="last",
    )
)


metric_columns = {
    "revenue": "sales",
    "pat": "net_profit",
    "eps": "eps",
}


lookups = {}

for metric_name, source_column in metric_columns.items():

    lookup = {}

    for _, row in valid_pnl.iterrows():

        lookup[
            (
                row["company_id"],
                int(row["_year_number"]),
            )
        ] = numeric(
            row[source_column]
        )

    lookups[
        metric_name
    ] = lookup


def calculate_for_row(
    company_id,
    year,
    metric,
    period,
):
    """Calculate one CAGR value and its flag."""

    current_year = year_number(
        year
    )

    if current_year is None:
        return None, "INSUFFICIENT"

    lookup = lookups[
        metric
    ]

    start_key = (
        company_id,
        current_year - period,
    )

    end_key = (
        company_id,
        current_year,
    )

    if (
        start_key not in lookup
        or end_key not in lookup
    ):
        return None, "INSUFFICIENT"

    start_value = lookup[
        start_key
    ]

    end_value = lookup[
        end_key
    ]

    if (
        start_value is None
        or end_value is None
    ):
        return None, "INSUFFICIENT"

    value, flag = calculate_cagr_with_flag(
        start_value,
        end_value,
        period,
    )

    if value is not None:
        value = float(value) * SCALE

    return value, flag


output_columns = []

for metric in [
    "revenue",
    "pat",
    "eps",
]:

    for period in [
        3,
        5,
        10,
    ]:

        value_column = (
            f"{metric}_cagr_{period}yr"
        )

        flag_column = (
            f"{metric}_cagr_{period}yr_flag"
        )

        values = []
        flags = []

        for _, row in ratios.iterrows():

            value, flag = calculate_for_row(
                row["company_id"],
                row["year"],
                metric,
                period,
            )

            values.append(
                value
            )

            flags.append(
                flag
            )

        ratios[
            value_column
        ] = values

        ratios[
            flag_column
        ] = flags

        output_columns.extend(
            [
                value_column,
                flag_column,
            ]
        )


with sqlite3.connect(DB) as conn:

    existing = {
        row[1]
        for row in conn.execute(
            """
            PRAGMA table_info(
                financial_ratios
            )
            """
        ).fetchall()
    }


    for metric in [
        "revenue",
        "pat",
        "eps",
    ]:

        for period in [
            3,
            5,
            10,
        ]:

            value_column = (
                f"{metric}_cagr_{period}yr"
            )

            flag_column = (
                f"{metric}_cagr_{period}yr_flag"
            )

            if value_column not in existing:

                conn.execute(
                    f"""
                    ALTER TABLE financial_ratios
                    ADD COLUMN {value_column} REAL
                    """
                )

            if flag_column not in existing:

                conn.execute(
                    f"""
                    ALTER TABLE financial_ratios
                    ADD COLUMN {flag_column} TEXT
                    """
                )


    update_columns = output_columns

    set_clause = ", ".join(
        f"{column} = ?"
        for column in update_columns
    )

    sql = f"""
    UPDATE financial_ratios
    SET {set_clause}
    WHERE company_id = ?
      AND year = ?
    """


    records = []

    for _, row in ratios.iterrows():

        values = []

        for column in update_columns:

            value = row[
                column
            ]

            if pd.isna(value):
                value = None

            elif isinstance(
                value,
                np.generic,
            ):
                value = value.item()

            values.append(
                value
            )

        values.extend(
            [
                row["company_id"],
                row["year"],
            ]
        )

        records.append(
            tuple(values)
        )


    conn.executemany(
        sql,
        records,
    )

    conn.commit()


# ============================================================
# VALIDATION
# ============================================================

with sqlite3.connect(DB) as conn:

    validation = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            revenue_cagr_3yr,
            revenue_cagr_5yr,
            revenue_cagr_10yr,
            pat_cagr_3yr,
            pat_cagr_5yr,
            pat_cagr_10yr,
            eps_cagr_3yr,
            eps_cagr_5yr,
            eps_cagr_10yr,
            revenue_cagr_5yr_flag
        FROM financial_ratios
        """,
        conn,
    )


OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

validation.to_csv(
    OUT,
    index=False,
)


print()
print("=" * 72)
print("CAGR POPULATION VALIDATION")
print("=" * 72)

for metric in [
    "revenue",
    "pat",
    "eps",
]:

    for period in [
        3,
        5,
        10,
    ]:

        column = (
            f"{metric}_cagr_{period}yr"
        )

        populated = int(
            validation[
                column
            ].notna().sum()
        )

        print(
            f"{column:<25}",
            "non-null:",
            populated,
        )


tcs = validation[
    validation["company_id"] == "TCS"
][
    [
        "year",
        "revenue_cagr_5yr",
        "revenue_cagr_5yr_flag",
    ]
]


print()
print("TCS Revenue CAGR 5Y:")
print(
    tcs.to_string(
        index=False
    )
)


tcs_valid = int(
    tcs[
        "revenue_cagr_5yr"
    ].notna().sum()
)


print()
print(
    "TCS non-null Revenue CAGR 5Y:",
    tcs_valid,
)

print(
    "Validation file:",
    OUT.resolve(),
)


if tcs_valid > 0:
    print(
        "CAGR NUMERIC POPULATION: PASS"
    )
else:
    print(
        "CAGR NUMERIC POPULATION: FAIL"
    )
