"""Multi-year financial trend analysis screen."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
)


st.title("Trend Analysis")
st.caption(
    "Compare up to three financial KPIs across the latest "
    "10 annual periods for any Nifty 100 company."
)


# ------------------------------------------------------------
# Metric configuration
# ------------------------------------------------------------

METRICS = {
    "ROE (%)": "return_on_equity_pct",
    "ROCE (%)": "return_on_capital_employed_pct",
    "Net Profit Margin (%)": "net_profit_margin_pct",
    "Operating Profit Margin (%)": "operating_profit_margin_pct",
    "Debt / Equity": "debt_to_equity",
    "Interest Coverage": "interest_coverage",
    "Revenue CAGR 5Y (%)": "revenue_cagr_5yr",
    "PAT CAGR 5Y (%)": "pat_cagr_5yr",
    "EPS CAGR 5Y (%)": "eps_cagr_5yr",
    "FCF Conversion (%)": "fcf_conversion_pct",
}


# ------------------------------------------------------------
# Company selector
# ------------------------------------------------------------

companies = get_companies().copy()

companies["search_label"] = (
    companies["company_id"].astype(str)
    + " — "
    + companies["company_name"].astype(str)
)

search = st.text_input(
    "Search company",
    placeholder="Example: TCS, Reliance, HDFC Bank...",
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
    st.warning(
        "Ticker not found — please try another company."
    )
    st.stop()


selected_label = st.selectbox(
    "Company",
    filtered["search_label"].tolist(),
)

ticker = selected_label.split(" — ", 1)[0]


# ------------------------------------------------------------
# Metric selector
# ------------------------------------------------------------

selected_labels = st.multiselect(
    "Select metrics",
    options=list(METRICS.keys()),
    default=[
        "ROE (%)",
        "ROCE (%)",
    ],
    max_selections=3,
)

if not selected_labels:
    st.info(
        "Select at least one metric to display the trend."
    )
    st.stop()


# ------------------------------------------------------------
# Ratio history
# ------------------------------------------------------------

ratios = get_ratios(ticker).copy()

if ratios.empty:
    st.warning(
        "No ratio history is available for this company."
    )
    st.stop()


ratios["year"] = ratios["year"].astype(str)

annual = ratios[
    ratios["year"].str.upper() != "TTM"
].copy()

annual = (
    annual
    .sort_values("year")
    .tail(10)
    .reset_index(drop=True)
)


if annual.empty:
    st.warning(
        "No annual financial history is available."
    )
    st.stop()


st.caption(
    f"Showing {len(annual)} annual periods for {ticker}"
)


# ------------------------------------------------------------
# Trend chart with YoY annotations
# ------------------------------------------------------------

fig = go.Figure()

export_columns = ["year"]

for label in selected_labels:

    metric = METRICS[label]

    values = pd.to_numeric(
        annual[metric],
        errors="coerce",
    )

    yoy = values.pct_change(
        fill_method=None
    ) * 100

    annotation_text = []

    for i, value in enumerate(values):

        if pd.isna(value):
            annotation_text.append("N/A")
            continue

        if i == 0 or pd.isna(yoy.iloc[i]):
            annotation_text.append("")
            continue

        annotation_text.append(
            f"{yoy.iloc[i]:+.1f}%"
        )

    fig.add_trace(
        go.Scatter(
            x=annual["year"],
            y=values,
            mode="lines+markers+text",
            name=label,
            text=annotation_text,
            textposition="top center",
            connectgaps=False,
            hovertemplate=(
                "<b>%{x}</b><br>"
                + label
                + ": %{y:.2f}<extra></extra>"
            ),
        )
    )

    export_columns.append(metric)


fig.update_layout(
    xaxis_title="Financial Year",
    yaxis_title="Metric Value",
    hovermode="x unified",
    legend_title_text="Metric",
    margin=dict(
        l=20,
        r=20,
        t=30,
        b=20,
    ),
)

fig.update_xaxes(
    type="category"
)

st.plotly_chart(
    fig,
    width="stretch",
)

st.caption(
    "Labels beside data points show year-over-year percentage "
    "change. N/A values are left unconnected."
)


# ------------------------------------------------------------
# Latest KPI summary
# ------------------------------------------------------------

st.subheader("Latest Available Values")

latest = annual.iloc[-1]

cols = st.columns(
    len(selected_labels)
)

for col, label in zip(
    cols,
    selected_labels,
):

    metric = METRICS[label]

    value = pd.to_numeric(
        pd.Series([latest[metric]]),
        errors="coerce",
    ).iloc[0]

    with col:

        if pd.isna(value):
            display = "N/A"
        else:
            display = f"{value:.2f}"

        st.metric(
            label,
            display,
        )


# ------------------------------------------------------------
# Data table
# ------------------------------------------------------------

st.divider()
st.subheader("Trend Data")

display = annual[
    [
        "year",
        *[
            METRICS[label]
            for label in selected_labels
        ],
    ]
].copy()


display = display.rename(
    columns={
        "year": "Financial Year",
        **{
            METRICS[label]: label
            for label in selected_labels
        },
    }
)

numeric = display.select_dtypes(
    include="number"
).columns

display[numeric] = display[
    numeric
].round(2)

st.dataframe(
    display,
    hide_index=True,
    width="stretch",
)


# ------------------------------------------------------------
# CSV export
# ------------------------------------------------------------

csv = display.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "Download Trend CSV",
    data=csv,
    file_name=f"{ticker}_trend_analysis.csv",
    mime="text/csv",
    width="stretch",
)


st.caption(
    "Source: financial_ratios | Annual data only; TTM excluded."
)
