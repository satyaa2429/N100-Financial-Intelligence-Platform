"""Tests for N100 ETL normalisation utilities."""

import pytest

from src.etl.normaliser import normalize_ticker, normalize_year


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mar-23", "2023-03"),
        ("Mar 23", "2023-03"),
        ("March-2023", "2023-03"),
        ("2023", "2023-03"),
        (2023, "2023-03"),
        ("FY23", "2023-03"),
        ("fy23", "2023-03"),
        ("Dec-22", "2022-12"),
        ("Jun-23", "2023-06"),
        ("2023-03", "2023-03"),
        ("Jan-24", "2024-01"),
        ("Feb-24", "2024-02"),
        ("Apr-24", "2024-04"),
        ("May-24", "2024-05"),
        ("Jul-24", "2024-07"),
        ("Aug-24", "2024-08"),
        ("Sep-24", "2024-09"),
        ("Oct-24", "2024-10"),
        ("Nov-24", "2024-11"),
        ("December-2024", "2024-12"),
    ],
)
def test_normalize_year_valid(raw: object, expected: str) -> None:
    """Check valid financial year formats."""
    assert normalize_year(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "garbage",
    ],
)
def test_normalize_year_invalid(raw: object) -> None:
    """Check invalid year values."""
    with pytest.raises(ValueError):
        normalize_year(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TCS", "TCS"),
        (" tcs ", "TCS"),
        ("HDFCBANK", "HDFCBANK"),
        (" hdfcbank ", "HDFCBANK"),
        ("M&M", "M&M"),
        ("m&m", "M&M"),
        ("BAJAJ-AUTO", "BAJAJ-AUTO"),
        (" bajaj-auto ", "BAJAJ-AUTO"),
        ("INFY", "INFY"),
        ("RELIANCE", "RELIANCE"),
        ("ITC", "ITC"),
        ("SBIN", "SBIN"),
        ("LT", "LT"),
        ("ONGC", "ONGC"),
        ("AXISBANK", "AXISBANK"),
    ],
)
def test_normalize_ticker_valid(raw: object, expected: str) -> None:
    """Check ticker stripping and upper-casing."""
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "A",
        "ABCDEFGHIJKLM",
    ],
)
def test_normalize_ticker_invalid(raw: object) -> None:
    """Check invalid ticker values."""
    with pytest.raises(ValueError):
        normalize_ticker(raw)