"""Interactive peer-group comparison dashboard."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.peer import load_peer_data, percent_rank
from src.dashboard.utils.db import get_companies


st.title("Peer Comparison")
st.caption(
    "Compare companies against their official peer group "
    "using financial metrics, percentiles and radar analysis."
)


@st.cache_data(ttl=600, show_spinner=False)
def load_dashboard_peer_data() -> pd.DataFrame:
    """Load peer data together with company names."""
    peers = load_peer_data()

    companies = get_companies()[
        ["company_id", "company_name"]
    ].copy()

    return peers.merge(
        companies,
        on="company_id",
        how="left",
    )


peer_data = load_dashboard_peer_data()


# ------------------------------------------------------------
# Official 8 radar axes
# ------------------------------------------------------------

RADAR_METRICS = {
    "ROE": "return_on_equity_pct",
    "ROCE": "return_on_capital_employed_pct",
    "Net Profit Margin": "net_profit_margin_pct",
    "Debt / Equity": "debt_to_equity",
    "Free Cash Flow": "free_cash_flow_cr",
    "PAT CAGR 5Y": "pat_cagr_5yr",
    "Revenue CAGR 5Y": "revenue_cagr_5yr",
    "EPS CAGR 5Y": "eps_cagr_5yr",
}

LOWER_IS_BETTER = {
    "debt_to_equity",
}


# ------------------------------------------------------------
# Peer group selector
# ------------------------------------------------------------

groups = sorted(
    peer_data["peer_group_name"]
    .dropna()
    .unique()
    .tolist()
)

selected_group = st.selectbox(
    "Peer Group",
    groups,
)

group_df = peer_data[
    peer_data["peer_group_name"] == selected_group
].copy()

group_df = group_df.sort_values(
    ["is_benchmark", "company_id"],
    ascending=[False, True],
)


# ------------------------------------------------------------
# Company selector
# ------------------------------------------------------------

group_df["company_label"] = (
    group_df["company_id"]
    + " — "
    + group_df["company_name"].fillna("")
)

selected_label = st.selectbox(
    "Company",
    group_df["company_label"].tolist(),
)

ticker = selected_label.split(" — ", 1)[0]

selected_company = group_df[
    group_df["company_id"] == ticker
].iloc[0]


benchmark_rows = group_df[
    group_df["is_benchmark"] == 1
]

benchmark_ticker = (
    benchmark_rows.iloc[0]["company_id"]
    if not benchmark_rows.empty
    else "N/A"
)


# ------------------------------------------------------------
# Group summary
# ------------------------------------------------------------

c1, c2, c3 = st.columns(3)

c1.metric(
    "Peer Group",
    selected_group,
)

c2.metric(
    "Companies",
    len(group_df),
)

c3.metric(
    "Benchmark",
    benchmark_ticker,
)


st.divider()


# ------------------------------------------------------------
# Metric selector
# ------------------------------------------------------------

selected_labels = st.multiselect(
    "Radar Metrics",
    options=list(RADAR_METRICS.keys()),
    default=list(RADAR_METRICS.keys()),
    max_selections=8,
)

if len(selected_labels) < 3:
    st.warning(
        "Select at least 3 metrics to display the radar chart."
    )
    st.stop()


selected_metrics = [
    RADAR_METRICS[label]
    for label in selected_labels
]


# ------------------------------------------------------------
# Radar normalisation
# P10-P90 within the selected official peer group
# ------------------------------------------------------------

def normalise_value(
    series: pd.Series,
    value: float,
    metric: str,
) -> float:
    """Normalise a metric to 0-100 using peer P10-P90."""

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if pd.isna(value) or numeric.empty:
        return np.nan

    p10 = numeric.quantile(0.10)
    p90 = numeric.quantile(0.90)

    if pd.isna(p10) or pd.isna(p90):
        return np.nan

    if p90 == p10:
        score = 50.0
    else:
        score = (
            (float(value) - float(p10))
            / (float(p90) - float(p10))
            * 100
        )

    score = float(np.clip(score, 0, 100))

    if metric in LOWER_IS_BETTER:
        score = 100 - score

    return score


company_scores = []
peer_scores = []

for label in selected_labels:

    metric = RADAR_METRICS[label]

    metric_series = pd.to_numeric(
        group_df[metric],
        errors="coerce",
    )

    company_value = pd.to_numeric(
        pd.Series([selected_company[metric]]),
        errors="coerce",
    ).iloc[0]

    peer_average = metric_series.mean()

    company_scores.append(
        normalise_value(
            metric_series,
            company_value,
            metric,
        )
    )

    peer_scores.append(
        normalise_value(
            metric_series,
            peer_average,
            metric,
        )
    )


# ------------------------------------------------------------
# Interactive radar
# ------------------------------------------------------------

radar_labels = selected_labels + [selected_labels[0]]

company_plot = company_scores + [company_scores[0]]
peer_plot = peer_scores + [peer_scores[0]]

fig = go.Figure()

fig.add_trace(
    go.Scatterpolar(
        r=company_plot,
        theta=radar_labels,
        fill="toself",
        name=ticker,
    )
)

fig.add_trace(
    go.Scatterpolar(
        r=peer_plot,
        theta=radar_labels,
        fill="toself",
        name="Peer Average",
    )
)

fig.update_layout(
    polar={
        "radialaxis": {
            "visible": True,
            "range": [0, 100],
        }
    },
    showlegend=True,
    margin=dict(
        l=40,
        r=40,
        t=40,
        b=40,
    ),
)

st.subheader(
    f"{ticker} vs {selected_group} Average"
)

st.plotly_chart(
    fig,
    use_container_width=True,
)

st.caption(
    "Radar values are normalised within the selected peer "
    "group using P10-P90 scaling. Lower D/E is scored higher."
)


# ------------------------------------------------------------
# Detailed peer table
# ------------------------------------------------------------

st.divider()
st.subheader("Peer Metric Comparison")

table = group_df[
    [
        "company_id",
        "company_name",
        "is_benchmark",
        *selected_metrics,
    ]
].copy()


for metric in selected_metrics:

    table[f"{metric}_percentile"] = (
        percent_rank(
            pd.to_numeric(
                table[metric],
                errors="coerce",
            )
        )
        * 100
    )


rename_map = {
    "company_id": "Ticker",
    "company_name": "Company",
    "is_benchmark": "Benchmark",
}

for label, metric in RADAR_METRICS.items():

    rename_map[metric] = label
    rename_map[f"{metric}_percentile"] = (
        f"{label} Percentile"
    )


table = table.rename(
    columns=rename_map
)

table["Benchmark"] = table["Benchmark"].map(
    {
        1: "Yes",
        0: "No",
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
    use_container_width=True,
    height=430,
)


# ------------------------------------------------------------
# Selected company detail
# ------------------------------------------------------------

st.subheader(f"{ticker} Metric Detail")

detail_rows = []

for label in selected_labels:

    metric = RADAR_METRICS[label]

    value = pd.to_numeric(
        pd.Series([selected_company[metric]]),
        errors="coerce",
    ).iloc[0]

    peer_avg = pd.to_numeric(
        group_df[metric],
        errors="coerce",
    ).mean()

    percentile_series = percent_rank(
        pd.to_numeric(
            group_df[metric],
            errors="coerce",
        )
    )

    selected_index = group_df.index[
        group_df["company_id"] == ticker
    ][0]

    percentile = percentile_series.loc[
        selected_index
    ]

    detail_rows.append(
        {
            "Metric": label,
            "Company Value": value,
            "Peer Average": peer_avg,
            "Raw Peer Percentile": (
                percentile * 100
                if pd.notna(percentile)
                else np.nan
            ),
        }
    )


detail = pd.DataFrame(
    detail_rows
).round(2)

st.dataframe(
    detail,
    hide_index=True,
    use_container_width=True,
)


# ------------------------------------------------------------
# Excel export
# ------------------------------------------------------------

excel_buffer = BytesIO()

with pd.ExcelWriter(
    excel_buffer,
    engine="openpyxl",
) as writer:

    table.to_excel(
        writer,
        sheet_name="Peer Comparison",
        index=False,
    )

    detail.to_excel(
        writer,
        sheet_name="Selected Company",
        index=False,
    )


st.download_button(
    "Download Peer Comparison Excel",
    data=excel_buffer.getvalue(),
    file_name=(
        selected_group
        .replace(" ", "_")
        .replace("/", "_")
        + "_peer_comparison.xlsx"
    ),
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    use_container_width=True,
)


# ------------------------------------------------------------
# Official Sprint 3 PNG download
# ------------------------------------------------------------

safe_ticker = re.sub(
    r"[^A-Za-z0-9._-]+",
    "_",
    ticker,
)

png_path = (
    Path("reports")
    / "radar_charts"
    / f"{safe_ticker}.png"
)

if png_path.exists():

    st.image(
        str(png_path),
        caption=(
            f"Official Sprint 3 8-axis radar chart — {ticker}"
        ),
        use_container_width=True,
    )

    st.download_button(
        "Download Official Radar PNG",
        data=png_path.read_bytes(),
        file_name=f"{safe_ticker}_radar.png",
        mime="image/png",
        use_container_width=True,
    )

else:

    st.info(
        "Pre-generated radar PNG is not available "
        "for this company."
    )


st.caption(
    "Peer memberships use the official peer_groups dataset. "
    "Percentile ranks follow the Sprint 3 PERCENT_RANK logic."
)
