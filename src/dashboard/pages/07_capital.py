from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies


# ---------------------------------------------------------
# Page header
# ---------------------------------------------------------
st.title("Capital Allocation")

st.caption(
    "Analyse how companies deploy operating cash across investment, "
    "financing and shareholder-return activities."
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
CAPITAL_PATH = Path("output/capital_allocation.csv")


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------
def normalise_bool(value):
    """Convert different boolean representations into True/False."""

    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
        "t",
    }


@st.cache_data(ttl=600, show_spinner=False)
def load_capital_allocation() -> pd.DataFrame:
    """Load capital-allocation output and attach company metadata."""

    if not CAPITAL_PATH.exists():
        return pd.DataFrame()

    capital = pd.read_csv(CAPITAL_PATH)

    # Clean company IDs
    capital["company_id"] = (
        capital["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Clean year
    capital["year"] = capital["year"].astype(str).str.strip()

    # Keep only annual-style YYYY-MM rows
    capital = capital[
        capital["year"].str.match(r"^\d{4}-\d{2}$", na=False)
    ].copy()

    # Load company metadata
    companies = get_companies().copy()

    if companies.empty:
        return capital

    # Detect company identifier column
    if "id" in companies.columns:
        companies = companies.rename(columns={"id": "company_id"})
    elif "ticker" in companies.columns:
        companies = companies.rename(columns={"ticker": "company_id"})

    companies["company_id"] = (
        companies["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Detect company name
    if "company_name" not in companies.columns:
        for candidate in ["name", "company"]:
            if candidate in companies.columns:
                companies = companies.rename(
                    columns={candidate: "company_name"}
                )
                break

    # Detect sector
    if "broad_sector" not in companies.columns:
        for candidate in ["sector", "broad_sector_name"]:
            if candidate in companies.columns:
                companies = companies.rename(
                    columns={candidate: "broad_sector"}
                )
                break

    # Select metadata columns that actually exist
    metadata_columns = [
        column
        for column in [
            "company_id",
            "company_name",
            "broad_sector",
            "sub_sector",
        ]
        if column in companies.columns
    ]

    companies = companies[metadata_columns].drop_duplicates(
        subset=["company_id"]
    )

    capital = capital.merge(
        companies,
        on="company_id",
        how="left",
    )

    # Friendly fallbacks
    if "company_name" not in capital.columns:
        capital["company_name"] = capital["company_id"]

    if "broad_sector" not in capital.columns:
        capital["broad_sector"] = "Unknown"

    if "sub_sector" not in capital.columns:
        capital["sub_sector"] = "Unknown"

    # Convert numeric columns
    numeric_columns = [
        "free_cash_flow_cr",
        "cfo_pat_ratio",
        "capex_intensity_pct",
        "fcf_conversion_pct",
        "operating_activity",
        "investing_activity",
    ]

    for column in numeric_columns:
        if column in capital.columns:
            capital[column] = pd.to_numeric(
                capital[column],
                errors="coerce",
            )

    # Normalise distress flag
    if "distress_flag" in capital.columns:
        capital["distress_flag_bool"] = capital[
            "distress_flag"
        ].apply(normalise_bool)
    else:
        capital["distress_flag_bool"] = False

    return capital


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------
data = load_capital_allocation()

if data.empty:
    st.error(
        "Capital allocation data is unavailable. "
        "Please generate output/capital_allocation.csv first."
    )
    st.stop()


# ---------------------------------------------------------
# Available financial years
# ---------------------------------------------------------
annual = data.copy()

years = sorted(
    annual["year"]
    .dropna()
    .astype(str)
    .unique()
    .tolist(),
    reverse=True,
)

if not years:
    st.warning("No valid financial years were found.")
    st.stop()


year_counts = (
    annual.groupby("year")["company_id"]
    .nunique()
    .sort_index(ascending=False)
)


# ---------------------------------------------------------
# Financial Year selector
# ---------------------------------------------------------
view_options = ["Latest Available"] + years

selected_year = st.sidebar.selectbox(
    "Financial Year",
    view_options,
    index=0,
)


# ---------------------------------------------------------
# Build selected dataset
# ---------------------------------------------------------
if selected_year == "Latest Available":

    # Sort so the latest available year for every company is last.
    # Example:
    # Most companies -> 2024-03
    # SIEMENS        -> 2024-09
    year_df = (
        annual.sort_values(
            ["company_id", "year"]
        )
        .drop_duplicates(
            subset=["company_id"],
            keep="last",
        )
        .copy()
    )

    selected_coverage = int(
        year_df["company_id"].nunique()
    )

else:

    selected_coverage = int(
        year_counts.get(selected_year, 0)
    )

    if selected_coverage < 80:
        st.sidebar.warning(
            f"{selected_year} has only "
            f"{selected_coverage} company records."
        )

    year_df = annual[
        annual["year"] == selected_year
    ].copy()


if year_df.empty:
    st.warning(
        "No capital-allocation records are available "
        "for the selected view."
    )
    st.stop()


# ---------------------------------------------------------
# Clean pattern labels
# ---------------------------------------------------------
year_df["pattern_label"] = (
    year_df["pattern_label"]
    .fillna("Unclassified")
    .astype(str)
    .str.strip()
)

year_df.loc[
    year_df["pattern_label"] == "",
    "pattern_label",
] = "Unclassified"


# ---------------------------------------------------------
# KPI calculations
# ---------------------------------------------------------
company_count = int(
    year_df["company_id"].nunique()
)

pattern_count = int(
    year_df["pattern_label"].nunique()
)

positive_fcf = int(
    (
        pd.to_numeric(
            year_df["free_cash_flow_cr"],
            errors="coerce",
        )
        > 0
    ).sum()
)

distress_count = int(
    year_df["distress_flag_bool"].sum()
)


# ---------------------------------------------------------
# KPI cards
# ---------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric(
        "Companies",
        company_count,
    )

with k2:
    st.metric(
        "Allocation Patterns",
        pattern_count,
    )

with k3:
    st.metric(
        "Positive FCF",
        positive_fcf,
    )

with k4:
    st.metric(
        "Distress Flags",
        distress_count,
    )


st.divider()


# ---------------------------------------------------------
# Capital Allocation Map
# ---------------------------------------------------------
st.subheader("Capital Allocation Map")

treemap_df = year_df.copy()

# Equal size for every company
treemap_df["_company_weight"] = 1

treemap_df["company_name"] = treemap_df[
    "company_name"
].fillna(
    treemap_df["company_id"]
)

treemap_df["broad_sector"] = treemap_df[
    "broad_sector"
].fillna("Unknown")


hover_data = {
    "_company_weight": False,
    "company_id": True,
    "company_name": True,
    "broad_sector": True,
}

if "free_cash_flow_cr" in treemap_df.columns:
    hover_data["free_cash_flow_cr"] = ":,.2f"

if "cfo_quality_label" in treemap_df.columns:
    hover_data["cfo_quality_label"] = True

if "capex_intensity_label" in treemap_df.columns:
    hover_data["capex_intensity_label"] = True


fig_treemap = px.treemap(
    treemap_df,
    path=[
        px.Constant("Nifty 100"),
        "pattern_label",
        "company_id",
    ],
    values="_company_weight",
    color="pattern_label",
    hover_data=hover_data,
)

fig_treemap.update_traces(
    root_color="white",
)

fig_treemap.update_layout(
    margin=dict(
        t=10,
        l=10,
        r=10,
        b=10,
    ),
    height=560,
)

st.plotly_chart(
    fig_treemap,
    width="stretch",
)

st.caption(
    "Each company has equal area. Companies are grouped by "
    "their actual capital-allocation classification."
)


st.divider()


# ---------------------------------------------------------
# Pattern distribution
# ---------------------------------------------------------
st.subheader("Pattern Distribution")

distribution = (
    year_df.groupby(
        "pattern_label",
        as_index=False,
    )["company_id"]
    .nunique()
    .rename(
        columns={
            "company_id": "company_count"
        }
    )
    .sort_values(
        "company_count",
        ascending=False,
    )
)

fig_distribution = px.bar(
    distribution,
    x="pattern_label",
    y="company_count",
    text="company_count",
    labels={
        "pattern_label": "Allocation Pattern",
        "company_count": "Company Count",
    },
)

fig_distribution.update_traces(
    textposition="inside",
)

fig_distribution.update_layout(
    height=500,
    showlegend=False,
    xaxis_title="Allocation Pattern",
    yaxis_title="Company Count",
)

st.plotly_chart(
    fig_distribution,
    width="stretch",
)


st.divider()


# ---------------------------------------------------------
# Companies by allocation pattern
# ---------------------------------------------------------
st.subheader("Companies by Allocation Pattern")

pattern_options = sorted(
    year_df["pattern_label"]
    .dropna()
    .unique()
    .tolist()
)

# Prefer Distress Signal when available for quick monitoring
default_pattern_index = 0

if "Distress Signal" in pattern_options:
    default_pattern_index = pattern_options.index(
        "Distress Signal"
    )


selected_pattern = st.selectbox(
    "Allocation Pattern",
    pattern_options,
    index=default_pattern_index,
)


pattern_df = year_df[
    year_df["pattern_label"] == selected_pattern
].copy()


st.markdown(
    f"### {len(pattern_df)} "
    f"{'company' if len(pattern_df) == 1 else 'companies'} "
    f"in {selected_pattern}"
)


# ---------------------------------------------------------
# Display table
# ---------------------------------------------------------
display_columns = []

column_labels = {
    "company_id": "Ticker",
    "company_name": "Company",
    "broad_sector": "Sector",
    "free_cash_flow_cr": "FCF ₹ Cr",
    "cfo_pat_ratio": "CFO / PAT",
    "cfo_quality_label": "CFO Quality",
    "capex_intensity_pct": "CapEx Intensity %",
    "capex_intensity_label": "CapEx Label",
    "fcf_conversion_pct": "FCF Conversion %",
    "fcf_conversion_label": "FCF Conversion",
    "distress_flag_bool": "Distress Flag",
    "year": "Data Year",
}

preferred_columns = [
    "company_id",
    "company_name",
    "broad_sector",
    "free_cash_flow_cr",
    "cfo_pat_ratio",
    "cfo_quality_label",
    "capex_intensity_pct",
    "capex_intensity_label",
    "fcf_conversion_pct",
    "fcf_conversion_label",
    "year",
]

for column in preferred_columns:
    if column in pattern_df.columns:
        display_columns.append(column)


table_df = pattern_df[
    display_columns
].copy()


# Round numeric columns
for column in [
    "free_cash_flow_cr",
    "cfo_pat_ratio",
    "capex_intensity_pct",
    "fcf_conversion_pct",
]:
    if column in table_df.columns:
        table_df[column] = pd.to_numeric(
            table_df[column],
            errors="coerce",
        ).round(2)


table_df = table_df.rename(
    columns=column_labels
)

table_df = table_df.sort_values(
    by="Ticker"
    if "Ticker" in table_df.columns
    else table_df.columns[0]
)


st.dataframe(
    table_df,
    width="stretch",
    hide_index=True,
)


# ---------------------------------------------------------
# CSV download
# ---------------------------------------------------------
csv = table_df.to_csv(
    index=False
).encode("utf-8")


safe_view_name = (
    selected_year
    .replace(" ", "_")
    .replace("/", "_")
)

safe_pattern_name = (
    selected_pattern
    .replace(" ", "_")
    .replace("/", "_")
)


st.download_button(
    "Download Pattern Companies CSV",
    data=csv,
    file_name=(
        f"{safe_view_name}_"
        f"{safe_pattern_name}_"
        "capital_allocation.csv"
    ),
    mime="text/csv",
    width="stretch",
)


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.caption(
    f"Source: output/capital_allocation.csv | "
    f"View: {selected_year} | "
    f"Companies shown: {year_df['company_id'].nunique()} | "
    f"Actual pattern labels: {pattern_count}"
)