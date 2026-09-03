import pytest

from src.analytics.cashflow_kpis import (
    calculate_capex_intensity,
    calculate_cfo_pat_ratio,
    calculate_fcf,
    calculate_fcf_conversion,
    classify_capital_allocation,
    classify_capex_intensity,
    classify_cfo_quality,
    classify_fcf_conversion,
    detect_distress,
)


def test_fcf():
    result = calculate_fcf(1000, -400)
    assert result == pytest.approx(600.0)


def test_cfo_pat_ratio():
    result = calculate_cfo_pat_ratio(120, 100)
    assert result == pytest.approx(1.2)


def test_cfo_pat_zero_profit():
    result = calculate_cfo_pat_ratio(120, 0)
    assert result is None


def test_high_quality_earnings():
    assert classify_cfo_quality(1.2) == "High Quality"


def test_accrual_risk():
    assert classify_cfo_quality(0.4) == "Accrual Risk"


def test_capex_intensity():
    result = calculate_capex_intensity(-80, 1000)
    assert result == pytest.approx(8.0)


def test_asset_light():
    assert classify_capex_intensity(2.0) == "Asset Light"


def test_capital_intensive():
    assert classify_capex_intensity(9.0) == "Capital Intensive"


def test_fcf_conversion():
    result = calculate_fcf_conversion(600, 1000)
    assert result == pytest.approx(60.0)


def test_fcf_conversion_efficient():
    assert classify_fcf_conversion(70) == "Efficient"


def test_reinvestor_pattern():
    result = classify_capital_allocation(
        100,
        -50,
        -20,
    )

    assert result == "Reinvestor"


def test_distress_signal():
    assert detect_distress(-100, 50) is True


def test_no_distress():
    assert detect_distress(100, -50) is False
