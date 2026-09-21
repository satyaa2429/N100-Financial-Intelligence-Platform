"""Sector-level analysis for the Nifty 100 dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_sector_snapshot


st.title("Sector Analysis")
st.caption(
    "Explore company fundamentals and sector-level KPI "
    "benchmarks across the Nifty 100 universe."
)


# ------------------------------------------------------------
# Controls
# ------------------------------------------------------------

year = st.sidebar.selectbox(
    "Financial Year",
    options=list(range(2024, 2018, -1)),
    index=0,
)

data = get_sector_snapshot(year)

sectors = sorted(
    data["broad_sector"]
    .dropna()
    .unique()
    .tolist()
)

selected_sector = st.selectbox(
    "Sector",
    sectors,
)


sector_df = data[
    data["broad_sector"] == selected_sector
].copy()


if sector_df.empty:
    st.warning(
        "No companies are available for this sector."
    )
    st.stop()


# ------------------------------------------------------------
# Summary KPIs
# ------------------------------------------------------------

company_count = sector_df["company_id"].nunique()

median_roe = pd.to_numeric(
    sector_df["roe_pct"],
    errors="coerce",
).median()

median_revenue = pd.to_numeric(
    sector_df["revenue_cr"],
    errors="coerce",
).median()

median_market_cap = pd.to_numeric(
    sector_df["market_cap_crore"],
    errors="coerce",
).median()


k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "Companies",
    company_count,
)

k2.metric(
    "Median ROE",
    (
        f"{median_roe:.1f}%"
        if pd.notna(median_roe)
        else "N/A"
    ),
)

k3.metric(
    "Median Revenue",
    (
        f"₹{median_revenue:,.0f} Cr"
        if pd.notna(median_revenue)
        else "N/A"
    ),
)

k4.metric(
    "Median Market Cap",
    (
        f"₹{median_market_cap:,.0f} Cr"
        if pd.notna(median_market_cap)
        else "N/A"
    ),
)


st.divider()


# ------------------------------------------------------------
# Bubble chart
# X = Revenue
# Y = ROE
# Bubble = Market Cap
# Colour = Sub-sector
# ------------------------------------------------------------

st.subheader(
    f"{selected_sector}: Revenue vs ROE"
)

bubble_df = sector_df.copy()

bubble_df["revenue_cr"] = pd.to_numeric(
    bubble_df["revenue_cr"],
    errors="coerce",
)

bubble_df["roe_pct"] = pd.to_numeric(
    bubble_df["roe_pct"],
    errors="coerce",
)

bubble_df["market_cap_crore"] = pd.to_numeric(
    bubble_df["market_cap_crore"],
    errors="coerce",
)

bubble_df = bubble_df.dropna(
    subset=[
        "revenue_cr",
        "roe_pct",
        "market_cap_crore",
    ]
)


if bubble_df.empty:

    st.info(
        "Insufficient data is available to create "
        "the bubble chart for this selection."
    )

else:

    # Plotly bubble sizes require positive values.
    bubble_df = bubble_df[
        bubble_df["market_cap_crore"] > 0
    ].copy()

    fig = px.scatter(
        bubble_df,
        x="revenue_cr",
        y="roe_pct",
        size="market_cap_crore",
        color="sub_sector",
        hover_name="company_name",
        hover_data={
            "company_id": True,
            "revenue_cr": ":,.0f",
            "roe_pct": ":.2f",
            "market_cap_crore": ":,.0f",
            "sub_sector": True,
        },
        labels={
            "revenue_cr": "Revenue (₹ Cr)",
            "roe_pct": "ROE (%)",
            "market_cap_crore": "Market Cap (₹ Cr)",
            "sub_sector": "Sub-sector",
        },
        size_max=70,
    )

    fig.update_layout(
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20,
        ),
        legend_title_text="Sub-sector",
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )

    st.caption(
        "Bubble size represents market capitalisation."
    )


# ------------------------------------------------------------
# Sector median KPI chart
# ------------------------------------------------------------

st.divider()
st.subheader("Sector Median KPIs")

KPI_COLUMNS = {
    "ROE": "roe_pct",
    "ROCE": "roce_pct",
    "Net Profit Margin": "npm_pct",
    "Revenue CAGR 5Y": "revenue_cagr_5yr",
    "PAT CAGR 5Y": "pat_cagr_5yr",
}


median_rows = []

for label, column in KPI_COLUMNS.items():

    values = pd.to_numeric(
        sector_df[column],
        errors="coerce",
    )

    median_rows.append(
        {
            "Metric": label,
            "Median Value": values.median(),
        }
    )


median_df = pd.DataFrame(
    median_rows
).dropna(
    subset=["Median Value"]
)


if median_df.empty:

    st.info(
        "No median KPI data is available for this sector."
    )

else:

    median_fig = px.bar(
        median_df,
        x="Metric",
        y="Median Value",
        text_auto=".1f",
        labels={
            "Median Value": "Median (%)",
        },
    )

    median_fig.update_layout(
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        median_fig,
        width="stretch",
    )


# ------------------------------------------------------------
# Company table
# ------------------------------------------------------------

st.divider()
st.subheader("Companies in Selected Sector")

table = sector_df[
    [
        "company_id",
        "company_name",
        "sub_sector",
        "revenue_cr",
        "roe_pct",
        "roce_pct",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "debt_to_equity",
        "market_cap_crore",
        "pe_ratio",
    ]
].copy()


table = table.rename(
    columns={
        "company_id": "Ticker",
        "company_name": "Company",
        "sub_sector": "Sub-sector",
        "revenue_cr": "Revenue ₹ Cr",
        "roe_pct": "ROE %",
        "roce_pct": "ROCE %",
        "revenue_cagr_5yr": "Revenue CAGR 5Y %",
        "pat_cagr_5yr": "PAT CAGR 5Y %",
        "debt_to_equity": "D/E",
        "market_cap_crore": "Market Cap ₹ Cr",
        "pe_ratio": "P/E",
    }
)


numeric_columns = table.select_dtypes(
    include="number"
).columns

table[numeric_columns] = table[
    numeric_columns
].round(2)


st.dataframe(
    table,
    hide_index=True,
    width="stretch",
)


st.caption(
    f"Financial year: {year} | "
    f"Actual populated broad sectors in database: {len(sectors)}"
)
