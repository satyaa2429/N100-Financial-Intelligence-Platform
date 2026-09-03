"""Full SQLite loader for the N100 Financial Intelligence Platform."""

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.etl.loader import load_all_core_datasets
from src.etl.normaliser import normalize_ticker, normalize_year


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
SUPPORTING_DIR = PROJECT_ROOT / "data" / "supporting"
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIT_FILE = OUTPUT_DIR / "load_audit.csv"

SUPPORTING_FILES = {
    "sectors": "sectors.xlsx",
    "stock_prices": "stock_prices.xlsx",
    "market_cap": "market_cap.xlsx",
    "financial_ratios": "financial_ratios.xlsx",
    "peer_groups": "peer_groups.xlsx",
}

CORE_SOURCE_COUNTS = {
    "companies": 92,
    "profitandloss": 1276,
    "balancesheet": 1312,
    "cashflow": 1187,
    "analysis": 20,
    "documents": 1585,
    "prosandcons": 16,
}


def load_supporting_excel(
    table_name: str,
) -> pd.DataFrame:
    """Load and normalise one supplementary Excel dataset."""

    path = SUPPORTING_DIR / SUPPORTING_FILES[table_name]

    if not path.exists():
        raise FileNotFoundError(
            f"Supplementary dataset not found: {path}"
        )

    df = pd.read_excel(
        path,
        header=0,
        engine="openpyxl",
    )

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    df = df.dropna(how="all").copy()

    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(
            normalize_ticker
        )

    if table_name == "financial_ratios":
        df["year"] = df["year"].apply(
            normalize_year
        )

    if table_name == "market_cap":
        df["year"] = pd.to_numeric(
            df["year"],
            errors="raise",
        ).astype(int)

    if table_name == "stock_prices":
        df["date"] = pd.to_datetime(
            df["date"],
            errors="raise",
        ).dt.strftime("%Y-%m-%d")

    if table_name == "peer_groups":
        if "is_benchmark" in df.columns:
            df["is_benchmark"] = (
                df["is_benchmark"]
                .apply(normalize_boolean)
            )

    return df


def normalize_boolean(value: object) -> int | None:
    """Convert boolean-like values to SQLite integers."""

    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return int(value)

    text = str(value).strip().lower()

    if text in {"true", "yes", "y", "1"}:
        return 1

    if text in {"false", "no", "n", "0"}:
        return 0

    try:
        return int(float(text))
    except ValueError:
        return None


def clean_supporting_dataset(
    df: pd.DataFrame,
    table_name: str,
    valid_company_ids: set[str],
) -> pd.DataFrame:
    """Apply FK filtering and logical-key deduplication."""

    cleaned = df.copy()

    if "company_id" in cleaned.columns:
        orphan_mask = ~cleaned["company_id"].isin(
            valid_company_ids
        )

        rejected_orphans = int(
            orphan_mask.sum()
        )

        if rejected_orphans:
            logger.warning(
                "DQ-03 | %-18s rejected %d orphan rows",
                table_name,
                rejected_orphans,
            )

            cleaned = cleaned.loc[
                ~orphan_mask
            ].copy()

    duplicate_keys = {
        "sectors": ["company_id"],
        "stock_prices": [
            "company_id",
            "date",
        ],
        "market_cap": [
            "company_id",
            "year",
        ],
        "financial_ratios": [
            "company_id",
            "year",
        ],
        "peer_groups": [
            "peer_group_name",
            "company_id",
        ],
    }

    keys = duplicate_keys.get(
        table_name
    )

    if keys:
        before = len(cleaned)

        cleaned = cleaned.drop_duplicates(
            subset=keys,
            keep="last",
        ).copy()

        removed = before - len(cleaned)

        if removed:
            logger.warning(
                "DQ-02 | %-18s removed %d duplicate rows",
                table_name,
                removed,
            )

    return cleaned


def load_supporting_datasets(
    valid_company_ids: set[str],
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, int],
]:
    """Load and clean all five supplementary datasets."""

    datasets: dict[str, pd.DataFrame] = {}
    rows_in: dict[str, int] = {}

    for table_name in SUPPORTING_FILES:
        df = load_supporting_excel(
            table_name
        )

        rows_in[table_name] = len(df)

        df = clean_supporting_dataset(
            df,
            table_name,
            valid_company_ids,
        )

        datasets[table_name] = df

        logger.info(
            "Prepared %-18s rows_in=%d rows_out=%d",
            table_name,
            rows_in[table_name],
            len(df),
        )

    return datasets, rows_in


def create_schema(
    connection: sqlite3.Connection,
) -> None:
    """Create the SQLite tables from schema.sql."""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_PATH}"
        )

    schema = SCHEMA_PATH.read_text(
        encoding="utf-8"
    )

    connection.executescript(schema)

    connection.execute(
        "PRAGMA foreign_keys = ON;"
    )


def clear_database(
    connection: sqlite3.Connection,
) -> None:
    """Delete existing rows in FK-safe order."""

    child_tables = [
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
        "sectors",
        "stock_prices",
        "market_cap",
        "financial_ratios",
        "peer_groups",
    ]

    for table_name in child_tables:
        connection.execute(
            f'DELETE FROM "{table_name}"'
        )

    connection.execute(
        'DELETE FROM "companies"'
    )


def insert_dataframe(
    connection: sqlite3.Connection,
    table_name: str,
    df: pd.DataFrame,
) -> float:
    """Insert one DataFrame and return runtime in seconds."""

    start = time.perf_counter()

    df.to_sql(
        table_name,
        connection,
        if_exists="append",
        index=False,
    )

    runtime = (
        time.perf_counter() - start
    )

    logger.info(
        "Inserted %-18s rows=%d runtime=%.3fs",
        table_name,
        len(df),
        runtime,
    )

    return runtime


def verify_row_counts(
    connection: sqlite3.Connection,
    datasets: dict[str, pd.DataFrame],
) -> None:
    """Verify database row counts."""

    for table_name, df in datasets.items():
        db_count = connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]

        if db_count != len(df):
            raise RuntimeError(
                f"Row count mismatch for {table_name}: "
                f"database={db_count}, "
                f"expected={len(df)}"
            )

        logger.info(
            "Verified %-18s rows=%d",
            table_name,
            db_count,
        )


def verify_foreign_keys(
    connection: sqlite3.Connection,
) -> None:
    """Ensure there are no FK violations."""

    violations = connection.execute(
        "PRAGMA foreign_key_check;"
    ).fetchall()

    if violations:
        raise RuntimeError(
            "Foreign key violations found: "
            f"{violations[:10]}"
        )

    logger.info(
        "Foreign key check passed: 0 violations."
    )


def create_audit_record(
    table_name: str,
    rows_in: int,
    rows_out: int,
    runtime_s: float,
) -> dict[str, object]:
    """Create one load-audit record."""

    return {
        "table": table_name,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rejected": rows_in - rows_out,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "runtime_s": round(
            runtime_s,
            4,
        ),
    }


def main() -> None:
    """Run the complete 12-dataset SQLite load."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info(
        "Loading cleaned core datasets..."
    )

    core_datasets = load_all_core_datasets(
        clean=True
    )

    valid_company_ids = set(
        core_datasets["companies"]["id"]
        .dropna()
        .astype(str)
    )

    logger.info(
        "Loading supplementary datasets..."
    )

    (
        supporting_datasets,
        supporting_rows_in,
    ) = load_supporting_datasets(
        valid_company_ids
    )

    all_datasets = {
        **core_datasets,
        **supporting_datasets,
    }

    rows_in = {
        **CORE_SOURCE_COUNTS,
        **supporting_rows_in,
    }

    audit_records: list[
        dict[str, object]
    ] = []

    logger.info(
        "Opening SQLite database: %s",
        DB_PATH,
    )

    with sqlite3.connect(
        DB_PATH
    ) as connection:

        create_schema(
            connection
        )

        clear_database(
            connection
        )

        load_order = [
            "companies",
            "profitandloss",
            "balancesheet",
            "cashflow",
            "analysis",
            "documents",
            "prosandcons",
            "sectors",
            "stock_prices",
            "market_cap",
            "financial_ratios",
            "peer_groups",
        ]

        for table_name in load_order:
            dataframe = all_datasets[
                table_name
            ]

            runtime = insert_dataframe(
                connection,
                table_name,
                dataframe,
            )

            audit_records.append(
                create_audit_record(
                    table_name,
                    rows_in[table_name],
                    len(dataframe),
                    runtime,
                )
            )

        verify_foreign_keys(
            connection
        )

        verify_row_counts(
            connection,
            all_datasets,
        )

        connection.commit()

    audit_df = pd.DataFrame(
        audit_records
    )

    audit_df.to_csv(
        AUDIT_FILE,
        index=False,
    )

    logger.info(
        "Load audit saved: %s",
        AUDIT_FILE,
    )

    logger.info(
        "Full 12-dataset database load completed successfully."
    )


if __name__ == "__main__":
    main()