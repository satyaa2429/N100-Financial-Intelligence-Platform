"""Sector-relative ROCE analysis for Banks and NBFCs."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "sector_roce_notes.csv"

ROCE_ANOMALY_TOLERANCE = 5.0


def safe_float(value: object) -> float | None:
    """Convert a value to float or return None."""

    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(number):
        return None

    return number


def is_financial_company(
    broad_sector: object,
    sub_sector: object,
) -> bool:
    """Return True for Bank/NBFC/financial-sector companies."""

    broad = str(
        broad_sector or ""
    ).strip().lower()

    sub = str(
        sub_sector or ""
    ).strip().lower()

    combined = f"{broad} {sub}"

    keywords = [
        "bank",
        "banking",
        "nbfc",
        "finance",
        "financial",
        "consumer finance",
        "housing finance",
    ]

    return any(
        keyword in combined
        for keyword in keywords
    )


def financial_type(
    broad_sector: object,
    sub_sector: object,
) -> str:
    """Classify a financial company as Bank or NBFC/Financial."""

    text = (
        f"{broad_sector or ''} "
        f"{sub_sector or ''}"
    ).lower()

    if "bank" in text:
        return "Bank"

    if (
        "nbfc" in text
        or "finance" in text
        or "financial" in text
    ):
        return "NBFC / Financial"

    return "Other"


def classify_sector_position(
    percentile: object,
) -> str:
    """Convert sector percentile into a relative ROCE label."""

    value = safe_float(
        percentile
    )

    if value is None:
        return "Insufficient Data"

    if value >= 75:
        return "Sector Leader"

    if value >= 50:
        return "Above Sector Median"

    if value >= 25:
        return "Below Sector Median"

    return "Sector Laggard"


def load_latest_roce() -> pd.DataFrame:
    """Load latest annual ROCE and sector data from SQLite."""

    query = """
    SELECT
        r.company_id,
        r.year,
        r.return_on_capital_employed_pct,
        c.company_name,
        c.roce_percentage AS source_roce_percentage,
        s.broad_sector,
        s.sub_sector
    FROM financial_ratios AS r
    INNER JOIN companies AS c
        ON r.company_id = c.id
    LEFT JOIN sectors AS s
        ON r.company_id = s.company_id
    """

    with sqlite3.connect(
        DB_PATH
    ) as conn:
        dataframe = pd.read_sql_query(
            query,
            conn,
        )

    dataframe = dataframe[
        dataframe["year"].astype(str).str.upper() != "TTM"
    ].copy()

    dataframe["_year_number"] = pd.to_numeric(
        dataframe["year"]
        .astype(str)
        .str[:4],
        errors="coerce",
    )

    dataframe = dataframe[
        dataframe["_year_number"].notna()
    ].copy()

    dataframe = dataframe.sort_values(
        [
            "company_id",
            "_year_number",
        ]
    )

    latest = (
        dataframe
        .groupby(
            "company_id",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    latest = latest.drop(
        columns=[
            "_year_number",
        ]
    )

    return latest


def build_sector_roce_analysis() -> pd.DataFrame:
    """Build Bank/NBFC sector-relative ROCE analysis."""

    dataframe = load_latest_roce()

    dataframe["is_financial"] = dataframe.apply(
        lambda row: is_financial_company(
            row["broad_sector"],
            row["sub_sector"],
        ),
        axis=1,
    )

    financials = dataframe[
        dataframe["is_financial"]
    ].copy()

    if financials.empty:
        raise RuntimeError(
            "No Bank/NBFC companies were detected "
            "from sectors table."
        )

    financials[
        "financial_type"
    ] = financials.apply(
        lambda row: financial_type(
            row["broad_sector"],
            row["sub_sector"],
        ),
        axis=1,
    )

    financials[
        "return_on_capital_employed_pct"
    ] = pd.to_numeric(
        financials[
            "return_on_capital_employed_pct"
        ],
        errors="coerce",
    )

    financials[
        "source_roce_percentage"
    ] = pd.to_numeric(
        financials[
            "source_roce_percentage"
        ],
        errors="coerce",
    )

    # --------------------------------------------------------
    # SECTOR-RELATIVE MEDIAN
    # --------------------------------------------------------

    financials[
        "sector_roce_median_pct"
    ] = (
        financials
        .groupby(
            "financial_type"
        )[
            "return_on_capital_employed_pct"
        ]
        .transform(
            "median"
        )
    )

    # --------------------------------------------------------
    # SECTOR-RELATIVE PERCENTILE
    # --------------------------------------------------------

    financials[
        "sector_roce_percentile"
    ] = (
        financials
        .groupby(
            "financial_type"
        )[
            "return_on_capital_employed_pct"
        ]
        .rank(
            method="average",
            pct=True,
        )
        * 100
    )

    financials[
        "sector_relative_position"
    ] = (
        financials[
            "sector_roce_percentile"
        ]
        .apply(
            classify_sector_position
        )
    )

    # --------------------------------------------------------
    # DIFFERENCE FROM SECTOR MEDIAN
    # --------------------------------------------------------

    financials[
        "difference_from_sector_median_pct"
    ] = (
        financials[
            "return_on_capital_employed_pct"
        ]
        - financials[
            "sector_roce_median_pct"
        ]
    )

    # --------------------------------------------------------
    # CROSS-CHECK VS companies.roce_percentage
    # --------------------------------------------------------

    financials[
        "source_difference_pct_points"
    ] = (
        financials[
            "return_on_capital_employed_pct"
        ]
        - financials[
            "source_roce_percentage"
        ]
    ).abs()

    financials[
        "source_crosscheck_anomaly"
    ] = (
        financials[
            "source_difference_pct_points"
        ]
        > ROCE_ANOMALY_TOLERANCE
    )

    financials[
        "anomaly_note"
    ] = financials.apply(
        lambda row:
        (
            "Computed ROCE differs from "
            "companies.roce_percentage by more than "
            f"{ROCE_ANOMALY_TOLERANCE:.1f} percentage points."
        )
        if row[
            "source_crosscheck_anomaly"
        ]
        else "Within cross-check tolerance.",
        axis=1,
    )

    result_columns = [
        "company_id",
        "company_name",
        "year",
        "broad_sector",
        "sub_sector",
        "financial_type",

        "return_on_capital_employed_pct",
        "sector_roce_median_pct",
        "sector_roce_percentile",
        "sector_relative_position",
        "difference_from_sector_median_pct",

        "source_roce_percentage",
        "source_difference_pct_points",
        "source_crosscheck_anomaly",
        "anomaly_note",
    ]

    result = financials[
        result_columns
    ].copy()

    result = result.sort_values(
        [
            "financial_type",
            "sector_roce_percentile",
        ],
        ascending=[
            True,
            False,
        ],
    )

    return result


def save_sector_roce_notes(
    dataframe: pd.DataFrame,
) -> None:
    """Save Day 13 sector ROCE analysis CSV."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        OUTPUT_FILE,
        index=False,
    )


def main() -> None:
    """Run Day 13 Bank/NBFC ROCE analysis."""

    result = build_sector_roce_analysis()

    save_sector_roce_notes(
        result
    )

    print(
        result.to_string(
            index=False
        )
    )

    print(
        "\nFinancial companies analysed:",
        len(result),
    )

    print(
        "Banks:",
        int(
            (
                result["financial_type"]
                == "Bank"
            ).sum()
        ),
    )

    print(
        "NBFC / Financial:",
        int(
            (
                result["financial_type"]
                == "NBFC / Financial"
            ).sum()
        ),
    )

    print(
        "ROCE cross-check anomalies:",
        int(
            result[
                "source_crosscheck_anomaly"
            ].sum()
        ),
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print(
        "\nDAY 13 COMPLETE"
    )


if __name__ == "__main__":
    main()
