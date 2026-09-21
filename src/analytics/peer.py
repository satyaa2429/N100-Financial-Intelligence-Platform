"""Peer-group percentile engine for Sprint 3 Day 18."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path("data/nifty100.db")
RATIO_YEAR = "2024-03"
MARKET_YEAR = 2024

METRICS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "cash_from_operations_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "cfo_pat_ratio",
    "capex_intensity_pct",
    "fcf_conversion_pct",
    "pe_ratio",
    "pb_ratio",
]


def load_peer_data() -> pd.DataFrame:
    """Load peer-group and supporting company data."""
    query = """
        SELECT
            pg.peer_group_name,
            pg.company_id,
            pg.is_benchmark,

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
            r.fcf_conversion_pct,

            m.pe_ratio,
            m.pb_ratio

        FROM peer_groups pg

        LEFT JOIN financial_ratios r
            ON r.company_id = pg.company_id
           AND r.year = ?

        LEFT JOIN market_cap m
            ON m.company_id = pg.company_id
           AND m.year = ?

        ORDER BY
            pg.peer_group_name,
            pg.company_id
    """

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            query,
            conn,
            params=(RATIO_YEAR, MARKET_YEAR),
        )


def percent_rank(values: pd.Series) -> pd.Series:
    """Replicate SQL PERCENT_RANK using RANK semantics."""

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    )

    valid = numeric.dropna()
    result = pd.Series(
        index=values.index,
        dtype=float,
    )

    n = len(valid)

    if n == 0:
        return result

    if n == 1:
        result.loc[valid.index] = 0.0
        return result

    ranks = valid.rank(
        method="min",
        ascending=True,
    )

    result.loc[valid.index] = (
        ranks - 1
    ) / (n - 1)

    return result


def build_peer_percentiles() -> pd.DataFrame:
    """Compute peer-group percentile metrics for all companies."""
    source = load_peer_data()

    rows = []

    for metric in METRICS:
        metric_frame = source[
            [
                "peer_group_name",
                "company_id",
                metric,
            ]
        ].copy()

        metric_frame["percentile_rank"] = (
            metric_frame.groupby(
                "peer_group_name",
                group_keys=False,
            )[metric]
            .apply(percent_rank)
        )

        metric_frame = metric_frame.dropna(
            subset=[metric]
        )

        for row in metric_frame.itertuples(
            index=False
        ):
            rows.append(
                {
                    "company_id": row.company_id,
                    "peer_group": row.peer_group_name,
                    "metric": metric,
                    "value": float(
                        getattr(row, metric)
                    ),
                    "percentile_rank": float(
                        row.percentile_rank
                    ),
                    "year": RATIO_YEAR,
                }
            )

    return pd.DataFrame(rows)


def save_peer_percentiles(
    frame: pd.DataFrame,
) -> None:

    """Save computed peer-percentile data to the project output."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_percentiles (
                company_id TEXT NOT NULL,
                peer_group TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                percentile_rank REAL NOT NULL,
                year TEXT NOT NULL,

                PRIMARY KEY (
                    company_id,
                    peer_group,
                    metric,
                    year
                ),

                FOREIGN KEY (company_id)
                    REFERENCES companies(id)
            )
            """
        )

        conn.execute(
            "DELETE FROM peer_percentiles WHERE year = ?",
            (RATIO_YEAR,),
        )

        frame.to_sql(
            "peer_percentiles",
            conn,
            if_exists="append",
            index=False,
        )

        conn.commit()


def main() -> None:
    """Run the peer-analysis workflow."""
    frame = build_peer_percentiles()
    save_peer_percentiles(frame)

    print("Rows:", len(frame))
    print(
        "Peer groups:",
        frame["peer_group"].nunique(),
    )
    print(
        "Companies:",
        frame["company_id"].nunique(),
    )
    print(
        "Metrics:",
        frame["metric"].nunique(),
    )
    print(
        "Percentile range:",
        round(frame["percentile_rank"].min(), 4),
        "to",
        round(frame["percentile_rank"].max(), 4),
    )

    duplicates = frame.duplicated(
        [
            "company_id",
            "peer_group",
            "metric",
            "year",
        ]
    ).sum()

    print("Duplicate keys:", duplicates)

    with sqlite3.connect(DB_PATH) as conn:
        db_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM peer_percentiles
            WHERE year = ?
            """,
            (RATIO_YEAR,),
        ).fetchone()[0]

        fk = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    print("Database rows:", db_rows)
    print("FK violations:", len(fk))


if __name__ == "__main__":
    main()
