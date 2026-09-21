"""Annual report repository for Nifty 100 companies."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_documents,
)


st.title("Annual Reports")
st.caption(
    "Browse available annual-report filings for Nifty 100 companies."
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

company_row = companies[
    companies["company_id"] == ticker
].iloc[0]


# ------------------------------------------------------------
# Load report links
# ------------------------------------------------------------

reports = get_documents(ticker).copy()

st.subheader(
    f"{company_row['company_name']} ({ticker})"
)

if reports.empty:

    st.info(
        "No annual-report links are available for this company."
    )
    st.stop()


reports["year"] = pd.to_numeric(
    reports["year"],
    errors="coerce",
).astype("Int64")

reports = reports.dropna(
    subset=["year"]
).copy()

reports["year"] = reports[
    "year"
].astype(int)


# ------------------------------------------------------------
# Year filter
# ------------------------------------------------------------

years = sorted(
    reports["year"]
    .unique()
    .tolist(),
    reverse=True,
)

year_options = [
    "All Years",
    *[str(year) for year in years],
]

selected_year = st.selectbox(
    "Report Year",
    year_options,
)

if selected_year != "All Years":

    display_reports = reports[
        reports["year"] == int(selected_year)
    ].copy()

else:

    display_reports = reports.copy()


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

k1, k2, k3 = st.columns(3)

k1.metric(
    "Reports Available",
    len(reports),
)

k2.metric(
    "Latest Report",
    max(years) if years else "N/A",
)

k3.metric(
    "Earliest Report",
    min(years) if years else "N/A",
)


st.divider()


# ------------------------------------------------------------
# Report cards
# ------------------------------------------------------------

st.subheader("Available Reports")

for row in display_reports.itertuples(
    index=False
):

    url = str(row.annual_report).strip()

    with st.container(border=True):

        left, right = st.columns(
            [4, 1]
        )

        with left:

            st.markdown(
                f"### Annual Report {row.year}"
            )

            st.caption(
                f"{company_row['company_name']} · {ticker}"
            )

            if url and url.lower() not in {
                "nan",
                "none",
                "",
            }:

                st.code(
                    url,
                    language=None,
                    wrap_lines=True,
                )

            else:

                st.warning(
                    "Report URL is unavailable."
                )


        with right:

            if (
                url
                and url.lower()
                not in {
                    "nan",
                    "none",
                    "",
                }
                and url.startswith(
                    ("http://", "https://")
                )
            ):

                st.link_button(
                    "Open PDF",
                    url,
                    width="stretch",
                )

            else:

                st.button(
                    "Unavailable",
                    disabled=True,
                    width="stretch",
                    key=f"missing_{ticker}_{row.year}",
                )


st.caption(
    "Annual-report links originate from the project documents dataset. "
    "External BSE links may become unavailable over time."
)
