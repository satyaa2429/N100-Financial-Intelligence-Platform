"""CAGR calculations with portal-compatible status flags."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


CAGR_NORMAL = "NORMAL"
CAGR_DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
CAGR_TURNAROUND = "TURNAROUND"
CAGR_BOTH_NEGATIVE = "BOTH_NEGATIVE"
CAGR_ZERO_BASE = "ZERO_BASE"
CAGR_INSUFFICIENT = "INSUFFICIENT"


def _valid_number(value: Any) -> bool:
    """Check whether value is a valid finite number."""

    if value is None:
        return False

    try:
        number = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(number)


def calculate_cagr_with_flag(
    start_value: Any,
    end_value: Any,
    years: Any,
) -> tuple[float | None, str]:
    """Calculate CAGR with the required status flag."""

    if not _valid_number(start_value):
        return None, CAGR_INSUFFICIENT

    if not _valid_number(end_value):
        return None, CAGR_INSUFFICIENT

    if not _valid_number(years):
        return None, CAGR_INSUFFICIENT

    start = float(start_value)
    end = float(end_value)
    period = float(years)

    if period <= 0:
        return None, CAGR_INSUFFICIENT

    if start == 0:
        return None, CAGR_ZERO_BASE

    if start > 0 and end < 0:
        return None, CAGR_DECLINE_TO_LOSS

    if start < 0 and end > 0:
        return None, CAGR_TURNAROUND

    if start < 0 and end < 0:
        return None, CAGR_BOTH_NEGATIVE

    if start < 0 and end == 0:
        return None, CAGR_TURNAROUND

    ratio = end / start

    if ratio < 0:
        return None, CAGR_INSUFFICIENT

    try:
        cagr = (
            (ratio ** (1.0 / period))
            - 1.0
        ) * 100
    except (ValueError, ZeroDivisionError):
        return None, CAGR_INSUFFICIENT

    if not math.isfinite(cagr):
        return None, CAGR_INSUFFICIENT

    return cagr, CAGR_NORMAL


def calculate_cagr(
    start_value: Any,
    end_value: Any,
    years: Any,
) -> tuple[float | None, bool]:
    """Backward-compatible CAGR function."""

    value, flag = calculate_cagr_with_flag(
        start_value,
        end_value,
        years,
    )

    turnaround = (
        flag == CAGR_TURNAROUND
    )

    return value, turnaround


def _extract_year(value: Any) -> int | None:
    """Extract year from normalized period."""

    if value is None:
        return None

    text = str(value).strip()

    if text.upper() == "TTM":
        return None

    if len(text) < 4:
        return None

    try:
        return int(text[:4])
    except ValueError:
        return None


def calculate_metric_cagr(
    company_data: pd.DataFrame,
    metric: str,
    years: int,
) -> tuple[float | None, str]:
    """Calculate metric CAGR for one company."""

    if metric not in company_data.columns:
        return None, CAGR_INSUFFICIENT

    if "year" not in company_data.columns:
        return None, CAGR_INSUFFICIENT

    df = company_data[
        [
            "year",
            metric,
        ]
    ].copy()

    df["_year_number"] = (
        df["year"].apply(
            _extract_year
        )
    )

    df[metric] = pd.to_numeric(
        df[metric],
        errors="coerce",
    )

    df = df[
        df["_year_number"].notna()
        & df[metric].notna()
    ].copy()

    if df.empty:
        return None, CAGR_INSUFFICIENT

    df["_year_number"] = (
        df["_year_number"].astype(int)
    )

    df = (
        df.sort_values(
            [
                "_year_number",
                "year",
            ]
        )
        .drop_duplicates(
            subset=["_year_number"],
            keep="last",
        )
    )

    latest_year = int(
        df["_year_number"].max()
    )

    required_start_year = (
        latest_year - years
    )

    latest = df[
        df["_year_number"]
        == latest_year
    ]

    start = df[
        df["_year_number"]
        == required_start_year
    ]

    if latest.empty or start.empty:
        return None, CAGR_INSUFFICIENT

    start_value = start.iloc[-1][
        metric
    ]

    end_value = latest.iloc[-1][
        metric
    ]

    return calculate_cagr_with_flag(
        start_value,
        end_value,
        years,
    )


def compute_cagr_metrics(
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Compute 3, 5 and 10 year CAGR metrics."""

    required_columns = {
        "company_id",
        "year",
    }

    if not required_columns.issubset(
        profit_loss.columns
    ):
        raise ValueError(
            "profit_loss requires company_id and year columns."
        )

    metrics = {
        "revenue": "sales",
        "pat": "net_profit",
        "eps": "eps",
    }

    periods = [
        3,
        5,
        10,
    ]

    rows: list[dict[str, Any]] = []

    for company_id, group in (
        profit_loss.groupby(
            "company_id"
        )
    ):

        row: dict[str, Any] = {
            "company_id": company_id,
        }

        for output_name, source_column in (
            metrics.items()
        ):

            for period in periods:

                value_column = (
                    f"{output_name}_cagr_"
                    f"{period}yr"
                )

                flag_column = (
                    f"{value_column}_flag"
                )

                value, flag = (
                    calculate_metric_cagr(
                        group,
                        source_column,
                        period,
                    )
                )

                row[value_column] = value
                row[flag_column] = flag

        rows.append(row)

    return pd.DataFrame(rows)


def create_cagr_wide_table(
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Create company-year CAGR data for financial_ratios population."""

    required_columns = {
        "company_id",
        "year",
        "sales",
        "net_profit",
        "eps",
    }

    if not required_columns.issubset(profit_loss.columns):
        missing = sorted(
            required_columns - set(profit_loss.columns)
        )
        raise ValueError(
            f"Missing CAGR source columns: {missing}"
        )

    df = profit_loss.copy()

    df["company_id"] = (
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["year"] = (
        df["year"]
        .astype(str)
        .str.strip()
    )

    for column in ["sales", "net_profit", "eps"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["_year_number"] = df["year"].apply(
        _extract_year
    )

    annual = df[
        df["_year_number"].notna()
    ].copy()

    annual["_year_number"] = (
        annual["_year_number"].astype(int)
    )

    annual = (
        annual
        .sort_values(
            [
                "company_id",
                "_year_number",
                "year",
            ]
        )
        .drop_duplicates(
            subset=[
                "company_id",
                "_year_number",
            ],
            keep="last",
        )
    )

    metrics = {
        "revenue": "sales",
        "pat": "net_profit",
        "eps": "eps",
    }

    lookups = {}

    for metric_name, source_column in metrics.items():
        lookups[metric_name] = {
            (
                row["company_id"],
                int(row["_year_number"]),
            ): row[source_column]
            for _, row in annual.iterrows()
        }

    base_rows = (
        df
        .drop_duplicates(
            subset=["company_id", "year"],
            keep="last",
        )
    )

    rows = []

    for _, row in base_rows.iterrows():

        company_id = row["company_id"]
        year = row["year"]
        current_year = _extract_year(year)

        result = {
            "company_id": company_id,
            "year": year,
        }

        for metric_name in metrics:

            lookup = lookups[metric_name]

            for period in [3, 5, 10]:

                value_column = (
                    f"{metric_name}_cagr_{period}yr"
                )

                flag_column = (
                    f"{value_column}_flag"
                )

                if current_year is None:
                    value = None
                    flag = CAGR_INSUFFICIENT
                else:
                    start_value = lookup.get(
                        (
                            company_id,
                            current_year - period,
                        )
                    )

                    end_value = lookup.get(
                        (
                            company_id,
                            current_year,
                        )
                    )

                    value, flag = (
                        calculate_cagr_with_flag(
                            start_value,
                            end_value,
                            period,
                        )
                    )

                result[value_column] = value
                result[flag_column] = flag

        rows.append(result)

    return pd.DataFrame(rows)


# ===== CAGR YEAR VALIDATION =====

_portal_calculate_cagr_with_flag = calculate_cagr_with_flag
_portal_calculate_cagr = calculate_cagr


def _validate_cagr_years(years):
    """Validate CAGR period."""

    try:
        years_value = float(years)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "CAGR years must be a positive number."
        ) from exc

    if years_value <= 0:
        raise ValueError(
            "CAGR years must be greater than zero."
        )


def calculate_cagr_with_flag(
    start_value,
    end_value,
    years,
):
    """Calculate CAGR with portal edge-case flag."""

    _validate_cagr_years(years)

    return _portal_calculate_cagr_with_flag(
        start_value,
        end_value,
        years,
    )


def calculate_cagr(
    start_value,
    end_value,
    years,
):
    """Calculate CAGR with backward-compatible output."""

    _validate_cagr_years(years)

    return _portal_calculate_cagr(
        start_value,
        end_value,
        years,
    )


