"""Sector analytics API routes."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.database import fetch_all


router = APIRouter(
    prefix="/api/v1",
    tags=["Sectors"],
)


def safe_records(
    frame: pd.DataFrame,
) -> list[dict]:
    """Convert DataFrame to JSON-safe records."""

    return (
        frame.astype(object)
        .where(
            pd.notna(frame),
            None,
        )
        .to_dict(
            orient="records"
        )
    )


@router.get(
    "/sectors",
    summary="Sector statistics",
)
def sector_statistics() -> list[dict]:
    """Return sector counts and median KPIs."""

    rows = fetch_all(
        """
        SELECT
            s.broad_sector,

            r.return_on_equity_pct
                AS roe,

            r.debt_to_equity,

            m.pe_ratio

        FROM sectors s

        LEFT JOIN financial_ratios r
            ON r.company_id = s.company_id
           AND r.year = (
                SELECT MAX(fr.year)
                FROM financial_ratios fr
                WHERE fr.company_id
                    = s.company_id
                  AND fr.year <> 'TTM'
           )

        LEFT JOIN market_cap m
            ON m.company_id = s.company_id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id
                    = s.company_id
           )
        """
    )

    frame = pd.DataFrame(
        rows
    )

    output = []

    for sector, group in (
        frame.groupby(
            "broad_sector"
        )
    ):

        output.append(
            {
                "sector_name":
                    sector,

                "company_count":
                    int(
                        len(group)
                    ),

                "median_roe":
                    group[
                        "roe"
                    ].median(),

                "median_pe":
                    group[
                        "pe_ratio"
                    ].median(),

                "median_de":
                    group[
                        "debt_to_equity"
                    ].median(),
            }
        )

    result = pd.DataFrame(
        output
    )

    return safe_records(
        result.sort_values(
            "sector_name"
        )
    )


@router.get(
    "/sectors/{sector}/companies",
    summary="Companies in sector",
)
def sector_companies(
    sector: str,
    year: str | None = None,
) -> list[dict]:
    """Return KPI summary for a sector."""

    sector_row = fetch_all(
        """
        SELECT DISTINCT broad_sector
        FROM sectors
        WHERE LOWER(broad_sector)
            = LOWER(?)
        """,
        (
            sector.strip(),
        ),
    )

    if not sector_row:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Sector '{sector}' "
                "was not found."
            ),
        )

    rows = fetch_all(
        """
        SELECT
            c.id AS ticker,
            c.company_name,
            s.broad_sector,
            s.sub_sector,

            r.year,

            r.return_on_equity_pct
                AS roe,
            r.return_on_capital_employed_pct
                AS roce,
            r.operating_profit_margin_pct
                AS opm,
            r.net_profit_margin_pct
                AS npm,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,

            m.pe_ratio

        FROM sectors s

        JOIN companies c
            ON c.id = s.company_id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = COALESCE(
                ?,
                (
                    SELECT MAX(fr.year)
                    FROM financial_ratios fr
                    WHERE fr.company_id = c.id
                      AND fr.year <> 'TTM'
                )
           )

        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id = c.id
           )

        WHERE LOWER(s.broad_sector)
            = LOWER(?)

        ORDER BY c.company_name
        """,
        (
            year,
            sector.strip(),
        ),
    )

    return rows