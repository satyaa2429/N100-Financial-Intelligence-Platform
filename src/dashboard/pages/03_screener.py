"""Interactive Nifty 100 financial screener."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.analytics.peer import RATIO_YEAR
from src.dashboard.utils.db import get_turnaround_companies
from src.dashboard.utils.api_client import get_health as get_api_health, get_screener as get_api_screener
from src.screener.engine import ScreenerEngine
from src.screener.ranking import build_ranking


st.title("Financial Screener")
st.caption(
    "Filter the Nifty 100 universe using financial quality, "
    "growth, valuation and leverage metrics."
)

# ------------------------------------------------------------
# FastAPI integration status
# ------------------------------------------------------------

try:
    api_health = get_api_health()

    api_preview = get_api_screener(
        min_roe=10,
        max_de=2,
    )

    if api_health.get("status") == "healthy":
        st.sidebar.success(
            "FastAPI connected "
            f"? {len(api_preview)} "
            "screened companies"
        )
    else:
        st.sidebar.warning(
            "FastAPI health check "
            "did not return healthy."
        )

except Exception as exc:
    st.sidebar.warning(
        "FastAPI unavailable. "
        f"Local dashboard remains active. "
        f"Details: {exc}"
    )


@st.cache_data(ttl=600, show_spinner=False)
def load_screener_universe() -> pd.DataFrame:
    """Load the aligned financial screener universe."""
    return ScreenerEngine().load_universe()


@st.cache_data(ttl=600, show_spinner=False)
def load_composite_ranking() -> pd.DataFrame:
    """Load sector-normalised composite ranking."""
    return build_ranking()


universe = load_screener_universe()
ranking = load_composite_ranking()

engine = ScreenerEngine()


# ------------------------------------------------------------
# Slider definitions
# ------------------------------------------------------------

SLIDERS = {
    "roe": {
        "label": "ROE minimum (%)",
        "operator": "min",
    },
    "debt_to_equity": {
        "label": "Debt / Equity maximum",
        "operator": "max",
    },
    "free_cash_flow": {
        "label": "Free Cash Flow minimum (₹ Cr)",
        "operator": "min",
    },
    "revenue_cagr_5yr": {
        "label": "Revenue CAGR 5Y minimum (%)",
        "operator": "min",
    },
    "pat_cagr_5yr": {
        "label": "PAT CAGR 5Y minimum (%)",
        "operator": "min",
    },
    "operating_profit_margin": {
        "label": "Operating Profit Margin minimum (%)",
        "operator": "min",
    },
    "pe_ratio": {
        "label": "P/E maximum",
        "operator": "max",
    },
    "pb_ratio": {
        "label": "P/B maximum",
        "operator": "max",
    },
    "dividend_yield": {
        "label": "Dividend Yield minimum (%)",
        "operator": "min",
    },
    "interest_coverage": {
        "label": "Interest Coverage minimum",
        "operator": "min",
    },
}


def metric_bounds(metric: str) -> tuple[float, float]:
    """Return safe slider bounds using observed data."""
    values = pd.to_numeric(
        universe[metric],
        errors="coerce",
    ).dropna()

    if values.empty:
        return 0.0, 1.0

    low = float(math.floor(values.min()))
    high = float(math.ceil(values.max()))

    if low == high:
        high = low + 1.0

    return low, high


BOUNDS = {
    metric: metric_bounds(metric)
    for metric in SLIDERS
}


def reset_filters() -> None:
    """Reset all sliders to non-restrictive boundaries."""
    for metric, details in SLIDERS.items():
        low, high = BOUNDS[metric]

        if details["operator"] == "min":
            st.session_state[f"filter_{metric}"] = low
        else:
            st.session_state[f"filter_{metric}"] = high


if "active_preset" not in st.session_state:
    st.session_state.active_preset = None


for metric, details in SLIDERS.items():

    key = f"filter_{metric}"

    if key not in st.session_state:

        low, high = BOUNDS[metric]

        if details["operator"] == "min":
            st.session_state[key] = low
        else:
            st.session_state[key] = high


# ------------------------------------------------------------
# Presets
# ------------------------------------------------------------

st.sidebar.subheader("Preset Screens")

p1, p2 = st.sidebar.columns(2)

with p1:

    if st.button(
        "Quality",
        use_container_width=True,
    ):
        reset_filters()

        st.session_state.filter_roe = 15.0
        st.session_state.filter_debt_to_equity = 1.0
        st.session_state.filter_free_cash_flow = 0.0

        st.session_state.active_preset = "quality"
        st.rerun()

    if st.button(
        "Growth",
        use_container_width=True,
    ):
        reset_filters()

        st.session_state.filter_pat_cagr_5yr = 20.0

        st.session_state.active_preset = "growth"
        st.rerun()

    if st.button(
        "Debt-Free",
        use_container_width=True,
    ):
        reset_filters()

        st.session_state.filter_debt_to_equity = 0.0

        st.session_state.active_preset = "debt_free"
        st.rerun()


with p2:

    if st.button(
        "Value",
        use_container_width=True,
    ):
        reset_filters()

        st.session_state.filter_pe_ratio = 20.0
        st.session_state.filter_pb_ratio = 3.0

        st.session_state.active_preset = "value"
        st.rerun()

    if st.button(
        "Dividend",
        use_container_width=True,
    ):
        reset_filters()

        st.session_state.filter_dividend_yield = 2.0

        st.session_state.active_preset = "dividend"
        st.rerun()

    if st.button(
        "Momentum",
        use_container_width=True,
    ):
        reset_filters()

        # Official Momentum preset: Revenue CAGR 5Y > 15%
        st.session_state.filter_revenue_cagr_5yr = 15.0

        st.session_state.active_preset = "momentum"
        st.rerun()


if st.sidebar.button(
    "Reset Filters",
    use_container_width=True,
):
    reset_filters()
    st.session_state.active_preset = None
    st.rerun()


if st.session_state.active_preset:
    st.sidebar.info(
        f"Active preset: "
        f"{st.session_state.active_preset.replace('_', ' ').title()}"
    )


# ------------------------------------------------------------
# Metric sliders
# ------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Financial Filters")

filter_values = {}

for metric, details in SLIDERS.items():

    low, high = BOUNDS[metric]

    spread = high - low

    if spread <= 10:
        step = 0.1
    elif spread <= 100:
        step = 1.0
    elif spread <= 1000:
        step = 5.0
    else:
        step = max(
            10.0,
            round(spread / 200, 0),
        )

    value = st.sidebar.slider(
        details["label"],
        min_value=float(low),
        max_value=float(high),
        value=float(
            st.session_state[f"filter_{metric}"]
        ),
        step=float(step),
        key=f"filter_{metric}",
    )

    filter_values[metric] = value


# ------------------------------------------------------------
# Determine active custom filters
# ------------------------------------------------------------

active_filters = {}

for metric, details in SLIDERS.items():

    value = filter_values[metric]
    low, high = BOUNDS[metric]

    if details["operator"] == "min":

        if value > low:
            active_filters[metric] = value

    else:

        if value < high:
            active_filters[metric] = value


# ------------------------------------------------------------
# Run screen
# ------------------------------------------------------------

results = engine.screen(active_filters)


# Existing Sprint 3 preset logic remains authoritative
# for the five presets already implemented.

preset = st.session_state.active_preset

if preset in {
    "quality",
    "value",
    "growth",
    "dividend",
    "debt_free",
}:

    preset_ids = set(
        engine.run_preset(preset)["company_id"]
    )

    results = results[
        results["company_id"].isin(preset_ids)
    ].copy()


# Official Turnaround Watch:
# Revenue CAGR 3yr > 10%
# latest FCF > 0
# D/E declining vs previous annual year.

elif preset == "turnaround":

    turnaround = get_turnaround_companies()

    turnaround_ids = set(
        turnaround["company_id"]
    )

    results = results[
        results["company_id"].isin(turnaround_ids)
    ].copy()


# ------------------------------------------------------------
# Add sector + composite ranking
# ------------------------------------------------------------

rank_cols = ranking[
    [
        "company_id",
        "broad_sector",
        "composite_score",
        "overall_rank",
    ]
].copy()

results = results.merge(
    rank_cols,
    on="company_id",
    how="left",
)

results = results.sort_values(
    [
        "composite_score",
        "company_id",
    ],
    ascending=[
        False,
        True,
    ],
)


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

st.subheader("Screening Results")

count = len(results)

st.markdown(
    f"### {count} "
    f"{'company matches' if count == 1 else 'companies match'} "
    f"your filters"
)

if preset == "turnaround":

    st.info(
        "Turnaround Watch additionally applies improving positive FCF, "
        "Revenue CAGR 3Y > 10% and declining D/E "
        "versus the previous annual year."
    )


display_columns = [
    "company_id",
    "company_name",
    "broad_sector",
    "composite_score",
    "roe",
    "debt_to_equity",
    "free_cash_flow",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "operating_profit_margin",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "interest_coverage",
]


display = results[
    [
        col
        for col in display_columns
        if col in results.columns
    ]
].copy()


display = display.rename(
    columns={
        "company_id": "Ticker",
        "company_name": "Company",
        "broad_sector": "Sector",
        "composite_score": "Composite Score",
        "roe": "ROE %",
        "debt_to_equity": "D/E",
        "free_cash_flow": "FCF ₹ Cr",
        "revenue_cagr_5yr": "Revenue CAGR 5Y %",
        "pat_cagr_5yr": "PAT CAGR 5Y %",
        "operating_profit_margin": "OPM %",
        "pe_ratio": "P/E",
        "pb_ratio": "P/B",
        "dividend_yield": "Dividend Yield %",
        "interest_coverage": "ICR",
    }
)


numeric_columns = [
    col
    for col in display.columns
    if col not in {
        "Ticker",
        "Company",
        "Sector",
    }
]

for column in numeric_columns:
    display[column] = pd.to_numeric(
        display[column],
        errors="coerce",
    ).round(2)


st.dataframe(
    display.head(50),
    hide_index=True,
    use_container_width=True,
    height=520,
)


# ------------------------------------------------------------
# CSV export
# ------------------------------------------------------------

csv_data = display.to_csv(
    index=False,
).encode("utf-8")

st.download_button(
    label="Download Screener Results CSV",
    data=csv_data,
    file_name="nifty100_screener_results.csv",
    mime="text/csv",
    use_container_width=True,
)


st.caption(
    f"Financial ratios: {RATIO_YEAR} | "
    "Valuation data: 2024 | "
    "Maximum 50 rows displayed on screen; "
    "CSV contains all matching companies."
)

