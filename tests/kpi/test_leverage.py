import pytest

from src.analytics.ratios import (
    calculate_asset_turnover,
    calculate_debt_to_equity,
    calculate_interest_coverage,
)


def test_debt_to_equity():
    result = calculate_debt_to_equity(
        borrowings=500,
        equity_capital=200,
        reserves=300,
    )

    assert result == pytest.approx(1.0)


def test_debt_free_company():
    result = calculate_debt_to_equity(
        borrowings=0,
        equity_capital=200,
        reserves=300,
    )

    assert result == pytest.approx(0.0)


def test_debt_to_equity_negative_equity():
    result = calculate_debt_to_equity(
        borrowings=500,
        equity_capital=-400,
        reserves=100,
    )

    assert result is None


def test_interest_coverage():
    result = calculate_interest_coverage(
        operating_profit=500,
        depreciation=100,
        other_income=50,
        interest=50,
    )

    assert result == pytest.approx(11.0)


def test_interest_coverage_zero_interest():
    result = calculate_interest_coverage(
        operating_profit=500,
        depreciation=100,
        other_income=50,
        interest=0,
    )

    assert result is None


def test_asset_turnover():
    result = calculate_asset_turnover(
        sales=1000,
        total_assets=500,
    )

    assert result == pytest.approx(2.0)


def test_asset_turnover_zero_assets():
    result = calculate_asset_turnover(
        sales=1000,
        total_assets=0,
    )

    assert result is None