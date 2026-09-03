import pytest

from src.analytics.ratios import (
    _valid_number,
    calculate_npm,
    calculate_opm,
    calculate_roe,
    calculate_roce,
)


def test_npm():
    assert calculate_npm(100, 1000) == pytest.approx(10.0)


def test_npm_zero_sales():
    assert calculate_npm(100, 0) is None


def test_opm():
    assert calculate_opm(200, 1000) == pytest.approx(20.0)


def test_opm_zero_sales():
    assert calculate_opm(200, 0) is None


def test_roe():
    assert calculate_roe(100, 200, 300) == pytest.approx(20.0)


def test_roe_negative_equity():
    assert calculate_roe(100, -400, 100) is None


def test_roce():
    result = calculate_roce(
        operating_profit=200,
        depreciation=50,
        equity_capital=200,
        reserves=300,
        borrowings=500,
    )

    assert result == pytest.approx(15.0)


def test_roce_invalid_capital():
    assert calculate_roce(
        200,
        50,
        -500,
        100,
        100,
    ) is None

def calculate_debt_to_equity(
    borrowings: object,
    equity_capital: object,
    reserves: object,
) -> float | None:
    """Calculate Debt-to-Equity ratio."""

    values = [
        borrowings,
        equity_capital,
        reserves,
    ]

    if not all(_valid_number(value) for value in values):
        return None

    debt = float(borrowings)

    equity = (
        float(equity_capital)
        + float(reserves)
    )

    if equity <= 0:
        return None

    if debt == 0:
        return 0.0

    return debt / equity


def calculate_interest_coverage(
    operating_profit: object,
    depreciation: object,
    other_income: object,
    interest: object,
) -> float | None:
    """Calculate Interest Coverage Ratio."""

    values = [
        operating_profit,
        depreciation,
        other_income,
        interest,
    ]

    if not all(_valid_number(value) for value in values):
        return None

    interest_value = float(interest)

    if interest_value == 0:
        return None

    # EBIT = operating profit - depreciation
    ebit = (
        float(operating_profit)
        - float(depreciation)
    )

    return (
        ebit + float(other_income)
    ) / interest_value


def calculate_asset_turnover(
    sales: object,
    total_assets: object,
) -> float | None:
    """Calculate Asset Turnover ratio."""

    if not _valid_number(sales) or not _valid_number(total_assets):
        return None

    assets = float(total_assets)

    if assets == 0:
        return None

    return float(sales) / assets