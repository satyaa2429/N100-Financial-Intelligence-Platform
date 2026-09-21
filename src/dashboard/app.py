import sys
from pathlib import Path

# ---------------------------------------------------------
# Make project root importable
# ---------------------------------------------------------
# app.py location:
# N100_Financial_Intelligence_Platform/src/dashboard/app.py
#
# parents[2] points to:
# N100_Financial_Intelligence_Platform
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# Imports
# ---------------------------------------------------------
import streamlit as st


# ---------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------
# Dashboard pages directory
# ---------------------------------------------------------
DASHBOARD_DIR = Path(__file__).resolve().parent
PAGES_DIR = DASHBOARD_DIR / "pages"


# ---------------------------------------------------------
# Define all 8 Sprint 4 dashboard screens
# ---------------------------------------------------------
home_page = st.Page(
    str(PAGES_DIR / "01_home.py"),
    title="Home",
    default=True,
)

profile_page = st.Page(
    str(PAGES_DIR / "02_profile.py"),
    title="Company Profile",
)

screener_page = st.Page(
    str(PAGES_DIR / "03_screener.py"),
    title="Screener",
)

peers_page = st.Page(
    str(PAGES_DIR / "04_peers.py"),
    title="Peer Comparison",
)

trends_page = st.Page(
    str(PAGES_DIR / "05_trends.py"),
    title="Trend Analysis",
)

sectors_page = st.Page(
    str(PAGES_DIR / "06_sectors.py"),
    title="Sector Analysis",
)

capital_page = st.Page(
    str(PAGES_DIR / "07_capital.py"),
    title="Capital Allocation",
)

reports_page = st.Page(
    str(PAGES_DIR / "08_reports.py"),
    title="Annual Reports",
)


# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------
navigation = st.navigation(
    [
        home_page,
        profile_page,
        screener_page,
        peers_page,
        trends_page,
        sectors_page,
        capital_page,
        reports_page,
    ]
)


# ---------------------------------------------------------
# Run selected page
# ---------------------------------------------------------
navigation.run()