"""Populate the SQLite financial_ratios table with computed KPIs."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import create_cagr_wide_table
from src.analytics.cashflow_kpis import compute_cashflow_kpis
from src.analytics.ratios import compute_financial_ratios
from src.etl.loader import load_all_core_datasets


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
OUTPUT_DIR = PROJECT_ROOT / "output"
VALIDATION_FILE = OUTPUT_DIR / "day12_ratio_validation.csv"


NEW_COLUMNS = {
    "return_on_capital_employed_pct": "REAL",
    "revenue_cagr_3yr": "REAL",
    "revenue_cagr_5yr": "REAL",
    "revenue_cagr_10yr": "REAL",
    "pat_cagr_3yr": "REAL",
    "pat_cagr_5yr": "REAL",
    "pat_cagr_10yr": "REAL",
    "eps_cagr_3yr": "REAL",
    "eps_cagr_5yr": "REAL",
    "eps_cagr_10yr": "REAL",
    "cfo_pat_ratio": "REAL",
    "capex_intensity_pct": "REAL",
    "fcf_conversion_pct": "REAL",
}


def safe_float(value: object) -> float | None:
    """Convert a value to float or return None."""

    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(result):
        return None

    return result


def calculate_book_value_per_share(
    equity_capital: object,
    reserves: object,
    face_value: object,
) -> float | None:
    """Calculate book value per share."""

    equity_capital_value = safe_float(
        equity_capital
    )
    reserves_value = safe_float(
        reserves
    )
    face_value_value = safe_float(
        face_value
    )

    if (
        equity_capital_value is None
        or reserves_value is None
        or face_value_value is None
    ):
        return None

    if equity_capital_value == 0:
        return None

    shares = (
        equity_capital_value
        / face_value_value
    )

    if shares == 0:
        return None

    return (
        equity_capital_value
        + reserves_value
    ) / shares


def ensure_database_columns(
    conn: sqlite3.Connection,
) -> None:
    """Add Sprint 2 KPI columns when they do not already exist."""

    existing = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(financial_ratios)"
        ).fetchall()
    }

    for column_name, column_type in NEW_COLUMNS.items():

        if column_name not in existing:
            conn.execute(
                f"ALTER TABLE financial_ratios "
                f"ADD COLUMN {column_name} {column_type}"
            )

    conn.commit()


def prepare_numeric_columns(
    dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Convert selected DataFrame columns to numeric."""

    result = dataframe.copy()

    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

    return result


def build_ratio_table() -> pd.DataFrame:
    """Compute the complete Sprint 2 ratio dataset."""

    datasets = load_all_core_datasets(
        clean=True
    )

    pnl = prepare_numeric_columns(
        datasets["profitandloss"],
        [
            "sales",
            "expenses",
            "operating_profit",
            "opm_percentage",
            "other_income",
            "interest",
            "depreciation",
            "net_profit",
            "eps",
            "dividend_payout",
        ],
    )

    bs = prepare_numeric_columns(
        datasets["balancesheet"],
        [
            "equity_capital",
            "reserves",
            "borrowings",
            "total_assets",
        ],
    )

    cf = prepare_numeric_columns(
        datasets["cashflow"],
        [
            "operating_activity",
            "investing_activity",
            "financing_activity",
            "net_cash_flow",
        ],
    )

    companies = prepare_numeric_columns(
        datasets["companies"],
        [
            "face_value",
        ],
    )

    # --------------------------------------------------------
    # DAY 8 + DAY 9 RATIOS
    # --------------------------------------------------------

    ratios = compute_financial_ratios(
        pnl,
        bs,
    )

    # --------------------------------------------------------
    # DAY 10 CAGR
    # --------------------------------------------------------

    cagr = create_cagr_wide_table(
        pnl
    )

    rename_cagr = {
        "revenue_cagr_3yr_pct":
            "revenue_cagr_3yr",
        "revenue_cagr_5yr_pct":
            "revenue_cagr_5yr",
        "revenue_cagr_10yr_pct":
            "revenue_cagr_10yr",

        "pat_cagr_3yr_pct":
            "pat_cagr_3yr",
        "pat_cagr_5yr_pct":
            "pat_cagr_5yr",
        "pat_cagr_10yr_pct":
            "pat_cagr_10yr",

        "eps_cagr_3yr_pct":
            "eps_cagr_3yr",
        "eps_cagr_5yr_pct":
            "eps_cagr_5yr",
        "eps_cagr_10yr_pct":
            "eps_cagr_10yr",
    }

    cagr = cagr.rename(
        columns=rename_cagr
    )

    cagr_columns = [
        "company_id",
        "year",
        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "revenue_cagr_10yr",
        "pat_cagr_3yr",
        "pat_cagr_5yr",
        "pat_cagr_10yr",
        "eps_cagr_3yr",
        "eps_cagr_5yr",
        "eps_cagr_10yr",
    ]

    for column in cagr_columns:
        if column not in cagr.columns:
            cagr[column] = None

    ratios = ratios.merge(
        cagr[cagr_columns],
        on=[
            "company_id",
            "year",
        ],
        how="left",
    )

    # --------------------------------------------------------
    # DAY 11 CASH FLOW KPIs
    # --------------------------------------------------------

    cash_kpis = compute_cashflow_kpis(
        cf,
        pnl,
    )

    cash_columns = [
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "free_cash_flow_cr",
        "cfo_pat_ratio",
        "capex_intensity_pct",
        "fcf_conversion_pct",
    ]

    ratios = ratios.merge(
        cash_kpis[cash_columns],
        on=[
            "company_id",
            "year",
        ],
        how="left",
        suffixes=(
            "",
            "_cash",
        ),
    )

    # --------------------------------------------------------
    # COMPANY FACE VALUE
    # --------------------------------------------------------

    company_reference = companies[
        [
            "id",
            "face_value",
        ]
    ].rename(
        columns={
            "id": "company_id",
        }
    )

    ratios = ratios.merge(
        company_reference,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # OFFICIAL FINANCIAL_RATIOS FIELDS
    # --------------------------------------------------------

    ratios["capex_cr"] = (
        ratios["investing_activity"]
        .abs()
    )

    ratios["earnings_per_share"] = (
        ratios["eps"]
    )

    ratios["book_value_per_share"] = (
        ratios.apply(
            lambda row:
            calculate_book_value_per_share(
                row["equity_capital"],
                row["reserves"],
                row["face_value"],
            ),
            axis=1,
        )
    )

    ratios[
        "dividend_payout_ratio_pct"
    ] = ratios["dividend_payout"]

    ratios["total_debt_cr"] = (
        ratios["borrowings"]
    )

    ratios[
        "cash_from_operations_cr"
    ] = ratios["operating_activity"]

    final_columns = [
        "company_id",
        "year",

        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "return_on_capital_employed_pct",

        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",

        "free_cash_flow_cr",
        "capex_cr",

        "earnings_per_share",
        "book_value_per_share",
        "dividend_payout_ratio_pct",

        "total_debt_cr",
        "cash_from_operations_cr",

        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "revenue_cagr_10yr",

        "pat_cagr_3yr",
        "pat_cagr_5yr",
        "pat_cagr_10yr",

        "eps_cagr_3yr",
        "eps_cagr_5yr",
        "eps_cagr_10yr",

        "cfo_pat_ratio",
        "capex_intensity_pct",
        "fcf_conversion_pct",
    ]

    for column in final_columns:
        if column not in ratios.columns:
            ratios[column] = None

    result = ratios[
        final_columns
    ].copy()

    result = result.drop_duplicates(
        subset=[
            "company_id",
            "year",
        ],
        keep="last",
    )

    return result


def populate_database(
    ratios: pd.DataFrame,
) -> int:
    """Replace financial_ratios contents with computed KPI records."""

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        ensure_database_columns(
            conn
        )

        database_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(financial_ratios)"
            ).fetchall()
        }

        insert_columns = [
            column
            for column in ratios.columns
            if column in database_columns
        ]

        insert_data = ratios[
            insert_columns
        ].copy()

        insert_data = insert_data.where(
            pd.notna(insert_data),
            None,
        )

        conn.execute(
            "DELETE FROM financial_ratios"
        )

        insert_data.to_sql(
            "financial_ratios",
            conn,
            if_exists="append",
            index=False,
        )

        conn.commit()

        row_count = conn.execute(
            "SELECT COUNT(*) "
            "FROM financial_ratios"
        ).fetchone()[0]

        fk_failures = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk_failures:
            raise RuntimeError(
                "Foreign key check failed: "
                + str(fk_failures[:5])
            )

    return row_count


def create_validation_file(
    ratios: pd.DataFrame,
) -> None:
    """Create five-company ratio spot-check output."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sample_companies = [
        "TCS",
        "RELIANCE",
        "HDFCBANK",
        "INFY",
        "ITC",
    ]

    sample = ratios[
        ratios["company_id"].isin(
            sample_companies
        )
    ].copy()

    sample = sample[
        sample["year"] != "TTM"
    ].copy()

    sample["_year"] = pd.to_numeric(
        sample["year"]
        .astype(str)
        .str[:4],
        errors="coerce",
    )

    sample = (
        sample
        .sort_values(
            [
                "company_id",
                "_year",
            ]
        )
        .groupby(
            "company_id",
            as_index=False,
        )
        .tail(1)
    )

    validation_columns = [
        "company_id",
        "year",
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
    ]

    sample[
        validation_columns
    ].to_csv(
        VALIDATION_FILE,
        index=False,
    )


def main() -> None:
    """Run Day 12 KPI computation and database population."""

    print(
        "Building financial ratios..."
    )

    ratios = build_ratio_table()

    print(
        "Computed rows:",
        len(ratios),
    )

    row_count = populate_database(
        ratios
    )

    create_validation_file(
        ratios
    )

    print(
        "Database rows:",
        row_count,
    )

    print(
        "Unique companies:",
        ratios["company_id"].nunique(),
    )

    print(
        "Duplicate company-year rows:",
        int(
            ratios.duplicated(
                [
                    "company_id",
                    "year",
                ]
            ).sum()
        ),
    )

    print(
        "Validation file:",
        VALIDATION_FILE,
    )

    if row_count >= 1100:
        print(
            "DAY 12 ROW COUNT CHECK: PASS"
        )
    else:
        print(
            "DAY 12 ROW COUNT CHECK: FAIL"
        )


if __name__ == "__main__":
    main()
