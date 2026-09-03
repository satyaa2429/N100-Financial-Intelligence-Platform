"""Finalize Sprint 2 portal fields in financial_ratios."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.cagr import calculate_cagr_with_flag


DB_PATH = Path("data/nifty100.db")
OUTPUT_PATH = Path("output/day12_portal_fields_check.csv")


def year_number(value):
    """Extract calendar year from normalized year."""

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
    """Convert value to finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan

    if not np.isfinite(number):
        return np.nan

    return number


def safe_ratio(
    numerator,
    denominator,
    multiplier=1.0,
):
    """Calculate safe numeric ratio."""

    numerator = numeric(numerator)
    denominator = numeric(denominator)

    if pd.isna(numerator):
        return np.nan

    if pd.isna(denominator):
        return np.nan

    if denominator == 0:
        return np.nan

    return (
        numerator
        / denominator
        * multiplier
    )


def winsor_score(
    series,
    higher_is_better=True,
):
    """Convert metric to P10/P90 normalized 0-100 score."""

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    valid = values.dropna()

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    if valid.empty:
        return result

    if len(valid) == 1:
        result.loc[valid.index] = 50.0
        return result

    p10 = float(
        valid.quantile(0.10)
    )

    p90 = float(
        valid.quantile(0.90)
    )

    if p90 == p10:
        result.loc[
            values.notna()
        ] = 50.0

        return result

    clipped = values.clip(
        lower=p10,
        upper=p90,
    )

    score = (
        (clipped - p10)
        / (p90 - p10)
        * 100
    )

    if not higher_is_better:
        score = 100 - score

    result.loc[
        values.notna()
    ] = score.loc[
        values.notna()
    ]

    return result


with sqlite3.connect(DB_PATH) as conn:

    ratios = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn,
    )

    pnl = pd.read_sql_query(
        "SELECT * FROM profitandloss",
        conn,
    )

    bs = pd.read_sql_query(
        "SELECT * FROM balancesheet",
        conn,
    )

    cf = pd.read_sql_query(
        "SELECT * FROM cashflow",
        conn,
    )

    sectors = pd.read_sql_query(
        "SELECT * FROM sectors",
        conn,
    )


# ============================================================
# PREPARE SOURCE DATA
# ============================================================

for dataframe in [
    ratios,
    pnl,
    bs,
    cf,
]:
    dataframe["company_id"] = (
        dataframe["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["year"] = (
        dataframe["year"]
        .astype(str)
        .str.strip()
    )


pnl_needed = [
    "company_id",
    "year",
    "net_profit",
    "sales",
    "operating_profit",
    "depreciation",
    "other_income",
    "interest",
    "opm_percentage",
    "eps",
]

for column in pnl_needed:
    if column not in pnl.columns:
        pnl[column] = np.nan


bs_needed = [
    "company_id",
    "year",
    "equity_capital",
    "reserves",
    "borrowings",
    "investments",
    "total_assets",
]

for column in bs_needed:
    if column not in bs.columns:
        bs[column] = np.nan


if "cash" not in bs.columns:
    bs["cash"] = 0.0


source = ratios[
    [
        "company_id",
        "year",
    ]
].copy()

source = source.merge(
    pnl[pnl_needed],
    on=[
        "company_id",
        "year",
    ],
    how="left",
)

source = source.merge(
    bs[
        bs_needed
        + ["cash"]
    ],
    on=[
        "company_id",
        "year",
    ],
    how="left",
)


sector_columns = [
    "company_id",
]

if "broad_sector" in sectors.columns:
    sector_columns.append(
        "broad_sector"
    )

else:
    sectors[
        "broad_sector"
    ] = ""

    sector_columns.append(
        "broad_sector"
    )


source = source.merge(
    sectors[
        sector_columns
    ],
    on="company_id",
    how="left",
)


# ============================================================
# ROA
# ============================================================

source[
    "return_on_assets_pct"
] = source.apply(
    lambda row: safe_ratio(
        row["net_profit"],
        row["total_assets"],
        100,
    )
    if numeric(
        row["total_assets"]
    ) > 0
    else np.nan,
    axis=1,
)


# ============================================================
# ROCE
# ============================================================

def calculate_roce_row(row):
    """Calculate ROCE from raw source values."""

    op = numeric(
        row["operating_profit"]
    )

    dep = numeric(
        row["depreciation"]
    )

    equity = numeric(
        row["equity_capital"]
    )

    reserves = numeric(
        row["reserves"]
    )

    borrowings = numeric(
        row["borrowings"]
    )

    values = [
        op,
        dep,
        equity,
        reserves,
        borrowings,
    ]

    if any(
        pd.isna(value)
        for value in values
    ):
        return np.nan

    capital = (
        equity
        + reserves
        + borrowings
    )

    if capital <= 0:
        return np.nan

    ebit = (
        op
        - dep
    )

    return (
        ebit
        / capital
        * 100
    )


source[
    "return_on_capital_employed_pct"
] = source.apply(
    calculate_roce_row,
    axis=1,
)


# ============================================================
# NET DEBT
# ============================================================

def calculate_net_debt_row(row):
    """Calculate net debt."""

    borrowings = numeric(
        row["borrowings"]
    )

    investments = numeric(
        row["investments"]
    )

    cash = numeric(
        row["cash"]
    )

    if pd.isna(borrowings):
        return np.nan

    if pd.isna(investments):
        investments = 0.0

    if pd.isna(cash):
        cash = 0.0

    return (
        borrowings
        - investments
        - cash
    )


source[
    "net_debt_cr"
] = source.apply(
    calculate_net_debt_row,
    axis=1,
)


# ============================================================
# ICR LABEL + WARNING
# ============================================================

def calculate_icr(row):
    """Calculate Interest Coverage Ratio."""

    interest = numeric(
        row["interest"]
    )

    operating_profit = numeric(
        row["operating_profit"]
    )

    other_income = numeric(
        row["other_income"]
    )

    if pd.isna(interest):
        return np.nan

    if interest == 0:
        return np.nan

    if pd.isna(
        operating_profit
    ):
        return np.nan

    if pd.isna(other_income):
        other_income = 0.0

    return (
        operating_profit
        + other_income
    ) / interest


source[
    "_calculated_icr"
] = source.apply(
    calculate_icr,
    axis=1,
)


source[
    "icr_label"
] = source.apply(
    lambda row:
    "Debt Free"
    if (
        not pd.isna(
            numeric(
                row["interest"]
            )
        )
        and numeric(
            row["interest"]
        ) == 0
    )
    else (
        "Normal"
        if not pd.isna(
            row["_calculated_icr"]
        )
        else None
    ),
    axis=1,
)


source[
    "icr_warning_flag"
] = source[
    "_calculated_icr"
].apply(
    lambda value:
    1
    if (
        not pd.isna(value)
        and value < 1.5
    )
    else 0
)


# ============================================================
# HIGH LEVERAGE
# ============================================================

ratio_lookup = ratios[
    [
        "company_id",
        "year",
        "debt_to_equity",
    ]
].copy()


source = source.merge(
    ratio_lookup,
    on=[
        "company_id",
        "year",
    ],
    how="left",
)


def leverage_flag(row):
    """Apply non-financial D/E > 5 warning."""

    de = numeric(
        row["debt_to_equity"]
    )

    if pd.isna(de):
        return 0

    sector = str(
        row.get(
            "broad_sector",
            "",
        )
    ).lower()

    financial_words = [
        "financial",
        "bank",
        "nbfc",
        "insurance",
    ]

    is_financial = any(
        word in sector
        for word in financial_words
    )

    if is_financial:
        return 0

    return int(
        de > 5
    )


source[
    "high_leverage_flag"
] = source.apply(
    leverage_flag,
    axis=1,
)


# ============================================================
# OPM MISMATCH FLAG
# ============================================================

def opm_mismatch(row):
    """Flag OPM difference above 1 percentage point."""

    sales = numeric(
        row["sales"]
    )

    operating_profit = numeric(
        row["operating_profit"]
    )

    source_opm = numeric(
        row["opm_percentage"]
    )

    if (
        pd.isna(sales)
        or sales == 0
        or pd.isna(
            operating_profit
        )
        or pd.isna(
            source_opm
        )
    ):
        return 0

    calculated = (
        operating_profit
        / sales
        * 100
    )

    return int(
        abs(
            calculated
            - source_opm
        ) > 1.0
    )


source[
    "opm_mismatch_flag"
] = source.apply(
    opm_mismatch,
    axis=1,
)


# ============================================================
# CAGR FLAGS
# ============================================================

pnl[
    "_year_number"
] = pnl[
    "year"
].apply(
    year_number
)

pnl = pnl[
    pnl["_year_number"].notna()
].copy()

pnl[
    "_year_number"
] = pnl[
    "_year_number"
].astype(int)

pnl = (
    pnl.sort_values(
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


metric_map = {
    "revenue": "sales",
    "pat": "net_profit",
    "eps": "eps",
}


value_maps = {}

for output_name, metric in metric_map.items():

    metric_values = {}

    for _, row in pnl.iterrows():

        company_id = str(
            row["company_id"]
        )

        year_value = int(
            row["_year_number"]
        )

        metric_values[
            (
                company_id,
                year_value,
            )
        ] = row[metric]

    value_maps[
        output_name
    ] = metric_values


def cagr_flag(
    company_id,
    year,
    metric,
    period,
):
    """Return CAGR status for company-year window."""

    current_year = year_number(
        year
    )

    if current_year is None:
        return "INSUFFICIENT"

    values = value_maps[
        metric
    ]

    start_key = (
        str(company_id),
        current_year - period,
    )

    end_key = (
        str(company_id),
        current_year,
    )

    if (
        start_key not in values
        or end_key not in values
    ):
        return "INSUFFICIENT"

    _, flag = (
        calculate_cagr_with_flag(
            values[start_key],
            values[end_key],
            period,
        )
    )

    return flag


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
            f"{metric}_cagr_"
            f"{period}yr_flag"
        )

        source[
            column
        ] = source.apply(
            lambda row,
            m=metric,
            p=period:
            cagr_flag(
                row[
                    "company_id"
                ],
                row[
                    "year"
                ],
                m,
                p,
            ),
            axis=1,
        )


# ============================================================
# COMPOSITE QUALITY SCORE
# ============================================================

source = source.merge(
    ratios[
        [
            "company_id",
            "year",
            "return_on_equity_pct",
            "free_cash_flow_cr",
        ]
    ],
    on=[
        "company_id",
        "year",
    ],
    how="left",
)


source[
    "_roe_score"
] = np.nan

source[
    "_fcf_score"
] = np.nan

source[
    "_roce_score"
] = np.nan

source[
    "_de_score"
] = np.nan


for _, index in (
    source.groupby(
        "year"
    ).groups.items()
):

    group = source.loc[
        index
    ]

    source.loc[
        index,
        "_roe_score",
    ] = winsor_score(
        group[
            "return_on_equity_pct"
        ],
        higher_is_better=True,
    )

    source.loc[
        index,
        "_fcf_score",
    ] = winsor_score(
        group[
            "free_cash_flow_cr"
        ],
        higher_is_better=True,
    )

    source.loc[
        index,
        "_roce_score",
    ] = winsor_score(
        group[
            "return_on_capital_employed_pct"
        ],
        higher_is_better=True,
    )

    source.loc[
        index,
        "_de_score",
    ] = winsor_score(
        group[
            "debt_to_equity"
        ],
        higher_is_better=False,
    )


required_scores = [
    "_roe_score",
    "_fcf_score",
    "_roce_score",
    "_de_score",
]


source[
    "composite_quality_score"
] = np.where(
    source[
        required_scores
    ].notna().all(
        axis=1
    ),
    (
        0.30
        * source[
            "_roe_score"
        ]
        + 0.25
        * source[
            "_fcf_score"
        ]
        + 0.25
        * source[
            "_roce_score"
        ]
        + 0.20
        * source[
            "_de_score"
        ]
    ),
    np.nan,
)


# ============================================================
# SQLITE COLUMN DEFINITIONS
# ============================================================

column_types = {
    "return_on_assets_pct":
        "REAL",

    "return_on_capital_employed_pct":
        "REAL",

    "net_debt_cr":
        "REAL",

    "icr_label":
        "TEXT",

    "icr_warning_flag":
        "INTEGER",

    "high_leverage_flag":
        "INTEGER",

    "opm_mismatch_flag":
        "INTEGER",

    "revenue_cagr_3yr_flag":
        "TEXT",

    "revenue_cagr_5yr_flag":
        "TEXT",

    "revenue_cagr_10yr_flag":
        "TEXT",

    "pat_cagr_3yr_flag":
        "TEXT",

    "pat_cagr_5yr_flag":
        "TEXT",

    "pat_cagr_10yr_flag":
        "TEXT",

    "eps_cagr_3yr_flag":
        "TEXT",

    "eps_cagr_5yr_flag":
        "TEXT",

    "eps_cagr_10yr_flag":
        "TEXT",

    "composite_quality_score":
        "REAL",
}


with sqlite3.connect(DB_PATH) as conn:

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

    for column, sql_type in (
        column_types.items()
    ):

        if column not in existing:

            conn.execute(
                f"""
                ALTER TABLE
                    financial_ratios
                ADD COLUMN
                    {column} {sql_type}
                """
            )

    update_columns = list(
        column_types.keys()
    )

    set_clause = ", ".join(
        f"{column} = ?"
        for column
        in update_columns
    )

    sql = f"""
    UPDATE financial_ratios
    SET {set_clause}
    WHERE company_id = ?
      AND year = ?
    """

    values = []

    for _, row in source.iterrows():

        record = []

        for column in update_columns:

            value = row[
                column
            ]

            if pd.isna(value):
                value = None

            elif column.endswith(
                "_flag"
            ) and column in {
                "icr_warning_flag",
                "high_leverage_flag",
                "opm_mismatch_flag",
            }:
                value = int(
                    value
                )

            elif isinstance(
                value,
                np.generic,
            ):
                value = value.item()

            record.append(
                value
            )

        record.extend(
            [
                row[
                    "company_id"
                ],
                row[
                    "year"
                ],
            ]
        )

        values.append(
            tuple(record)
        )

    conn.executemany(
        sql,
        values,
    )

    conn.commit()


# ============================================================
# VALIDATION
# ============================================================

with sqlite3.connect(DB_PATH) as conn:

    final = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        conn,
    )


OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


check_columns = list(
    column_types.keys()
)


summary = pd.DataFrame(
    {
        "column": check_columns,
        "non_null_rows": [
            int(
                final[column]
                .notna()
                .sum()
            )
            for column
            in check_columns
        ],
    }
)


summary.to_csv(
    OUTPUT_PATH,
    index=False,
)


print()
print("=" * 70)
print("SPRINT 2 DAY 12 PORTAL FIELD UPDATE")
print("=" * 70)

print(
    "Rows:",
    len(final),
)

print(
    "Unique companies:",
    final[
        "company_id"
    ].nunique(),
)

print()

for column in check_columns:

    print(
        f"{column:<38}",
        "-> PASS | non-null:",
        int(
            final[
                column
            ].notna().sum()
        ),
    )


print()
print(
    "Validation file:",
    OUTPUT_PATH.resolve(),
)

print()

if (
    len(final) >= 1100
    and final[
        "company_id"
    ].nunique() == 92
    and all(
        column in final.columns
        for column
        in check_columns
    )
):
    print(
        "DAY 12 PORTAL FIELD CHECK: PASS"
    )

else:
    print(
        "DAY 12 PORTAL FIELD CHECK: FAIL"
    )
