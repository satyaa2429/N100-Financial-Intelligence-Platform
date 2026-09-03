import pytest

from src.analytics.cagr import (
    calculate_cagr,
)


def test_three_year_cagr():
    result, turnaround = calculate_cagr(
        100,
        133.1,
        3,
    )

    assert result == pytest.approx(
        10.0,
        abs=0.01,
    )

    assert turnaround is False


def test_five_year_cagr():
    result, turnaround = calculate_cagr(
        100,
        161.051,
        5,
    )

    assert result == pytest.approx(
        10.0,
        abs=0.01,
    )

    assert turnaround is False


def test_ten_year_cagr():
    result, turnaround = calculate_cagr(
        100,
        259.374,
        10,
    )

    assert result == pytest.approx(
        10.0,
        abs=0.01,
    )

    assert turnaround is False


def test_turnaround():
    result, turnaround = calculate_cagr(
        -100,
        150,
        5,
    )

    assert result is None
    assert turnaround is True


def test_zero_base():
    result, turnaround = calculate_cagr(
        0,
        100,
        5,
    )

    assert result is None
    assert turnaround is False


def test_negative_end():
    result, turnaround = calculate_cagr(
        100,
        -50,
        5,
    )

    assert result is None
    assert turnaround is False


def test_missing_start():
    result, turnaround = calculate_cagr(
        None,
        100,
        3,
    )

    assert result is None
    assert turnaround is False


def test_invalid_year_window():
    with pytest.raises(ValueError):
        calculate_cagr(
            100,
            150,
            0,
        )