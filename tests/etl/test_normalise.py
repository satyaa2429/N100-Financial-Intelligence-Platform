import pytest

from src.etl.normaliser import normalize_ticker, normalize_year


# ============================================================
# normalize_year() - 20 TEST CASES
# ============================================================

@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("Mar-23", "2023-03"),
        ("Mar 23", "2023-03"),
        ("March-2023", "2023-03"),
        ("FY23", "2023-03"),
        ("FY24", "2024-03"),
        ("2023", "2023-03"),
        (2023, "2023-03"),
        (2024, "2024-03"),
        ("2023-03", "2023-03"),
        ("2024-12", "2024-12"),
        ("Dec-22", "2022-12"),
        ("December-2022", "2022-12"),
        ("Jun-23", "2023-06"),
        ("June-2023", "2023-06"),
        ("Sep-24", "2024-09"),
        ("September-2024", "2024-09"),
        (2024.5, "2024-09"),
        ("2024.5", "2024-09"),
        ("TTM", "TTM"),
        ("ttm", "TTM"),
    ],
)
def test_normalize_year_valid(raw_value, expected):
    assert normalize_year(raw_value) == expected


# ============================================================
# normalize_ticker() - 15 TEST CASES
# ============================================================

@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("TCS", "TCS"),
        (" tcs ", "TCS"),
        ("reliance", "RELIANCE"),
        (" INFY", "INFY"),
        ("HDFCBANK ", "HDFCBANK"),
        ("BAJAJ-AUTO", "BAJAJ-AUTO"),
        ("m&m", "M&M"),
        ("ITC", "ITC"),
        ("axisbank", "AXISBANK"),
        ("SBIN", "SBIN"),
        ("LT", "LT"),
        ("ONGC", "ONGC"),
        ("MARUTI", "MARUTI"),
        ("ADANIPORTS", "ADANIPORTS"),
        ("POWERGRID", "POWERGRID"),
    ],
)
def test_normalize_ticker_valid(raw_value, expected):
    assert normalize_ticker(raw_value) == expected
