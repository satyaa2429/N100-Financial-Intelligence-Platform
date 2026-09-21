"""Company Profile screen for the Nifty 100 dashboard."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
    get_pl,
    get_pros_cons,
)


st.title("Company Profile")
st.caption(
    "Search any Nifty 100 company to explore fundamentals, "
    "financial trends and business observations."
)


# ------------------------------------------------------------
# Company search
# ------------------------------------------------------------

companies = get_companies().copy()

companies["search_label"] = (
    companies["company_id"].astype(str)
    + " — "
    + companies["company_name"].astype(str)
)

search = st.text_input(
    "Search by company name or ticker",
    placeholder="Example: TCS, HDFC Bank, Reliance...",
)

if search.strip():
    term = search.strip().lower()

    filtered = companies[
        companies["company_id"]
        .astype(str)
        .str.lower()
        .str.contains(term, na=False)
        |
        companies["company_name"]
        .astype(str)
        .str.lower()
        .str.contains(term, na=False)
    ].copy()
else:
    filtered = companies.copy()


if filtered.empty:
    st.warning("Ticker not found — please try another company.")
    st.stop()


selected_label = st.selectbox(
    "Select company",
    options=filtered["search_label"].tolist(),
)

ticker = selected_label.split(" — ", 1)[0]

company_rows = companies[
    companies["company_id"] == ticker
]

if company_rows.empty:
    st.warning("Ticker not found — please try another company.")
    st.stop()

company = company_rows.iloc[0]


# ------------------------------------------------------------
# Company information card
# ------------------------------------------------------------

st.subheader(f"{company['company_name']} ({ticker})")

info1, info2, info3 = st.columns(3)

info1.markdown(
    f"**Sector**  \n"
    f"{company['broad_sector'] if pd.notna(company['broad_sector']) else 'N/A'}"
)

info2.markdown(
    f"**Sub-sector**  \n"
    f"{company['sub_sector'] if pd.notna(company['sub_sector']) else 'N/A'}"
)

info3.markdown(
    f"**NSE Ticker**  \n{ticker}"
)

about = company["about_company"]

if pd.notna(about) and str(about).strip():
    st.markdown("**About Company**")
    st.write(str(about))
else:
    st.info("Company description is not available.")


# ------------------------------------------------------------
# Latest annual KPI row
# ------------------------------------------------------------

ratio_history = get_ratios(ticker).copy()

if not ratio_history.empty:
    ratio_history["year"] = ratio_history["year"].astype(str)

    annual_ratios = ratio_history[
        ratio_history["year"].str.upper() != "TTM"
    ].copy()

    annual_ratios = annual_ratios.sort_values(
        "year",
        ascending=False,
    )
else:
    annual_ratios = pd.DataFrame()


if annual_ratios.empty:
    st.warning(
        "Financial ratio data is not available for this company."
    )
else:
    latest = annual_ratios.iloc[0]
    latest_year = latest["year"]

    st.caption(f"Latest available financial year: {latest_year}")

    def pct(value):
        """Format a numeric value as a percentage for display."""
        if pd.isna(value):
            return "N/A"
        return f"{value:.1f}%"

    def number(value):
        """Format a numeric value for dashboard display."""
        if pd.isna(value):
            return "N/A"
        return f"{value:.2f}"

    def crore(value):
        """Format a monetary value in Indian rupees crore."""
        if pd.isna(value):
            return "N/A"
        return f"₹{value:,.0f} Cr"

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    k1.metric(
        "ROE",
        pct(latest["return_on_equity_pct"]),
    )

    k2.metric(
        "ROCE",
        pct(latest["return_on_capital_employed_pct"]),
    )

    k3.metric(
        "Net Profit Margin",
        pct(latest["net_profit_margin_pct"]),
    )

    k4.metric(
        "Debt / Equity",
        number(latest["debt_to_equity"]),
    )

    k5.metric(
        "Revenue CAGR 5Y",
        pct(latest["revenue_cagr_5yr"]),
    )

    k6.metric(
        "Free Cash Flow",
        crore(latest["free_cash_flow_cr"]),
    )


st.divider()


# ------------------------------------------------------------
# 10-year Revenue and Net Profit chart
# ------------------------------------------------------------

pl = get_pl(ticker).copy()

if not pl.empty:
    pl["year"] = pl["year"].astype(str)

    annual_pl = pl[
        pl["year"].str.upper() != "TTM"
    ].copy()

    annual_pl = (
        annual_pl
        .sort_values("year")
        .tail(10)
    )

    st.subheader("10-Year Revenue & Net Profit")

    if not annual_pl.empty:
        revenue_fig = go.Figure()

        revenue_fig.add_trace(
            go.Bar(
                x=annual_pl["year"],
                y=annual_pl["sales"],
                name="Revenue",
            )
        )

        revenue_fig.add_trace(
            go.Bar(
                x=annual_pl["year"],
                y=annual_pl["net_profit"],
                name="Net Profit",
            )
        )

        revenue_fig.update_layout(
            barmode="group",
            xaxis_title="Financial Year",
            yaxis_title="₹ Crore",
            margin=dict(l=20, r=20, t=30, b=20),
            legend_title_text="Metric",
        )

        st.plotly_chart(
            revenue_fig,
            use_container_width=True,
        )
    else:
        st.info("Revenue and profit history is not available.")
else:
    st.info("Profit and loss history is not available.")


# ------------------------------------------------------------
# 10-year ROE and ROCE dual-axis chart
# ------------------------------------------------------------

if not annual_ratios.empty:
    trend_ratios = (
        annual_ratios
        .sort_values("year")
        .tail(10)
    )

    st.subheader("10-Year ROE & ROCE Trend")

    trend_fig = make_subplots(
        specs=[[{"secondary_y": True}]]
    )

    trend_fig.add_trace(
        go.Scatter(
            x=trend_ratios["year"],
            y=trend_ratios["return_on_equity_pct"],
            mode="lines+markers",
            name="ROE",
        ),
        secondary_y=False,
    )

    trend_fig.add_trace(
        go.Scatter(
            x=trend_ratios["year"],
            y=trend_ratios["return_on_capital_employed_pct"],
            mode="lines+markers",
            name="ROCE",
        ),
        secondary_y=True,
    )

    trend_fig.update_xaxes(
        title_text="Financial Year"
    )

    trend_fig.update_yaxes(
        title_text="ROE (%)",
        secondary_y=False,
    )

    trend_fig.update_yaxes(
        title_text="ROCE (%)",
        secondary_y=True,
    )

    trend_fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
    )

    st.plotly_chart(
        trend_fig,
        use_container_width=True,
    )


st.divider()


# ------------------------------------------------------------
# Pros and Cons
# ------------------------------------------------------------

st.subheader("Pros & Cons")

pros_cons = get_pros_cons(ticker)

if pros_cons.empty:
    st.info(
        "Pros and cons are not available for this company."
    )
else:
    pro_col, con_col = st.columns(2)

    with pro_col:
        st.markdown("### ✅ Pros")

        for item in pros_cons["pros"].dropna():
            if str(item).strip():
                st.success(str(item))

    with con_col:
        st.markdown("### ❌ Cons")

        for item in pros_cons["cons"].dropna():
            if str(item).strip():
                st.error(str(item))


st.divider()

st.caption(
    "Source: N100 Financial Intelligence SQLite database"
)
