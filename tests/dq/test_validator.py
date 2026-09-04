"""Unit tests for all N100 data-quality validation rules."""

from types import SimpleNamespace

import pandas as pd

from src.etl import validator as v


def empty_annual():
    return pd.DataFrame(columns=["company_id", "year"])


def empty_child():
    return pd.DataFrame(columns=["company_id", "year"])


def find_rule(failures, rule_id):
    matches = [
        item
        for item in failures
        if item["rule_id"] == rule_id
    ]
    assert matches, f"{rule_id} did not trigger"
    return matches


def test_dq01_duplicate_company_primary_key():
    datasets = {
        "companies": pd.DataFrame(
            {
                "id": ["TCS", "TCS"],
            }
        )
    }

    failures = []

    v.validate_dq01(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-01",
    )

    assert len(matches) == 2
    assert all(
        row["severity"] == "CRITICAL"
        for row in matches
    )


def test_dq02_duplicate_annual_key():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2024-03", "2024-03"],
            }
        ),
        "balancesheet": empty_annual(),
        "cashflow": empty_annual(),
    }

    failures = []

    v.validate_dq02(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-02",
    )

    assert len(matches) == 2
    assert all(
        row["severity"] == "CRITICAL"
        for row in matches
    )


def test_dq03_foreign_key_violation():
    datasets = {
        "companies": pd.DataFrame(
            {"id": ["TCS"]}
        ),
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["UNKNOWN"],
                "year": ["2024-03"],
            }
        ),
        "balancesheet": empty_child(),
        "cashflow": empty_child(),
        "analysis": empty_child(),
        "documents": empty_child(),
        "prosandcons": empty_child(),
    }

    failures = []

    v.validate_dq03(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-03",
    )

    assert len(matches) == 1
    assert matches[0]["severity"] == "CRITICAL"


def test_dq04_balance_sheet_mismatch():
    datasets = {
        "balancesheet": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "total_assets": [100.0],
                "total_liabilities": [95.0],
            }
        )
    }

    failures = []

    v.validate_dq04(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-04",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq05_opm_cross_check():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "sales": [100.0],
                "operating_profit": [20.0],
                "opm_percentage": [10.0],
            }
        )
    }

    failures = []

    v.validate_dq05(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-05",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq06_non_positive_sales():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "sales": [0],
            }
        )
    }

    failures = []

    v.validate_dq06(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-06",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq07_invalid_year_format():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["Mar-24"],
            }
        ),
        "balancesheet": empty_annual(),
        "cashflow": empty_annual(),
    }

    failures = []

    v.validate_dq07(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-07",
    )

    assert matches[0]["severity"] == "CRITICAL"


def test_dq08_invalid_ticker_format():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": [" tcs "],
                "year": ["2024-03"],
            }
        ),
        "balancesheet": empty_child(),
        "cashflow": empty_child(),
        "analysis": empty_child(),
        "documents": empty_child(),
        "prosandcons": empty_child(),
    }

    failures = []

    v.validate_dq08(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-08",
    )

    assert matches[0]["severity"] == "CRITICAL"


def test_dq09_net_cash_mismatch():
    datasets = {
        "cashflow": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "operating_activity": [100.0],
                "investing_activity": [-20.0],
                "financing_activity": [-30.0],
                "net_cash_flow": [0.0],
            }
        )
    }

    failures = []

    v.validate_dq09(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-09",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq10_negative_fixed_assets():
    datasets = {
        "balancesheet": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "fixed_assets": [-1.0],
            }
        )
    }

    failures = []

    v.validate_dq10(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-10",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq11_tax_rate_out_of_range():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "tax_percentage": [75.0],
            }
        )
    }

    failures = []

    v.validate_dq11(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-11",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq12_dividend_payout_above_cap():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "dividend_payout": [250.0],
            }
        )
    }

    failures = []

    v.validate_dq12(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-12",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq13_invalid_annual_report_url(monkeypatch):
    datasets = {
        "documents": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "Year": ["2024"],
                "Annual_Report": [
                    "https://example.com/report.pdf"
                ],
            }
        )
    }

    monkeypatch.setattr(
        v.requests,
        "head",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=404
        ),
    )

    failures = []

    v.validate_dq13(
        datasets,
        failures,
        check_urls=True,
    )

    matches = find_rule(
        failures,
        "DQ-13",
    )

    assert matches[0]["severity"] == "WARNING"
    assert "404" in matches[0]["issue"]


def test_dq14_eps_sign_inconsistency():
    datasets = {
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "net_profit": [100.0],
                "eps": [0.0],
            }
        )
    }

    failures = []

    v.validate_dq14(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-14",
    )

    assert matches[0]["severity"] == "WARNING"


def test_dq15_strict_balance_check():
    datasets = {
        "balancesheet": pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2024-03"],
                "total_assets": [100.0],
                "total_liabilities": [99.0],
            }
        )
    }

    failures = []

    v.validate_dq15(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-15",
    )

    assert matches[0]["severity"] == "INFO"


def test_dq16_less_than_five_year_history():
    datasets = {
        "companies": pd.DataFrame(
            {
                "id": ["TCS"],
            }
        ),
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2023-03", "2024-03"],
            }
        ),
        "balancesheet": pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2023-03", "2024-03"],
            }
        ),
        "cashflow": pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2023-03", "2024-03"],
            }
        ),
    }

    failures = []

    v.validate_dq16(
        datasets,
        failures,
    )

    matches = find_rule(
        failures,
        "DQ-16",
    )

    assert len(matches) == 3
    assert all(
        row["severity"] == "WARNING"
        for row in matches
    )
