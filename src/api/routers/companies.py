"""Company and financial-statement API routes."""

from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from src.api.database import (
    PROJECT_ROOT,
    company_exists,
    fetch_all,
    fetch_one,
    latest_ratio_year,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Companies"],
)


def normalize_ticker(
    ticker: str,
) -> str:
    """Normalize NSE ticker."""

    return ticker.strip().upper()


def ensure_company(
    ticker: str,
) -> str:
    """Validate ticker and return normalized value."""

    ticker = normalize_ticker(
        ticker
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

    return ticker


def year_conditions(
    from_year: str | None,
    to_year: str | None,
) -> tuple[str, list[str]]:
    """Build optional financial-year filters."""

    conditions: list[str] = []

    params: list[str] = []

    if from_year:

        conditions.append(
            "year >= ?"
        )

        params.append(
            from_year
        )

    if to_year:

        conditions.append(
            "year <= ?"
        )

        params.append(
            to_year
        )

    if not conditions:
        return "", params

    return (
        " AND "
        + " AND ".join(
            conditions
        ),
        params,
    )


def generated_pros_cons(
    ticker: str,
) -> list[dict]:
    """Read generated pros/cons when available."""

    path = (
        PROJECT_ROOT
        / "output"
        / "pros_cons_generated.csv"
    )

    if not path.exists():
        return []

    results = []

    try:

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:

            reader = csv.DictReader(
                handle
            )

            for row in reader:

                company_id = str(
                    row.get(
                        "company_id",
                        "",
                    )
                ).strip().upper()

                if company_id == ticker:
                    results.append(
                        dict(row)
                    )

    except (
        OSError,
        csv.Error,
    ):
        return []

    return results


@router.get(
    "/companies",
    summary="List companies",
)
def list_companies(
    sector: str | None = None,
    market_cap_category: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """List all companies with optional filters."""

    query = """
        SELECT
            c.id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,
            s.market_cap_category,
            r.return_on_equity_pct
                AS roe_pct,
            r.return_on_capital_employed_pct
                AS roce_pct

        FROM companies c

        LEFT JOIN sectors s
            ON s.company_id = c.id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = (
                SELECT MAX(fr.year)
                FROM financial_ratios fr
                WHERE fr.company_id = c.id
                  AND fr.year <> 'TTM'
           )

        WHERE 1 = 1
    """

    params: list = []

    if sector:

        query += """
            AND LOWER(s.broad_sector)
                = LOWER(?)
        """

        params.append(
            sector.strip()
        )

    if market_cap_category:

        query += """
            AND LOWER(
                s.market_cap_category
            ) = LOWER(?)
        """

        params.append(
            market_cap_category.strip()
        )

    if search:

        query += """
            AND (
                LOWER(c.id)
                    LIKE LOWER(?)
                OR LOWER(c.company_name)
                    LIKE LOWER(?)
            )
        """

        pattern = (
            f"%{search.strip()}%"
        )

        params.extend(
            [
                pattern,
                pattern,
            ]
        )

    query += """
        ORDER BY c.company_name
    """

    return fetch_all(
        query,
        tuple(params),
    )


@router.get(
    "/companies/{ticker}",
    summary="Company profile",
)
def company_profile(
    ticker: str,
    year: str | None = None,
) -> dict:
    """Return company profile and KPI data."""

    ticker = ensure_company(
        ticker
    )

    selected_year = (
        year
        or latest_ratio_year(
            ticker
        )
    )

    profile = fetch_one(
        """
        SELECT
            c.*,
            s.broad_sector,
            s.sub_sector,
            s.index_weight_pct,
            s.market_cap_category,

            r.year AS ratio_year,

            r.net_profit_margin_pct,
            r.operating_profit_margin_pct,
            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.debt_to_equity,
            r.interest_coverage,
            r.asset_turnover,
            r.free_cash_flow_cr,
            r.cash_from_operations_cr,
            r.earnings_per_share,
            r.book_value_per_share,
            r.dividend_payout_ratio_pct,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,
            r.cfo_pat_ratio,
            r.capex_intensity_pct,
            r.fcf_conversion_pct

        FROM companies c

        LEFT JOIN sectors s
            ON s.company_id = c.id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = ?

        WHERE UPPER(c.id)
            = UPPER(?)
        """,
        (
            selected_year,
            ticker,
        ),
    )

    if profile is None:

        raise HTTPException(
            status_code=404,
            detail="Company profile not found.",
        )

    generated = (
        generated_pros_cons(
            ticker
        )
    )

    if generated:

        profile[
            "pros_cons"
        ] = generated

    else:

        profile[
            "pros_cons"
        ] = fetch_all(
            """
            SELECT
                pros,
                cons
            FROM prosandcons
            WHERE UPPER(company_id)
                = UPPER(?)
            """,
            (
                ticker,
            ),
        )

    return profile


@router.get(
    "/companies/{ticker}/pl",
    summary="Profit and loss history",
)
def profit_and_loss(
    ticker: str,
    from_year: str | None = None,
    to_year: str | None = None,
) -> list[dict]:
    """Return P&L history."""

    ticker = ensure_company(
        ticker
    )

    condition, extra = (
        year_conditions(
            from_year,
            to_year,
        )
    )

    query = """
        SELECT *
        FROM profitandloss
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    query += condition

    query += """
        ORDER BY year
    """

    params = [
        ticker,
        *extra,
    ]

    return fetch_all(
        query,
        tuple(params),
    )


@router.get(
    "/companies/{ticker}/bs",
    summary="Balance sheet history",
)
def balance_sheet(
    ticker: str,
    from_year: str | None = None,
    to_year: str | None = None,
) -> list[dict]:
    """Return balance-sheet history."""

    ticker = ensure_company(
        ticker
    )

    condition, extra = (
        year_conditions(
            from_year,
            to_year,
        )
    )

    query = """
        SELECT *
        FROM balancesheet
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    query += condition

    query += """
        ORDER BY year
    """

    return fetch_all(
        query,
        tuple(
            [
                ticker,
                *extra,
            ]
        ),
    )


@router.get(
    "/companies/{ticker}/cashflow",
    summary="Cash-flow history",
)
def cashflow(
    ticker: str,
    from_year: str | None = None,
    to_year: str | None = None,
) -> list[dict]:
    """Return cash-flow history."""

    ticker = ensure_company(
        ticker
    )

    condition, extra = (
        year_conditions(
            from_year,
            to_year,
        )
    )

    query = """
        SELECT *
        FROM cashflow
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    query += condition

    query += """
        ORDER BY year
    """

    return fetch_all(
        query,
        tuple(
            [
                ticker,
                *extra,
            ]
        ),
    )


@router.get(
    "/companies/{ticker}/ratios",
    summary="Financial ratios",
)
def ratios(
    ticker: str,
    year: str | None = None,
) -> list[dict]:
    """Return computed KPI history."""

    ticker = ensure_company(
        ticker
    )

    query = """
        SELECT *
        FROM financial_ratios
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    params: list = [
        ticker
    ]

    if year:

        query += """
            AND year = ?
        """

        params.append(
            year
        )

    query += """
        ORDER BY year
    """

    return fetch_all(
        query,
        tuple(params),
    )


@router.get(
    "/companies/{ticker}/documents",
    summary="Annual reports",
)
def documents(
    ticker: str,
    from_year: int | None = Query(
        default=None
    ),
    to_year: int | None = Query(
        default=None
    ),
) -> list[dict]:
    """Return annual-report links."""

    ticker = ensure_company(
        ticker
    )

    query = """
        SELECT
            Year AS year,
            Annual_Report
        FROM documents
        WHERE UPPER(company_id)
            = UPPER(?)
    """

    params: list = [
        ticker
    ]

    if from_year is not None:

        query += """
            AND Year >= ?
        """

        params.append(
            from_year
        )

    if to_year is not None:

        query += """
            AND Year <= ?
        """

        params.append(
            to_year
        )

    query += """
        ORDER BY Year
    """

    rows = fetch_all(
        query,
        tuple(params),
    )

    for row in rows:

        url = row.get(
            "Annual_Report"
        )

        row[
            "is_url_valid"
        ] = bool(
            isinstance(
                url,
                str,
            )
            and url.lower().startswith(
                (
                    "http://",
                    "https://",
                )
            )
        )

    return rows