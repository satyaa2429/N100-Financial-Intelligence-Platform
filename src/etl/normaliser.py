"""Normalisation utilities for the N100 ETL pipeline."""

import math
import re
from numbers import Real


MONTH_MAP = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}


def normalize_ticker(value: object) -> str:
    """Normalise company ticker to uppercase stripped text."""

    if value is None:
        raise ValueError("Ticker cannot be empty")

    ticker = str(value).strip().upper()

    if ticker in {"", "NAN", "NONE", "<NA>", "NAT"}:
        raise ValueError("Ticker cannot be empty")

    if len(ticker) < 2 or len(ticker) > 12:
        raise ValueError(f"Invalid ticker length: {ticker}")

    return ticker


def normalize_year(value: object) -> str:
    """Normalise financial year labels to YYYY-MM format."""

    if value is None:
        raise ValueError("Year cannot be empty")

    # Handle numeric values from Excel.
    if isinstance(value, Real):
        numeric_value = float(value)

        if math.isnan(numeric_value):
            raise ValueError("Year cannot be empty")

        # Example: 2023 / 2023.0 -> 2023-03
        if numeric_value.is_integer():
            year_number = int(numeric_value)

            if 1900 <= year_number <= 2100:
                return f"{year_number}-03"

        # Interim half-year value found in balancesheet.xlsx.
        # Example: 2024.5 -> 2024-09
        whole_year = int(numeric_value)

        if (
            1900 <= whole_year <= 2100
            and abs(numeric_value - (whole_year + 0.5)) < 0.000001
        ):
            return f"{whole_year}-09"

    year = str(value).strip()

    if year.upper() in {"", "NAN", "NONE", "<NA>", "NAT"}:
        raise ValueError("Year cannot be empty")

    # Trailing Twelve Months.
    if year.upper() == "TTM":
        return "TTM"

    # String form of interim half-year.
    # Example: "2024.5" -> "2024-09"
    match = re.fullmatch(r"(\d{4})\.5", year)

    if match:
        return f"{match.group(1)}-09"

    # Already normalised.
    # Example: 2023-03
    match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", year)

    if match:
        return year

    # Plain financial year.
    # Example: 2023 -> 2023-03
    if re.fullmatch(r"\d{4}", year):
        return f"{year}-03"

    # FY formats:
    # FY23
    # FY 23
    # FY2023
    # FY 2023
    match = re.fullmatch(
        r"FY\s*(\d{2}|\d{4})",
        year,
        re.IGNORECASE,
    )

    if match:
        year_text = match.group(1)

        if len(year_text) == 2:
            year_text = f"20{year_text}"

        return f"{year_text}-03"

    # Month-based formats:
    # Mar-23
    # Mar 23
    # Mar-2023
    # Mar 2023
    # March-2023
    # Mar 2023 15
    # Mar 2016 9m
    match = re.fullmatch(
        r"([A-Za-z]+)[\s-]+"
        r"(\d{2}|\d{4})"
        r"(?:[\s-]+\d+\s*[mM]?)?",
        year,
    )

    if match:
        month_text = match.group(1).lower()
        year_text = match.group(2)

        if month_text not in MONTH_MAP:
            raise ValueError(f"Invalid month: {value}")

        if len(year_text) == 2:
            year_text = f"20{year_text}"

        month_number = MONTH_MAP[month_text]

        return f"{year_text}-{month_number}"

    raise ValueError(f"Unable to parse year: {value}")