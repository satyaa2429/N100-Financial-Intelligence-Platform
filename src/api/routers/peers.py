"""Peer comparison API routes."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.database import (
    company_exists,
    fetch_all,
    fetch_one,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Peers"],
)


PEER_METRICS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "cfo_pat_ratio",
]


RADAR_METRICS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
]


def safe_records(
    frame: pd.DataFrame,
) -> list[dict]:
    """Convert DataFrame to JSON-safe dictionaries."""

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
    "/peers/{group_name}",
    summary="Peer group",
)
def peer_group(
    group_name: str,
    year: str | None = None,
) -> list[dict]:
    """Return peer-group KPI percentile ranks."""

    members = fetch_all(
        """
        SELECT
            pg.peer_group_name,
            pg.company_id,
            pg.is_benchmark,
            c.company_name,

            r.net_profit_margin_pct,
            r.operating_profit_margin_pct,
            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,
            r.cfo_pat_ratio

        FROM peer_groups pg

        JOIN companies c
            ON c.id = pg.company_id

        LEFT JOIN financial_ratios r
            ON r.company_id = pg.company_id
           AND r.year = COALESCE(
                ?,
                (
                    SELECT MAX(fr.year)
                    FROM financial_ratios fr
                    WHERE fr.company_id
                        = pg.company_id
                      AND fr.year <> 'TTM'
                )
           )

        WHERE LOWER(pg.peer_group_name)
            = LOWER(?)

        ORDER BY pg.company_id
        """,
        (
            year,
            group_name.strip(),
        ),
    )

    if not members:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Peer group "
                f"'{group_name}' "
                "was not found."
            ),
        )

    frame = pd.DataFrame(
        members
    )

    for metric in PEER_METRICS:

        frame[
            f"{metric}_percentile"
        ] = (
            pd.to_numeric(
                frame[metric],
                errors="coerce",
            )
            .rank(
                pct=True
            )
            * 100
        )

    return safe_records(
        frame
    )


@router.get(
    "/companies/{ticker}/peers/compare",
    summary="Company peer comparison",
)
def compare_peers(
    ticker: str,
    year: str | None = None,
) -> dict:
    """Return company, peer average and benchmark radar data."""

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

    group = fetch_one(
        """
        SELECT peer_group_name
        FROM peer_groups
        WHERE UPPER(company_id)
            = UPPER(?)
        ORDER BY peer_group_name
        LIMIT 1
        """,
        (
            ticker,
        ),
    )

    if group is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "No peer group exists "
                f"for {ticker}."
            ),
        )

    group_name = (
        group[
            "peer_group_name"
        ]
    )

    rows = fetch_all(
        """
        SELECT
            pg.company_id,
            pg.is_benchmark,

            r.net_profit_margin_pct,
            r.operating_profit_margin_pct,
            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr

        FROM peer_groups pg

        LEFT JOIN financial_ratios r
            ON r.company_id = pg.company_id
           AND r.year = COALESCE(
                ?,
                (
                    SELECT MAX(fr.year)
                    FROM financial_ratios fr
                    WHERE fr.company_id
                        = pg.company_id
                      AND fr.year <> 'TTM'
                )
           )

        WHERE pg.peer_group_name = ?
        """,
        (
            year,
            group_name,
        ),
    )

    frame = pd.DataFrame(
        rows
    )

    for metric in RADAR_METRICS:

        frame[metric] = (
            pd.to_numeric(
                frame[metric],
                errors="coerce",
            )
        )

    company_rows = frame[
        frame["company_id"]
        .str.upper()
        == ticker
    ]

    if company_rows.empty:

        raise HTTPException(
            status_code=404,
            detail="Company peer data unavailable.",
        )

    company_row = (
        company_rows.iloc[0]
    )

    benchmark_rows = frame[
        frame["is_benchmark"]
        == 1
    ]

    benchmark = (
        benchmark_rows.iloc[0]
        if not benchmark_rows.empty
        else None
    )

    radar_data = []

    for metric in RADAR_METRICS:

        item = {
            "metric": metric,
            "company_value":
                company_row[
                    metric
                ],
            "peer_average":
                frame[
                    metric
                ].mean(),
            "benchmark_value":
                None,
        }

        if benchmark is not None:

            item[
                "benchmark_value"
            ] = benchmark[
                metric
            ]

        radar_data.append(
            item
        )

    radar_frame = (
        pd.DataFrame(
            radar_data
        )
    )

    return {
        "ticker": ticker,
        "peer_group":
            group_name,
        "radar_data":
            safe_records(
                radar_frame
            ),
    }