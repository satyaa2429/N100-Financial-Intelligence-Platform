"""Financial ratio calculations for the N100 platform."""

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


def calculate_npm(
    net_profit: Any,
    sales: Any,
) -> float | None:
    """Calculate Net Profit Margin."""

    if not _valid_number(net_profit):
        return None

    if not _valid_number(sales):
        return None

    sales_value = float(sales)

    if sales_value == 0:
        return None

    return float(net_profit) / sales_value * 100


def calculate_opm(
    operating_profit: Any,
    sales: Any,
) -> float | None:
    """Calculate Operating Profit Margin."""

    if not _valid_number(operating_profit):
        return None

    if not _valid_number(sales):
        return None

    sales_value = float(sales)

    if sales_value == 0:
        return None

    return float(operating_profit) / sales_value * 100


def calculate_roe(
    net_profit: Any,
    equity_capital: Any,
    reserves: Any,
) -> float | None:
    """Calculate Return on Equity."""

    values = [
        net_profit,
        equity_capital,
        reserves,
    ]

    if not all(_valid_number(v) for v in values):
        return None

    equity = (
        float(equity_capital)
        + float(reserves)
    )

    if equity <= 0:
        return None

    return (
        float(net_profit)
        / equity
        * 100
    )


def calculate_roce(
    operating_profit: Any,
    depreciation: Any,
    equity_capital: Any,
    reserves: Any,
    borrowings: Any,
) -> float | None:
    """Calculate Return on Capital Employed."""

    values = [
        operating_profit,
        depreciation,
        equity_capital,
        reserves,
        borrowings,
    ]

    if not all(_valid_number(v) for v in values):
        return None

    ebit = (
        float(operating_profit)
        - float(depreciation)
    )

    capital_employed = (
        float(equity_capital)
        + float(reserves)
        + float(borrowings)
    )

    if capital_employed <= 0:
        return None

    return (
        ebit
        / capital_employed
        * 100
    )


def calculate_roa(
    net_profit: Any,
    total_assets: Any,
) -> float | None:
    """Calculate Return on Assets."""

    if not _valid_number(net_profit):
        return None

    if not _valid_number(total_assets):
        return None

    assets = float(total_assets)

    if assets <= 0:
        return None

    return (
        float(net_profit)
        / assets
        * 100
    )


def calculate_debt_to_equity(
    borrowings: Any,
    equity_capital: Any,
    reserves: Any,
) -> float | None:
    """Calculate Debt-to-Equity."""

    values = [
        borrowings,
        equity_capital,
        reserves,
    ]

    if not all(_valid_number(v) for v in values):
        return None

    equity = (
        float(equity_capital)
        + float(reserves)
    )

    if equity <= 0:
        return None

    debt = float(borrowings)

    if debt == 0:
        return 0.0

    return debt / equity


def calculate_net_debt(
    borrowings: Any,
    investments: Any,
) -> float | None:
    """Calculate Net Debt."""

    if not _valid_number(borrowings):
        return None

    if not _valid_number(investments):
        return None

    return (
        float(borrowings)
        - float(investments)
    )


def calculate_interest_coverage(
    operating_profit: Any,
    other_income: Any,
    interest: Any,
) -> float | None:
    """Calculate Interest Coverage Ratio."""

    if not _valid_number(operating_profit):
        return None

    other_income_value = (
        float(other_income)
        if _valid_number(other_income)
        else 0.0
    )

    if not _valid_number(interest):
        return None

    interest_value = float(interest)

    if interest_value == 0:
        return None

    numerator = (
        float(operating_profit)
        + other_income_value
    )

    return numerator / interest_value


def calculate_asset_turnover(
    sales: Any,
    total_assets: Any,
) -> float | None:
    """Calculate Asset Turnover."""

    if not _valid_number(sales):
        return None

    if not _valid_number(total_assets):
        return None

    assets = float(total_assets)

    if assets == 0:
        return None

    return float(sales) / assets


def get_icr_label(
    interest: Any,
    icr: Any,
) -> str | None:
    """Return ICR label."""

    if (
        _valid_number(interest)
        and float(interest) == 0
    ):
        return "Debt Free"

    if not _valid_number(icr):
        return None

    return "Normal"


def get_icr_warning_flag(
    interest: Any,
    icr: Any,
) -> bool:
    """Flag ICR below 1.5."""

    if (
        _valid_number(interest)
        and float(interest) == 0
    ):
        return False

    if not _valid_number(icr):
        return False

    return float(icr) < 1.5


def get_high_leverage_flag(
    debt_to_equity: Any,
    broad_sector: Any = None,
) -> bool:
    """Flag D/E above 5 for non-financial companies."""

    if not _valid_number(debt_to_equity):
        return False

    sector = (
        ""
        if broad_sector is None
        else str(broad_sector).lower()
    )

    financial_words = [
        "financial",
        "bank",
        "nbfc",
        "insurance",
    ]

    is_financial = any(
        word in sector
        for word in financial_words
    )

    if is_financial:
        return False

    return float(debt_to_equity) > 5


def get_opm_mismatch_flag(
    calculated_opm: Any,
    source_opm: Any,
    tolerance: float = 1.0,
) -> bool:
    """Flag OPM mismatch greater than tolerance."""

    if not _valid_number(calculated_opm):
        return False

    if not _valid_number(source_opm):
        return False

    return (
        abs(
            float(calculated_opm)
            - float(source_opm)
        )
        > tolerance
    )


def _compute_single_ratio_record(
    *,
    net_profit: Any,
    sales: Any,
    operating_profit: Any,
    depreciation: Any,
    equity_capital: Any,
    reserves: Any,
    borrowings: Any,
    investments: Any = None,
    other_income: Any = None,
    interest: Any = None,
    total_assets: Any = None,
    source_opm: Any = None,
    broad_sector: Any = None,
) -> dict[str, Any]:
    """Compute one ratio record."""

    npm = calculate_npm(
        net_profit,
        sales,
    )

    opm = calculate_opm(
        operating_profit,
        sales,
    )

    roe = calculate_roe(
        net_profit,
        equity_capital,
        reserves,
    )

    roce = calculate_roce(
        operating_profit,
        depreciation,
        equity_capital,
        reserves,
        borrowings,
    )

    roa = calculate_roa(
        net_profit,
        total_assets,
    )

    debt_to_equity = (
        calculate_debt_to_equity(
            borrowings,
            equity_capital,
            reserves,
        )
    )

    icr = calculate_interest_coverage(
        operating_profit,
        other_income,
        interest,
    )

    return {
        "net_profit_margin_pct": npm,
        "operating_profit_margin_pct": opm,
        "return_on_equity_pct": roe,
        "return_on_capital_employed_pct": roce,
        "return_on_assets_pct": roa,
        "debt_to_equity": debt_to_equity,

        # Keep both names for compatibility.
        "interest_coverage": icr,
        "interest_coverage_ratio": icr,

        "asset_turnover": (
            calculate_asset_turnover(
                sales,
                total_assets,
            )
        ),

        "net_debt_cr": (
            calculate_net_debt(
                borrowings,
                investments,
            )
        ),

        "icr_label": (
            get_icr_label(
                interest,
                icr,
            )
        ),

        "icr_warning_flag": (
            get_icr_warning_flag(
                interest,
                icr,
            )
        ),

        "high_leverage_flag": (
            get_high_leverage_flag(
                debt_to_equity,
                broad_sector,
            )
        ),

        "opm_mismatch_flag": (
            get_opm_mismatch_flag(
                opm,
                source_opm,
            )
        ),
    }


def _value(
    row: pd.Series,
    column: str,
) -> Any:
    """Read a DataFrame value safely."""

    if column not in row.index:
        return None

    return row[column]


def _compute_dataframe_ratios(
    pnl: pd.DataFrame,
    bs: pd.DataFrame,
) -> pd.DataFrame:
    """Compute financial ratios from P&L and balance sheet tables."""

    required_pnl = {
        "company_id",
        "year",
        "net_profit",
        "sales",
        "operating_profit",
    }

    required_bs = {
        "company_id",
        "year",
        "equity_capital",
        "reserves",
        "borrowings",
        "total_assets",
    }

    missing_pnl = (
        required_pnl
        - set(pnl.columns)
    )

    missing_bs = (
        required_bs
        - set(bs.columns)
    )

    if missing_pnl:
        raise ValueError(
            "P&L missing columns: "
            + ", ".join(
                sorted(missing_pnl)
            )
        )

    if missing_bs:
        raise ValueError(
            "Balance Sheet missing columns: "
            + ", ".join(
                sorted(missing_bs)
            )
        )

    pnl_columns = [
        column
        for column in [
            "company_id",
            "year",
            "net_profit",
            "sales",
            "operating_profit",
            "depreciation",
            "other_income",
            "interest",
            "opm_percentage",
        ]
        if column in pnl.columns
    ]

    bs_columns = [
        column
        for column in [
            "company_id",
            "year",
            "equity_capital",
            "reserves",
            "borrowings",
            "investments",
            "total_assets",
        ]
        if column in bs.columns
    ]

    merged = pnl[
        pnl_columns
    ].merge(
        bs[bs_columns],
        on=[
            "company_id",
            "year",
        ],
        how="inner",
        validate="one_to_one",
    )

    records: list[
        dict[str, Any]
    ] = []

    for _, row in merged.iterrows():

        result = (
            _compute_single_ratio_record(
                net_profit=_value(
                    row,
                    "net_profit",
                ),
                sales=_value(
                    row,
                    "sales",
                ),
                operating_profit=_value(
                    row,
                    "operating_profit",
                ),
                depreciation=_value(
                    row,
                    "depreciation",
                ),
                equity_capital=_value(
                    row,
                    "equity_capital",
                ),
                reserves=_value(
                    row,
                    "reserves",
                ),
                borrowings=_value(
                    row,
                    "borrowings",
                ),
                investments=_value(
                    row,
                    "investments",
                ),
                other_income=_value(
                    row,
                    "other_income",
                ),
                interest=_value(
                    row,
                    "interest",
                ),
                total_assets=_value(
                    row,
                    "total_assets",
                ),
                source_opm=_value(
                    row,
                    "opm_percentage",
                ),
            )
        )

        result["company_id"] = row[
            "company_id"
        ]

        result["year"] = row[
            "year"
        ]

        records.append(
            result
        )

    columns_first = [
        "company_id",
        "year",
    ]

    result_df = pd.DataFrame(
        records
    )

    other_columns = [
        column
        for column in result_df.columns
        if column not in columns_first
    ]

    return result_df[
        columns_first
        + other_columns
    ]


def compute_financial_ratios(
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame | dict[str, Any]:
    """
    Compute ratios.

    Supports:
    compute_financial_ratios(pnl_df, bs_df)

    and individual keyword inputs.
    """

    if len(args) == 2:

        pnl = args[0]
        bs = args[1]

        if (
            isinstance(pnl, pd.DataFrame)
            and isinstance(bs, pd.DataFrame)
        ):
            return _compute_dataframe_ratios(
                pnl,
                bs,
            )

        raise TypeError(
            "Two positional arguments must be "
            "Pandas DataFrames."
        )

    if args:
        raise TypeError(
            "Use either two DataFrames or keyword arguments."
        )

    return _compute_single_ratio_record(
        **kwargs
    )


def compute_profitability_ratios(
    *,
    net_profit: Any,
    sales: Any,
    operating_profit: Any,
    depreciation: Any,
    equity_capital: Any,
    reserves: Any,
    borrowings: Any,
    total_assets: Any = None,
) -> dict[str, Any]:
    """Compute profitability ratios."""

    return {
        "net_profit_margin_pct": (
            calculate_npm(
                net_profit,
                sales,
            )
        ),
        "operating_profit_margin_pct": (
            calculate_opm(
                operating_profit,
                sales,
            )
        ),
        "return_on_equity_pct": (
            calculate_roe(
                net_profit,
                equity_capital,
                reserves,
            )
        ),
        "return_on_capital_employed_pct": (
            calculate_roce(
                operating_profit,
                depreciation,
                equity_capital,
                reserves,
                borrowings,
            )
        ),
        "return_on_assets_pct": (
            calculate_roa(
                net_profit,
                total_assets,
            )
        ),
    }


# ===== FULL DATAFRAME COMPATIBILITY =====

_previous_compute_financial_ratios = compute_financial_ratios


def compute_financial_ratios(*args, **kwargs):
    """Support DataFrame pipeline while preserving source columns."""

    if len(args) == 2:

        pnl, bs = args

        if not isinstance(pnl, pd.DataFrame):
            raise TypeError(
                "First argument must be a pandas DataFrame."
            )

        if not isinstance(bs, pd.DataFrame):
            raise TypeError(
                "Second argument must be a pandas DataFrame."
            )

        merged = pnl.merge(
            bs,
            on=[
                "company_id",
                "year",
            ],
            how="left",
            suffixes=(
                "_pnl",
                "_bs",
            ),
            validate="one_to_one",
        )

        calculated_rows = []

        for _, row in merged.iterrows():

            result = {
                "net_profit_margin_pct":
                    calculate_npm(
                        row.get("net_profit"),
                        row.get("sales"),
                    ),

                "operating_profit_margin_pct":
                    calculate_opm(
                        row.get("operating_profit"),
                        row.get("sales"),
                    ),

                "return_on_equity_pct":
                    calculate_roe(
                        row.get("net_profit"),
                        row.get("equity_capital"),
                        row.get("reserves"),
                    ),

                "return_on_capital_employed_pct":
                    calculate_roce(
                        row.get("operating_profit"),
                        row.get("depreciation"),
                        row.get("equity_capital"),
                        row.get("reserves"),
                        row.get("borrowings"),
                    ),

                "return_on_assets_pct":
                    calculate_roa(
                        row.get("net_profit"),
                        row.get("total_assets"),
                    ),

                "debt_to_equity":
                    calculate_debt_to_equity(
                        row.get("borrowings"),
                        row.get("equity_capital"),
                        row.get("reserves"),
                    ),

                "net_debt_cr":
                    calculate_net_debt(
                        row.get("borrowings"),
                        row.get("investments"),
                    ),

                "interest_coverage":
                    calculate_interest_coverage(
                        row.get("operating_profit"),
                        row.get("other_income"),
                        row.get("interest"),
                    ),

                "asset_turnover":
                    calculate_asset_turnover(
                        row.get("sales"),
                        row.get("total_assets"),
                    ),
            }

            icr = result[
                "interest_coverage"
            ]

            result[
                "interest_coverage_ratio"
            ] = icr

            result[
                "icr_label"
            ] = get_icr_label(
                row.get("interest"),
                icr,
            )

            result[
                "icr_warning_flag"
            ] = get_icr_warning_flag(
                row.get("interest"),
                icr,
            )

            result[
                "high_leverage_flag"
            ] = get_high_leverage_flag(
                result[
                    "debt_to_equity"
                ],
                row.get("broad_sector"),
            )

            result[
                "opm_mismatch_flag"
            ] = get_opm_mismatch_flag(
                result[
                    "operating_profit_margin_pct"
                ],
                row.get("opm_percentage"),
            )

            calculated_rows.append(
                result
            )

        calculated = pd.DataFrame(
            calculated_rows,
            index=merged.index,
        )

        for column in calculated.columns:
            merged[column] = calculated[column]

        return merged

    if len(args) != 0:
        raise TypeError(
            "Use two DataFrames or keyword arguments."
        )

    return _previous_compute_financial_ratios(
        **kwargs
    )


# ===== ICR KEYWORD COMPATIBILITY =====

_portal_calculate_interest_coverage = calculate_interest_coverage


def calculate_interest_coverage(
    operating_profit,
    *args,
    depreciation=None,
    other_income=None,
    interest=None,
):
    """Calculate ICR while accepting the legacy depreciation argument."""

    if args:

        if len(args) == 2:
            other_income = args[0]
            interest = args[1]

        elif len(args) == 3:
            depreciation = args[0]
            other_income = args[1]
            interest = args[2]

        else:
            raise TypeError(
                "calculate_interest_coverage accepts "
                "operating_profit, other_income, interest "
                "or the legacy depreciation argument."
            )

    # depreciation is intentionally ignored.
    # Sprint 2 formula:
    # (operating_profit + other_income) / interest

    return _portal_calculate_interest_coverage(
        operating_profit,
        other_income,
        interest,
    )

