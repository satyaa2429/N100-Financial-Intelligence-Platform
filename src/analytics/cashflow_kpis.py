"""Cash-flow KPIs and capital-allocation analysis."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _valid_number(value: Any) -> bool:
    """Return True when value is a valid finite number."""

    if value is None:
        return False

    try:
        number = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(number)


def calculate_fcf(
    operating_activity: Any,
    investing_activity: Any,
) -> float | None:
    """Calculate Free Cash Flow."""

    if not _valid_number(operating_activity):
        return None

    if not _valid_number(investing_activity):
        return None

    return (
        float(operating_activity)
        + float(investing_activity)
    )


def calculate_free_cash_flow(
    operating_activity: Any,
    investing_activity: Any,
) -> float | None:
    """Backward-compatible alias for FCF."""

    return calculate_fcf(
        operating_activity,
        investing_activity,
    )


def calculate_cfo_pat_ratio(
    operating_activity: Any,
    net_profit: Any,
) -> float | None:
    """Calculate CFO divided by PAT."""

    if not _valid_number(operating_activity):
        return None

    if not _valid_number(net_profit):
        return None

    pat = float(net_profit)

    if pat == 0:
        return None

    return (
        float(operating_activity)
        / pat
    )


def classify_cfo_quality(
    cfo_pat_ratio: Any,
) -> str | None:
    """Classify CFO quality using portal thresholds."""

    if not _valid_number(cfo_pat_ratio):
        return None

    ratio = float(cfo_pat_ratio)

    if ratio > 1.0:
        return "High Quality"

    if ratio >= 0.5:
        return "Moderate"

    return "Accrual Risk"


def calculate_capex_intensity(
    investing_activity: Any,
    sales: Any,
) -> float | None:
    """Calculate CapEx Intensity percentage."""

    if not _valid_number(investing_activity):
        return None

    if not _valid_number(sales):
        return None

    sales_value = float(sales)

    if sales_value == 0:
        return None

    return (
        abs(float(investing_activity))
        / abs(sales_value)
        * 100
    )


def classify_capex_intensity(
    capex_intensity: Any,
) -> str | None:
    """Classify CapEx Intensity."""

    if not _valid_number(capex_intensity):
        return None

    value = float(capex_intensity)

    if value < 3:
        return "Asset Light"

    if value > 8:
        return "Capital Intensive"

    return "Moderate"


def calculate_fcf_conversion(
    free_cash_flow: Any,
    operating_profit: Any,
) -> float | None:
    """Calculate FCF Conversion percentage."""

    if not _valid_number(free_cash_flow):
        return None

    if not _valid_number(operating_profit):
        return None

    profit = float(operating_profit)

    if profit == 0:
        return None

    return (
        float(free_cash_flow)
        / profit
        * 100
    )


def classify_fcf_conversion(
    fcf_conversion: Any,
) -> str | None:
    """Classify FCF Conversion."""

    if not _valid_number(fcf_conversion):
        return None

    value = float(fcf_conversion)

    if value > 60:
        return "Efficient"

    if value < 30:
        return "CapEx Heavy"

    return "Moderate"


def cash_flow_sign(
    value: Any,
) -> str:
    """Return positive, negative, or zero sign."""

    if not _valid_number(value):
        return "0"

    number = float(value)

    if number > 0:
        return "+"

    if number < 0:
        return "-"

    return "0"


def cash_flow_signs(
    operating_activity: Any,
    investing_activity: Any,
    financing_activity: Any,
) -> tuple[str, str, str]:
    """Return CFO, CFI and CFF signs."""

    return (
        cash_flow_sign(operating_activity),
        cash_flow_sign(investing_activity),
        cash_flow_sign(financing_activity),
    )


def classify_capital_allocation(
    operating_activity: Any,
    investing_activity: Any,
    financing_activity: Any,
    cfo_pat_ratio: Any = None,
) -> str:
    """Classify the exact portal capital-allocation pattern."""

    signs = cash_flow_signs(
        operating_activity,
        investing_activity,
        financing_activity,
    )

    if signs == ("+", "-", "-"):

        if (
            _valid_number(cfo_pat_ratio)
            and float(cfo_pat_ratio) > 1.0
        ):
            return "Shareholder Returns"

        return "Reinvestor"

    if signs == ("+", "+", "-"):
        return "Liquidating Assets"

    if signs == ("-", "+", "+"):
        return "Distress Signal"

    if signs == ("-", "-", "+"):
        return "Growth Funded by Debt"

    if signs == ("+", "+", "+"):
        return "Cash Accumulator"

    if signs == ("-", "-", "-"):
        return "Pre-Revenue"

    if signs == ("+", "-", "+"):
        return "Mixed"

    return "Unclassified"


def classify_capital_allocation_pattern(
    operating_activity: Any,
    investing_activity: Any,
    financing_activity: Any,
    cfo_pat_ratio: Any = None,
) -> str:
    """Backward-compatible capital allocation alias."""

    return classify_capital_allocation(
        operating_activity,
        investing_activity,
        financing_activity,
        cfo_pat_ratio,
    )


def detect_distress(
    operating_activity: Any,
    financing_activity: Any,
) -> bool:
    """Detect negative CFO supported by positive financing."""

    if not _valid_number(operating_activity):
        return False

    if not _valid_number(financing_activity):
        return False

    return (
        float(operating_activity) < 0
        and float(financing_activity) > 0
    )


def rolling_cfo_pat_quality(
    ratios: list[Any],
) -> tuple[float | None, str | None]:
    """Calculate five-year average CFO/PAT quality."""

    valid = [
        float(value)
        for value in ratios
        if _valid_number(value)
    ]

    if not valid:
        return None, None

    latest_five = valid[-5:]

    average = (
        sum(latest_five)
        / len(latest_five)
    )

    return (
        average,
        classify_cfo_quality(average),
    )


def has_three_negative_fcf(
    values: list[Any],
) -> bool:
    """Detect three consecutive negative FCF years."""

    consecutive = 0

    for value in values:

        if (
            _valid_number(value)
            and float(value) < 0
        ):
            consecutive += 1

            if consecutive >= 3:
                return True

        else:
            consecutive = 0

    return False


def compute_cashflow_kpis(
    cashflow: pd.DataFrame,
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Compute cash-flow KPIs for each company-year."""

    required_cf = {
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "financing_activity",
    }

    required_pl = {
        "company_id",
        "year",
        "net_profit",
        "sales",
        "operating_profit",
    }

    missing_cf = (
        required_cf
        - set(cashflow.columns)
    )

    missing_pl = (
        required_pl
        - set(profit_loss.columns)
    )

    if missing_cf:
        raise ValueError(
            "Missing cashflow columns: "
            + ", ".join(sorted(missing_cf))
        )

    if missing_pl:
        raise ValueError(
            "Missing profit/loss columns: "
            + ", ".join(sorted(missing_pl))
        )

    cf = cashflow[
        [
            "company_id",
            "year",
            "operating_activity",
            "investing_activity",
            "financing_activity",
        ]
    ].copy()

    pl = profit_loss[
        [
            "company_id",
            "year",
            "net_profit",
            "sales",
            "operating_profit",
        ]
    ].copy()

    df = cf.merge(
        pl,
        on=[
            "company_id",
            "year",
        ],
        how="left",
    )

    rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():

        cfo = row["operating_activity"]
        cfi = row["investing_activity"]
        cff = row["financing_activity"]

        pat = row["net_profit"]
        sales = row["sales"]

        operating_profit = row[
            "operating_profit"
        ]

        fcf = calculate_fcf(
            cfo,
            cfi,
        )

        cfo_pat_ratio = (
            calculate_cfo_pat_ratio(
                cfo,
                pat,
            )
        )

        capex_intensity = (
            calculate_capex_intensity(
                cfi,
                sales,
            )
        )

        fcf_conversion = (
            calculate_fcf_conversion(
                fcf,
                operating_profit,
            )
        )

        cfo_sign, cfi_sign, cff_sign = (
            cash_flow_signs(
                cfo,
                cfi,
                cff,
            )
        )

        pattern = (
            classify_capital_allocation(
                cfo,
                cfi,
                cff,
                cfo_pat_ratio,
            )
        )

        rows.append(
            {
                "company_id": row[
                    "company_id"
                ],
                "year": row[
                    "year"
                ],
                "free_cash_flow_cr": fcf,
                "cfo_pat_ratio": (
                    cfo_pat_ratio
                ),
                "cfo_quality_label": (
                    classify_cfo_quality(
                        cfo_pat_ratio
                    )
                ),
                "capex_intensity_pct": (
                    capex_intensity
                ),
                "capex_intensity_label": (
                    classify_capex_intensity(
                        capex_intensity
                    )
                ),
                "fcf_conversion_pct": (
                    fcf_conversion
                ),
                "fcf_conversion_label": (
                    classify_fcf_conversion(
                        fcf_conversion
                    )
                ),
                "cfo_sign": cfo_sign,
                "cfi_sign": cfi_sign,
                "cff_sign": cff_sign,
                "pattern_label": pattern,
                "distress_flag": (
                    detect_distress(
                        cfo,
                        cff,
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def compute_cash_flow_kpis(
    cashflow: pd.DataFrame,
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Backward-compatible KPI function alias."""

    return compute_cashflow_kpis(
        cashflow,
        profit_loss,
    )


# ===== POPULATE RATIOS COMPATIBILITY =====

_original_compute_cashflow_kpis = compute_cashflow_kpis


def compute_cashflow_kpis(
    cashflow: pd.DataFrame,
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Return cash KPIs with source CFO and CFI columns."""

    result = _original_compute_cashflow_kpis(
        cashflow,
        profit_loss,
    )

    source_columns = cashflow[
        [
            "company_id",
            "year",
            "operating_activity",
            "investing_activity",
        ]
    ].copy()

    source_columns = (
        source_columns
        .drop_duplicates(
            subset=[
                "company_id",
                "year",
            ],
            keep="last",
        )
    )

    result = result.merge(
        source_columns,
        on=[
            "company_id",
            "year",
        ],
        how="left",
        validate="one_to_one",
    )

    return result


def compute_cash_flow_kpis(
    cashflow: pd.DataFrame,
    profit_loss: pd.DataFrame,
) -> pd.DataFrame:
    """Backward-compatible cash KPI function."""

    return compute_cashflow_kpis(
    cashflow,
    profit_loss,
)