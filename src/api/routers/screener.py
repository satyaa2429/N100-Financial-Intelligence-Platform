"""Investment screener API route."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.database import fetch_all


router = APIRouter(
    prefix="/api/v1",
    tags=["Screener"],
)


def percentile(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """Return percentile scores from zero to one."""

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    return numeric.rank(
        pct=True,
        ascending=higher_is_better,
    )


@router.get(
    "/screener",
    summary="Financial screener",
)
def screener(
    min_roe: float | None = None,
    max_de: float | None = None,
    min_fcf: float | None = None,
    sector: str | None = None,
    min_rev_cagr_5yr: float | None = None,
    min_pat_cagr_5yr: float | None = None,
    max_pe: float | None = None,
) -> list[dict]:
    """Filter and rank companies."""

    if (
        max_de is not None
        and max_de < 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "max_de cannot be negative."
            ),
        )

    rows = fetch_all(
        """
        SELECT
            c.id AS ticker,
            c.company_name,
            s.broad_sector AS sector,

            r.return_on_equity_pct
                AS roe,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.operating_profit_margin_pct
                AS opm,

            m.pe_ratio

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

        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id = c.id
           )
        """
    )

    frame = pd.DataFrame(
        rows
    )

    if frame.empty:
        return []

    score_columns = [
        "roe",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "free_cash_flow_cr",
        "debt_to_equity",
        "pe_ratio",
    ]

    for column in score_columns:

        frame[column] = (
            pd.to_numeric(
                frame[column],
                errors="coerce",
            )
        )

    frame["roe_score"] = (
        percentile(
            frame["roe"],
            True,
        )
    )

    frame["revenue_score"] = (
        percentile(
            frame[
                "revenue_cagr_5yr"
            ],
            True,
        )
    )

    frame["profit_score"] = (
        percentile(
            frame[
                "pat_cagr_5yr"
            ],
            True,
        )
    )

    frame["fcf_score"] = (
        percentile(
            frame[
                "free_cash_flow_cr"
            ],
            True,
        )
    )

    frame["de_score"] = (
        percentile(
            frame[
                "debt_to_equity"
            ],
            False,
        )
    )

    frame["pe_score"] = (
        percentile(
            frame[
                "pe_ratio"
            ],
            False,
        )
    )

    frame[
        "composite_score"
    ] = (
        frame[
            [
                "roe_score",
                "revenue_score",
                "profit_score",
                "fcf_score",
                "de_score",
                "pe_score",
            ]
        ]
        .mean(
            axis=1,
            skipna=True,
        )
        * 100
    )

    if min_roe is not None:

        frame = frame[
            frame["roe"]
            >= min_roe
        ]

    if max_de is not None:

        frame = frame[
            frame[
                "debt_to_equity"
            ]
            <= max_de
        ]

    if min_fcf is not None:

        frame = frame[
            frame[
                "free_cash_flow_cr"
            ]
            >= min_fcf
        ]

    if sector:

        frame = frame[
            frame["sector"]
            .fillna("")
            .str.lower()
            == sector.strip().lower()
        ]

    if min_rev_cagr_5yr is not None:

        frame = frame[
            frame[
                "revenue_cagr_5yr"
            ]
            >= min_rev_cagr_5yr
        ]

    if min_pat_cagr_5yr is not None:

        frame = frame[
            frame[
                "pat_cagr_5yr"
            ]
            >= min_pat_cagr_5yr
        ]

    if max_pe is not None:

        frame = frame[
            frame[
                "pe_ratio"
            ]
            <= max_pe
        ]

    frame = frame.sort_values(
        "composite_score",
        ascending=False,
    )

    frame[
        "composite_score"
    ] = (
        frame[
            "composite_score"
        ]
        .round(2)
    )

    output_columns = [
        "ticker",
        "company_name",
        "sector",
        "roe",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "opm",
        "pe_ratio",
        "composite_score",
    ]

    output = (
        frame[
            output_columns
        ]
        .astype(object)
        .where(
            pd.notna(
                frame[
                    output_columns
                ]
            ),
            None,
        )
    )

    return output.to_dict(
        orient="records"
    )