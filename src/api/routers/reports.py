"""Report, valuation and portfolio API routes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.database import (
    PROJECT_ROOT,
    company_exists,
    fetch_all,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Reports"],
)


PORTFOLIO_METRICS = [
    "return_on_equity_pct",
    "debt_to_equity",
    "pe_ratio",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "free_cash_flow_cr",
]


@router.get(
    "/companies/{ticker}/tearsheet",
    summary="Download company tearsheet",
)
def tearsheet(
    ticker: str,
):
    """Return the pre-generated company PDF."""

    ticker = (
        ticker.strip().upper()
    )

    if not company_exists(
        ticker
    ):

        raise HTTPException(
            status_code=404,
            detail=(
                f"Company '{ticker}' "
                "was not found."
            ),
        )

    path = (
        PROJECT_ROOT
        / "reports"
        / "tearsheets"
        / f"{ticker}_tearsheet.pdf"
    )

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Tearsheet PDF "
                "was not found."
            ),
        )

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=path.name,
    )


@router.get(
    "/market-cap/{ticker}",
    summary="Historical valuation multiples",
)
def market_cap(
    ticker: str,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[dict]:
    """Return historical market-cap and valuation data."""

    ticker = (
        ticker.strip().upper()
    )

    if not company_exists(
        ticker
    ):

        raise HTTPException(
            status_code=404,
            detail=(
                f"Company '{ticker}' "
                "was not found."
            ),
        )

    query = """
        SELECT
            company_id,
            year,
            market_cap_crore,
            enterprise_value_crore,
            pe_ratio,
            pb_ratio,
            ev_ebitda,
            dividend_yield_pct
        FROM market_cap
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    params: list = [
        ticker
    ]

    if from_year is not None:

        query += """
            AND year >= ?
        """

        params.append(
            from_year
        )

    if to_year is not None:

        query += """
            AND year <= ?
        """

        params.append(
            to_year
        )

    query += """
        ORDER BY year
    """

    return fetch_all(
        query,
        tuple(params),
    )


@router.get(
    "/portfolio/stats",
    summary="Portfolio statistics",
)
def portfolio_stats(
    year: str | None = None,
) -> list[dict]:
    """Return P10-P90 statistics for ten core KPIs."""

    rows = fetch_all(
        """
        SELECT
            r.company_id,
            r.return_on_equity_pct,
            r.debt_to_equity,
            r.return_on_capital_employed_pct,
            r.net_profit_margin_pct,
            r.operating_profit_margin_pct,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,
            r.free_cash_flow_cr,
            m.pe_ratio

        FROM financial_ratios r

        LEFT JOIN market_cap m
            ON m.company_id = r.company_id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id
                    = r.company_id
           )

        WHERE r.year = COALESCE(
            ?,
            (
                SELECT MAX(fr.year)
                FROM financial_ratios fr
                WHERE fr.year <> 'TTM'
            )
        )
        """,
        (
            year,
        ),
    )

    frame = pd.DataFrame(
        rows
    )

    output = []

    for metric in PORTFOLIO_METRICS:

        values = (
            pd.to_numeric(
                frame[
                    metric
                ],
                errors="coerce",
            )
            .dropna()
        )

        if values.empty:
            continue

        output.append(
            {
                "metric":
                    metric,
                "p10":
                    values.quantile(
                        0.10
                    ),
                "p25":
                    values.quantile(
                        0.25
                    ),
                "p50":
                    values.quantile(
                        0.50
                    ),
                "p75":
                    values.quantile(
                        0.75
                    ),
                "p90":
                    values.quantile(
                        0.90
                    ),
                "mean":
                    values.mean(),
                "observations":
                    int(
                        len(values)
                    ),
            }
        )

    output_frame = (
        pd.DataFrame(
            output
        )
        .astype(object)
    )

    output_frame = (
        output_frame.where(
            pd.notna(
                output_frame
            ),
            None,
        )
    )

    return output_frame.to_dict(
        orient="records"
    )