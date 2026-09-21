"""Home dashboard for the Nifty 100 Financial Intelligence Platform."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_home_snapshot


st.title("Nifty 100 Financial Intelligence")
st.caption(
    "Portfolio-level fundamentals, valuation, growth and sector intelligence."
)

year = st.sidebar.selectbox(
    "Financial Year",
    options=list(range(2024, 2018, -1)),
    index=0,
)

df = get_home_snapshot(year)

if df.empty:
    st.error("No data is available for the selected year.")
    st.stop()


# ------------------------------------------------------------
# Summary KPIs
# ------------------------------------------------------------

avg_roe = df["return_on_equity_pct"].mean()
median_pe = df["pe_ratio"].median()
median_de = df["debt_to_equity"].median()
median_rev_cagr = df["revenue_cagr_5yr"].median()
debt_free = int((df["total_debt_cr"] == 0).sum())
total_companies = int(df["company_id"].nunique())

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric(
    "Average ROE",
    f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A",
)

k2.metric(
    "Median P/E",
    f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A",
)

k3.metric(
    "Median D/E",
    f"{median_de:.2f}" if pd.notna(median_de) else "N/A",
)

k4.metric(
    "Total Companies",
    f"{total_companies}",
)

k5.metric(
    "Median Revenue CAGR 5Y",
    f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A",
)

k6.metric(
    "Debt-Free Companies",
    f"{debt_free}",
)


st.divider()


# ------------------------------------------------------------
# Sector distribution
# ------------------------------------------------------------

left, right = st.columns([1, 1.25])

with left:
    st.subheader("Sector Breakdown")

    sector_counts = (
        df.groupby("broad_sector", dropna=False)["company_id"]
        .nunique()
        .reset_index(name="company_count")
    )

    sector_counts["broad_sector"] = sector_counts[
        "broad_sector"
    ].fillna("Unclassified")

    fig = px.pie(
        sector_counts,
        names="broad_sector",
        values="company_count",
        hole=0.55,
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        legend_title_text="Sector",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    sector_total = sector_counts["broad_sector"].nunique()

    st.caption(
        f"{sector_total} populated broad-sector classifications "
        f"across {total_companies} companies."
    )


# ------------------------------------------------------------
# Dynamic 50 / 30 / 20 ranking
# ------------------------------------------------------------

with right:
    st.subheader("Top 5 Companies by Composite Score")

    score_df = df.copy()

    higher_better = [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "net_profit_margin_pct",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "dividend_yield_pct",
    ]

    lower_better = [
        "pe_ratio",
        "pb_ratio",
    ]

    for col in higher_better:
        score_df[f"{col}_score"] = (
            score_df.groupby("broad_sector")[col]
            .rank(method="average", pct=True, ascending=True)
            .fillna(0.50)
        )

    for col in lower_better:
        score_df[f"{col}_score"] = (
            score_df.groupby("broad_sector")[col]
            .rank(method="average", pct=True, ascending=False)
            .fillna(0.50)
        )

    score_df["profitability_score"] = score_df[
        [
            "return_on_equity_pct_score",
            "return_on_capital_employed_pct_score",
            "net_profit_margin_pct_score",
        ]
    ].mean(axis=1)

    score_df["growth_score"] = score_df[
        [
            "revenue_cagr_5yr_score",
            "pat_cagr_5yr_score",
            "eps_cagr_5yr_score",
        ]
    ].mean(axis=1)

    score_df["valuation_score"] = score_df[
        [
            "pe_ratio_score",
            "pb_ratio_score",
            "dividend_yield_pct_score",
        ]
    ].mean(axis=1)

    score_df["composite_score"] = (
        score_df["profitability_score"] * 0.50
        + score_df["growth_score"] * 0.30
        + score_df["valuation_score"] * 0.20
    ) * 100

    top5 = (
        score_df.sort_values(
            ["composite_score", "company_id"],
            ascending=[False, True],
        )
        .head(5)
        [
            [
                "company_id",
                "company_name",
                "broad_sector",
                "composite_score",
            ]
        ]
        .copy()
    )

    top5["composite_score"] = top5["composite_score"].round(2)

    top5.columns = [
        "Ticker",
        "Company",
        "Sector",
        "Composite Score",
    ]

    top5["Company"] = top5["Company"].apply(
        lambda name: name if len(str(name)) <= 36
        else str(name)[:33] + "..."
    )

    st.dataframe(
        top5,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn(
                "Ticker",
                width="small",
            ),
            "Company": st.column_config.TextColumn(
                "Company",
                width="medium",
            ),
            "Sector": st.column_config.TextColumn(
                "Sector",
                width="medium",
            ),
            "Composite Score": st.column_config.NumberColumn(
                "Composite Score",
                format="%.2f",
                width="small",
            ),
        },
    )

    st.caption(
        "Composite Score = 50% Profitability + "
        "30% Growth + 20% Valuation, normalised within sector."
    )


st.divider()

st.caption(
    f"Dashboard year: {year} | "
    "Source: N100 Financial Intelligence SQLite database"
)

