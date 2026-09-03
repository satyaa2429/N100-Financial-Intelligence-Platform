"""Generate Sprint 2 financial ratio edge-case log."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.analytics.cagr import compute_cagr_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
LOG_PATH = PROJECT_ROOT / "ratio_edge_cases.log"


def add_entry(
    entries: list[str],
    case_type: str,
    company_id: object,
    year: object,
    detail: str,
) -> None:
    """Add one formatted edge-case entry."""

    entries.append(
        f"{case_type} | "
        f"company_id={company_id} | "
        f"year={year} | "
        f"{detail}"
    )


def generate_edge_case_log() -> int:
    """Scan project data and write all detected ratio edge cases."""

    entries: list[str] = []

    with sqlite3.connect(DB_PATH) as conn:

        pnl = pd.read_sql_query(
            """
            SELECT
                company_id,
                year,
                sales,
                operating_profit,
                other_income,
                interest,
                depreciation,
                net_profit,
                eps
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
                reserves,
                borrowings,
                total_assets
            FROM balancesheet
            """,
            conn,
        )

        cf = pd.read_sql_query(
            """
            SELECT
                company_id,
                year,
                operating_activity,
                investing_activity,
                financing_activity
            FROM cashflow
            """,
            conn,
        )

    # ========================================================
    # P&L EDGE CASES
    # ========================================================

    pnl["sales_num"] = pd.to_numeric(
        pnl["sales"],
        errors="coerce",
    )

    pnl["interest_num"] = pd.to_numeric(
        pnl["interest"],
        errors="coerce",
    )

    pnl["net_profit_num"] = pd.to_numeric(
        pnl["net_profit"],
        errors="coerce",
    )

    pnl["operating_profit_num"] = pd.to_numeric(
        pnl["operating_profit"],
        errors="coerce",
    )

    for _, row in pnl[
        pnl["sales_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DIVISION_BY_ZERO_SALES",
            row["company_id"],
            row["year"],
            "NPM=None; OPM=None because sales=0",
        )

    for _, row in pnl[
        pnl["interest_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DEBT_FREE_ICR",
            row["company_id"],
            row["year"],
            "interest=0; ICR=None; display=Debt Free",
        )

    # ========================================================
    # BALANCE SHEET EDGE CASES
    # ========================================================

    bs["equity_capital_num"] = pd.to_numeric(
        bs["equity_capital"],
        errors="coerce",
    )

    bs["reserves_num"] = pd.to_numeric(
        bs["reserves"],
        errors="coerce",
    )

    bs["borrowings_num"] = pd.to_numeric(
        bs["borrowings"],
        errors="coerce",
    )

    bs["total_assets_num"] = pd.to_numeric(
        bs["total_assets"],
        errors="coerce",
    )

    bs["total_equity"] = (
        bs["equity_capital_num"]
        + bs["reserves_num"]
    )

    bs["capital_employed"] = (
        bs["total_equity"]
        + bs["borrowings_num"]
    )

    for _, row in bs[
        bs["borrowings_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DEBT_FREE_DE",
            row["company_id"],
            row["year"],
            "borrowings=0; debt_to_equity=0",
        )

    for _, row in bs[
        bs["total_equity"] <= 0
    ].iterrows():

        add_entry(
            entries,
            "INVALID_EQUITY",
            row["company_id"],
            row["year"],
            "equity+reserves<=0; ROE=None",
        )

    for _, row in bs[
        bs["total_assets_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DIVISION_BY_ZERO_ASSETS",
            row["company_id"],
            row["year"],
            "total_assets=0; asset_turnover=None",
        )

    for _, row in bs[
        bs["capital_employed"] <= 0
    ].iterrows():

        add_entry(
            entries,
            "INVALID_CAPITAL_EMPLOYED",
            row["company_id"],
            row["year"],
            "equity+reserves+borrowings<=0; ROCE=None",
        )

    # ========================================================
    # CASH FLOW EDGE CASES
    # ========================================================

    cash_join = cf.merge(
        pnl[
            [
                "company_id",
                "year",
                "net_profit_num",
                "operating_profit_num",
            ]
        ],
        on=["company_id", "year"],
        how="left",
    )

    for _, row in cash_join[
        cash_join["net_profit_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DIVISION_BY_ZERO_PAT",
            row["company_id"],
            row["year"],
            "net_profit=0; CFO/PAT=None",
        )

    for _, row in cash_join[
        cash_join["operating_profit_num"] == 0
    ].iterrows():

        add_entry(
            entries,
            "DIVISION_BY_ZERO_OPERATING_PROFIT",
            row["company_id"],
            row["year"],
            "operating_profit=0; FCF conversion=None",
        )

    # ========================================================
    # CAGR EDGE CASES
    # ========================================================

    cagr_input = pnl[
        [
            "company_id",
            "year",
            "sales",
            "net_profit",
            "eps",
        ]
    ].copy()

    cagr_result = compute_cagr_metrics(
        cagr_input
    )

    if not cagr_result.empty:

        cagr_result["start_num"] = pd.to_numeric(
            cagr_result["start_value"],
            errors="coerce",
        )

        cagr_result["end_num"] = pd.to_numeric(
            cagr_result["end_value"],
            errors="coerce",
        )

        for _, row in cagr_result.iterrows():

            start = row["start_num"]
            end = row["end_num"]

            detail = (
                f"metric={row['metric']}; "
                f"window={row['window_years']}yr; "
                f"start={row['start_value']}; "
                f"end={row['end_value']}"
            )

            if pd.isna(start):

                add_entry(
                    entries,
                    "CAGR_INSUFFICIENT_HISTORY",
                    row["company_id"],
                    row["year"],
                    detail + "; CAGR=None",
                )

            elif start == 0:

                add_entry(
                    entries,
                    "CAGR_ZERO_BASE",
                    row["company_id"],
                    row["year"],
                    detail + "; CAGR=None; flag=ZERO_BASE",
                )

            elif (
                start < 0
                and not pd.isna(end)
                and end > 0
            ):

                add_entry(
                    entries,
                    "CAGR_TURNAROUND",
                    row["company_id"],
                    row["year"],
                    detail + "; CAGR=None; flag=TURNAROUND",
                )

            elif (
                start > 0
                and not pd.isna(end)
                and end < 0
            ):

                add_entry(
                    entries,
                    "CAGR_DECLINE_TO_LOSS",
                    row["company_id"],
                    row["year"],
                    detail + "; CAGR=None; flag=DECLINE_TO_LOSS",
                )

            elif (
                start < 0
                and not pd.isna(end)
                and end < 0
            ):

                add_entry(
                    entries,
                    "CAGR_BOTH_NEGATIVE",
                    row["company_id"],
                    row["year"],
                    detail + "; CAGR=None; flag=BOTH_NEGATIVE",
                )

    entries.sort()

    header = [
        "N100 FINANCIAL INTELLIGENCE PLATFORM",
        "SPRINT 2 - RATIO ENGINE EDGE CASE LOG",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Database: {DB_PATH}",
        f"Total edge cases: {len(entries)}",
        "",
    ]

    LOG_PATH.write_text(
        "\n".join(
            header + entries
        ),
        encoding="utf-8",
    )

    return len(entries)


def main() -> None:
    """Generate ratio edge-case log."""

    count = generate_edge_case_log()

    print(
        "Edge cases logged:",
        count,
    )

    print(
        "Saved:",
        LOG_PATH,
    )


if __name__ == "__main__":
    main()
