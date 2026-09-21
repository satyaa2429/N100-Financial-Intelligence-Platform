"""SQLite database helpers for the FastAPI service."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with dictionary-style rows."""

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def fetch_all(
    query: str,
    params: tuple[Any, ...] = (),
) -> list[dict]:
    """Execute a query and return all rows."""

    with get_connection() as connection:

        rows = connection.execute(
            query,
            params,
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def fetch_one(
    query: str,
    params: tuple[Any, ...] = (),
) -> dict | None:
    """Execute a query and return one row."""

    with get_connection() as connection:

        row = connection.execute(
            query,
            params,
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def company_exists(
    ticker: str,
) -> bool:
    """Check whether a company exists."""

    row = fetch_one(
        """
        SELECT id
        FROM companies
        WHERE UPPER(id) = UPPER(?)
        """,
        (
            ticker.strip(),
        ),
    )

    return row is not None


def latest_ratio_year(
    ticker: str | None = None,
) -> str | None:
    """Return the latest financial-ratio year."""

    if ticker:

        row = fetch_one(
            """
            SELECT MAX(year) AS year
            FROM financial_ratios
            WHERE UPPER(company_id) = UPPER(?)
              AND year <> 'TTM'
            """,
            (
                ticker.strip(),
            ),
        )

    else:

        row = fetch_one(
            """
            SELECT MAX(year) AS year
            FROM financial_ratios
            WHERE year <> 'TTM'
            """
        )

    if not row:
        return None

    return row.get("year")


def table_names() -> list[str]:
    """Return all user-created database tables."""

    rows = fetch_all(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )

    return [
        row["name"]
        for row in rows
    ]


def table_row_counts() -> dict[str, int]:
    """Return row counts for all database tables."""

    counts: dict[str, int] = {}

    with get_connection() as connection:

        for table in table_names():

            row = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()

            counts[table] = int(
                row[0]
            )

    return counts