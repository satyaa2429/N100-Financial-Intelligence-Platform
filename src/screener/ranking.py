"""Sector-relative 50/30/20 ranking engine for N100."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path("data/nifty100.db")
OUTPUT_PATH = Path("output/screener_output.xlsx")

RATIO_YEAR = "2024-03"
MARKET_YEAR = 2024


PROFITABILITY_METRICS = {
    "roe": "roe",
    "roce": "roce",
    "npm": "npm",
}

GROWTH_METRICS = {
    "revenue_cagr_5yr": "revenue_cagr_5yr",
    "pat_cagr_5yr": "pat_cagr_5yr",
    "eps_cagr_5yr": "eps_cagr_5yr",
}

VALUATION_METRICS = {
    "pe_ratio": ("pe_ratio", False),
    "pb_ratio": ("pb_ratio", False),
    "dividend_yield": ("dividend_yield", True),
}


def load_ranking_data() -> pd.DataFrame:
    query = """
        SELECT
            c.id AS company_id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,

            r.return_on_equity_pct AS roe,
            r.return_on_capital_employed_pct AS roce,
            r.net_profit_margin_pct AS npm,

            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,

            m.pe_ratio,
            m.pb_ratio,
            m.dividend_yield_pct AS dividend_yield

        FROM companies c

        LEFT JOIN sectors s
            ON s.company_id = c.id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = ?

        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = ?

        ORDER BY c.id
    """

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            query,
            conn,
            params=(RATIO_YEAR, MARKET_YEAR),
        )


def sector_percentile(
    frame: pd.DataFrame,
    column: str,
    higher_is_better: bool = True,
) -> pd.Series:
    values = pd.to_numeric(
        frame[column],
        errors="coerce",
    )

    ranks = values.groupby(
        frame["broad_sector"]
    ).rank(
        pct=True,
        ascending=higher_is_better,
        method="average",
    )

    return (
        ranks
        .mul(100)
        .fillna(50.0)
    )


def build_ranking() -> pd.DataFrame:
    frame = load_ranking_data()

    # Profitability
    for score_name, source_column in (
        PROFITABILITY_METRICS.items()
    ):
        frame[f"{score_name}_score"] = (
            sector_percentile(
                frame,
                source_column,
                higher_is_better=True,
            )
        )

    frame["profitability_score"] = frame[
        [
            "roe_score",
            "roce_score",
            "npm_score",
        ]
    ].mean(axis=1)

    # Growth
    for score_name, source_column in (
        GROWTH_METRICS.items()
    ):
        frame[f"{score_name}_score"] = (
            sector_percentile(
                frame,
                source_column,
                higher_is_better=True,
            )
        )

    frame["growth_score"] = frame[
        [
            "revenue_cagr_5yr_score",
            "pat_cagr_5yr_score",
            "eps_cagr_5yr_score",
        ]
    ].mean(axis=1)

    # Valuation
    for score_name, (
        source_column,
        higher_is_better,
    ) in VALUATION_METRICS.items():

        frame[f"{score_name}_score"] = (
            sector_percentile(
                frame,
                source_column,
                higher_is_better=higher_is_better,
            )
        )

    frame["valuation_score"] = frame[
        [
            "pe_ratio_score",
            "pb_ratio_score",
            "dividend_yield_score",
        ]
    ].mean(axis=1)

    # Official Sprint 3 weighting
    frame["composite_score"] = (
        frame["profitability_score"] * 0.50
        + frame["growth_score"] * 0.30
        + frame["valuation_score"] * 0.20
    )

    frame["sector_rank"] = (
        frame.groupby(
            "broad_sector"
        )["composite_score"]
        .rank(
            method="min",
            ascending=False,
        )
        .astype(int)
    )

    frame["overall_rank"] = (
        frame["composite_score"]
        .rank(
            method="min",
            ascending=False,
        )
        .astype(int)
    )

    return frame.sort_values(
        [
            "composite_score",
            "company_id",
        ],
        ascending=[
            False,
            True,
        ],
    ).reset_index(drop=True)


def export_ranking(
    frame: pd.DataFrame,
) -> None:

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with pd.ExcelWriter(
        OUTPUT_PATH,
        engine="openpyxl",
    ) as writer:

        frame.to_excel(
            writer,
            sheet_name="Composite Ranking",
            index=False,
        )

        for sector, group in frame.groupby(
            "broad_sector"
        ):
            sheet_name = (
                str(sector)[:31]
            )

            group.sort_values(
                "sector_rank"
            ).to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )


def main() -> None:
    ranking = build_ranking()

    export_ranking(ranking)

    print("Companies:", len(ranking))
    print(
        "Sectors:",
        ranking["broad_sector"].nunique(),
    )

    print(
        "Score range:",
        round(
            ranking["composite_score"].min(),
            2,
        ),
        "to",
        round(
            ranking["composite_score"].max(),
            2,
        ),
    )

    print()
    print("Top 10:")
    print(
        ranking[
            [
                "overall_rank",
                "company_id",
                "broad_sector",
                "profitability_score",
                "growth_score",
                "valuation_score",
                "composite_score",
                "sector_rank",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print()
    print(
        "Saved:",
        OUTPUT_PATH.resolve(),
    )


if __name__ == "__main__":
    main()


