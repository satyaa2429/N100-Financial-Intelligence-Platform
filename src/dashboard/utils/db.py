"""Shared cached SQLite data-access functions for the Streamlit dashboard."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
CACHE_TTL = 600


def _read_sql(query: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a read-only SQLite query and return a DataFrame."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            query,
            conn,
            params=params,
        )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_companies() -> pd.DataFrame:
    """Return all companies with sector metadata."""
    return _read_sql(
        """
        SELECT
            c.id AS company_id,
            c.company_name,
            c.about_company,
            c.website,
            c.nse_profile,
            c.bse_profile,
            c.face_value,
            c.book_value,
            c.roce_percentage,
            c.roe_percentage,
            s.broad_sector,
            s.sub_sector,
            s.index_weight_pct,
            s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s
            ON s.company_id = c.id
        ORDER BY c.id
        """
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ratios(
    ticker: str,
    year: str | None = None,
) -> pd.DataFrame:
    """Return computed financial ratios for one company."""
    ticker = ticker.strip().upper()

    if year is None:
        return _read_sql(
            """
            SELECT *
            FROM financial_ratios
            WHERE company_id = ?
            ORDER BY year DESC
            """,
            (ticker,),
        )

    return _read_sql(
        """
        SELECT *
        FROM financial_ratios
        WHERE company_id = ?
          AND year = ?
        ORDER BY year DESC
        """,
        (ticker, year),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_pl(ticker: str) -> pd.DataFrame:
    """Return profit-and-loss history for one company."""
    return _read_sql(
        """
        SELECT *
        FROM profitandloss
        WHERE company_id = ?
        ORDER BY year
        """,
        (ticker.strip().upper(),),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_bs(ticker: str) -> pd.DataFrame:
    """Return balance-sheet history for one company."""
    return _read_sql(
        """
        SELECT *
        FROM balancesheet
        WHERE company_id = ?
        ORDER BY year
        """,
        (ticker.strip().upper(),),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_cf(ticker: str) -> pd.DataFrame:
    """Return cash-flow history for one company."""
    return _read_sql(
        """
        SELECT *
        FROM cashflow
        WHERE company_id = ?
        ORDER BY year
        """,
        (ticker.strip().upper(),),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_sectors() -> pd.DataFrame:
    """Return sector mappings for the full company universe."""
    return _read_sql(
        """
        SELECT
            s.company_id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,
            s.index_weight_pct,
            s.market_cap_category
        FROM sectors s
        LEFT JOIN companies c
            ON c.id = s.company_id
        ORDER BY
            s.broad_sector,
            s.sub_sector,
            s.company_id
        """
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_peers(group_name: str) -> pd.DataFrame:
    """Return all companies in a selected official peer group."""
    return _read_sql(
        """
        SELECT
            pg.peer_group_name,
            pg.company_id,
            c.company_name,
            pg.is_benchmark
        FROM peer_groups pg
        LEFT JOIN companies c
            ON c.id = pg.company_id
        WHERE pg.peer_group_name = ?
        ORDER BY
            pg.is_benchmark DESC,
            pg.company_id
        """,
        (group_name,),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_valuation(ticker: str) -> pd.DataFrame:
    """Return historical valuation multiples for one company."""
    return _read_sql(
        """
        SELECT *
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year
        """,
        (ticker.strip().upper(),),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_home_snapshot(year: int) -> pd.DataFrame:
    """Return company, sector, ratio and valuation data for the Home screen."""
    ratio_year = f"{int(year)}-03"

    return _read_sql(
        """
        SELECT
            c.id AS company_id,
            c.company_name,
            s.broad_sector,
            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.net_profit_margin_pct,
            r.debt_to_equity,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,
            r.total_debt_cr,
            m.pe_ratio,
            m.pb_ratio,
            m.dividend_yield_pct
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
        """,
        (ratio_year, int(year)),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    """Return available pros and cons for one company."""
    return _read_sql(
        """
        SELECT pros, cons
        FROM prosandcons
        WHERE company_id = ?
        ORDER BY id
        """,
        (ticker.strip().upper(),),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_turnaround_companies() -> pd.DataFrame:
    """Return companies matching the official Turnaround Watch conditions."""
    return _read_sql(
        """
        SELECT
            current.company_id,
            current.revenue_cagr_3yr,
            current.free_cash_flow_cr,
            current.debt_to_equity AS current_debt_to_equity,
            previous.debt_to_equity AS previous_debt_to_equity
        FROM financial_ratios current
        JOIN financial_ratios previous
            ON previous.company_id = current.company_id
           AND previous.year = '2023-03'
        WHERE current.year = '2024-03'
          AND current.revenue_cagr_3yr > 10
          AND current.free_cash_flow_cr > 0
          AND previous.free_cash_flow_cr IS NOT NULL
          AND current.free_cash_flow_cr > previous.free_cash_flow_cr
          AND current.debt_to_equity IS NOT NULL
          AND previous.debt_to_equity IS NOT NULL
          AND current.debt_to_equity < previous.debt_to_equity
        ORDER BY current.company_id
        """
    )



@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_sector_snapshot(year: int) -> pd.DataFrame:
    """Return company-level sector analytics for one year."""
    ratio_year = f"{int(year)}-03"

    return _read_sql(
        """
        SELECT
            c.id AS company_id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,
            s.market_cap_category,
            p.sales AS revenue_cr,
            r.return_on_equity_pct AS roe_pct,
            r.return_on_capital_employed_pct AS roce_pct,
            r.net_profit_margin_pct AS npm_pct,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.debt_to_equity,
            m.market_cap_crore,
            m.pe_ratio,
            m.pb_ratio
        FROM companies c
        LEFT JOIN sectors s
            ON s.company_id = c.id
        LEFT JOIN profitandloss p
            ON p.company_id = c.id
           AND p.year = ?
        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = ?
        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = ?
        ORDER BY
            s.broad_sector,
            c.id
        """,
        (
            ratio_year,
            ratio_year,
            int(year),
        ),
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_documents(ticker: str) -> pd.DataFrame:
    """Return annual-report links for one company."""
    return _read_sql(
        """
        SELECT
            company_id,
            Year AS year,
            Annual_Report AS annual_report
        FROM documents
        WHERE company_id = ?
        ORDER BY Year DESC
        """,
        (ticker.strip().upper(),),
    )
