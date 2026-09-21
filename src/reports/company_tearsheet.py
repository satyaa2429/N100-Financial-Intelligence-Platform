"""Generate two-page company financial tearsheets."""

from __future__ import annotations

import argparse
import html
import sqlite3
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "tearsheets"
)

CASHFLOW_INTELLIGENCE_PATH = (
    PROJECT_ROOT
    / "output"
    / "cashflow_intelligence.xlsx"
)

PROS_CONS_PATH = (
    PROJECT_ROOT
    / "output"
    / "pros_cons_generated.csv"
)


PAGE_WIDTH, PAGE_HEIGHT = A4


styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "ReportTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=21,
    alignment=TA_CENTER,
    spaceAfter=6,
)

SUBTITLE_STYLE = ParagraphStyle(
    "Subtitle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=9,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#555555"),
    spaceAfter=10,
)

SECTION_STYLE = ParagraphStyle(
    "Section",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=colors.HexColor("#17365D"),
    spaceBefore=5,
    spaceAfter=5,
)

NORMAL_STYLE = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontSize=8,
    leading=11,
    alignment=TA_LEFT,
)

SMALL_STYLE = ParagraphStyle(
    "Small",
    parent=styles["Normal"],
    fontSize=7,
    leading=9,
)

CARD_STYLE = ParagraphStyle(
    "Card",
    parent=styles["Normal"],
    fontSize=8,
    leading=12,
    alignment=TA_CENTER,
)


def safe_number(value):
    """Return numeric value or None."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_number(value, decimals: int = 1) -> str:
    """Format ordinary numeric value."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}"


def fmt_pct(value) -> str:
    """Format percentage value."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.1f}%"


def fmt_multiple(value) -> str:
    """Format ratio as multiple."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.2f}x"


def fmt_cr(value) -> str:
    """Format Indian crore amount."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f} Cr"


def query_df(
    conn: sqlite3.Connection,
    query: str,
    params: tuple = (),
) -> pd.DataFrame:
    """Execute SQL and return DataFrame."""
    return pd.read_sql_query(
        query,
        conn,
        params=params,
    )


def get_company_profile(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load company and sector information."""
    return query_df(
        conn,
        """
        SELECT
            c.id AS company_id,
            c.company_name,
            COALESCE(
                s.broad_sector,
                'Not Available'
            ) AS broad_sector,
            COALESCE(
                s.sub_sector,
                'Not Available'
            ) AS sub_sector
        FROM companies c
        LEFT JOIN sectors s
            ON s.company_id = c.id
        WHERE c.id = ?
        """,
        (ticker,),
    )


def get_latest_ratios(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load latest financial ratio record."""
    return query_df(
        conn,
        """
        SELECT *
        FROM financial_ratios
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year DESC
        LIMIT 1
        """,
        (ticker,),
    )


def get_ratio_history(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load historical ROE and ROCE."""
    return query_df(
        conn,
        """
        SELECT
            year,
            return_on_equity_pct,
            return_on_capital_employed_pct
        FROM financial_ratios
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year
        """,
        (ticker,),
    )


def get_pnl_history(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load historical P&L."""
    return query_df(
        conn,
        """
        SELECT
            year,
            sales,
            operating_profit,
            net_profit,
            eps
        FROM profitandloss
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year
        """,
        (ticker,),
    )


def get_bs_history(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load balance-sheet history."""
    return query_df(
        conn,
        """
        SELECT
            year,
            equity_capital,
            reserves,
            borrowings,
            other_liabilities,
            total_assets
        FROM balancesheet
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year
        """,
        (ticker,),
    )


def get_cf_history(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load cash-flow history."""
    return query_df(
        conn,
        """
        SELECT
            year,
            operating_activity,
            investing_activity,
            financing_activity,
            net_cash_flow
        FROM cashflow
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year
        """,
        (ticker,),
    )


def get_latest_market_data(
    conn: sqlite3.Connection,
    ticker: str,
) -> pd.DataFrame:
    """Load latest market valuation record."""
    return query_df(
        conn,
        """
        SELECT *
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year DESC
        LIMIT 1
        """,
        (ticker,),
    )


def get_original_pros_cons(
    conn: sqlite3.Connection,
    ticker: str,
) -> tuple[list[str], list[str]]:
    """Load original qualitative pros and cons."""
    frame = query_df(
        conn,
        """
        SELECT
            pros,
            cons
        FROM prosandcons
        WHERE company_id = ?
        """,
        (ticker,),
    )

    pros = []
    cons = []

    if frame.empty:
        return pros, cons

    for value in frame.get(
        "pros",
        pd.Series(dtype=str),
    ):
        if pd.notna(value) and str(value).strip():
            pros.append(str(value).strip())

    for value in frame.get(
        "cons",
        pd.Series(dtype=str),
    ):
        if pd.notna(value) and str(value).strip():
            cons.append(str(value).strip())

    return pros, cons


def get_generated_pros_cons(
    ticker: str,
) -> tuple[list[str], list[str]]:
    """Load auto-generated qualitative insights."""
    if not PROS_CONS_PATH.exists():
        return [], []

    frame = pd.read_csv(
        PROS_CONS_PATH
    )

    required = {
        "company_id",
        "type",
        "text",
    }

    if not required.issubset(
        frame.columns
    ):
        return [], []

    frame["company_id"] = (
        frame["company_id"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    company = frame[
        frame["company_id"] == ticker
    ].copy()

    if company.empty:
        return [], []

    company["type_normalised"] = (
        company["type"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    if "confidence_pct" in company.columns:
        company["confidence_pct"] = (
            pd.to_numeric(
                company["confidence_pct"],
                errors="coerce",
            )
        )

        company = company.sort_values(
            "confidence_pct",
            ascending=False,
        )

    pros = (
        company[
            company["type_normalised"]
            .str.startswith("pro")
        ]["text"]
        .dropna()
        .astype(str)
        .tolist()
    )

    cons = (
        company[
            company["type_normalised"]
            .str.startswith("con")
        ]["text"]
        .dropna()
        .astype(str)
        .tolist()
    )

    return pros, cons


def get_cashflow_intelligence(
    ticker: str,
) -> dict:
    """Load company row from cash-flow intelligence workbook."""
    if not CASHFLOW_INTELLIGENCE_PATH.exists():
        return {}

    try:
        sheets = pd.read_excel(
            CASHFLOW_INTELLIGENCE_PATH,
            sheet_name=None,
        )
    except Exception:
        return {}

    for frame in sheets.values():
        if "company_id" not in frame.columns:
            continue

        ids = (
            frame["company_id"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        match = frame[
            ids == ticker
        ]

        if not match.empty:
            return match.iloc[0].to_dict()

    return {}


def unique_text(
    items: list[str],
    limit: int = 3,
) -> list[str]:
    """Remove duplicate insight text."""
    output = []
    seen = set()

    for item in items:
        text = str(item).strip()

        if not text:
            continue

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)
        output.append(text)

        if len(output) >= limit:
            break

    return output


def make_revenue_profit_chart(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    """Create 10-year revenue and profit chart."""
    data = frame.tail(10).copy()

    data["sales"] = pd.to_numeric(
        data["sales"],
        errors="coerce",
    )

    data["net_profit"] = pd.to_numeric(
        data["net_profit"],
        errors="coerce",
    )

    x = range(len(data))

    fig, ax = plt.subplots(
        figsize=(7.2, 2.5)
    )

    width = 0.38

    ax.bar(
        [i - width / 2 for i in x],
        data["sales"],
        width=width,
        label="Revenue",
    )

    ax.bar(
        [i + width / 2 for i in x],
        data["net_profit"],
        width=width,
        label="Net Profit",
    )

    ax.set_title(
        "Revenue and Net Profit Trend"
    )

    ax.set_ylabel("Rs Crore")

    ax.set_xticks(list(x))

    ax.set_xticklabels(
        data["year"].astype(str),
        rotation=45,
        ha="right",
        fontsize=7,
    )

    ax.legend(
        fontsize=7
    )

    ax.grid(
        axis="y",
        alpha=0.2,
    )

    fig.tight_layout()

    fig.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


def make_returns_chart(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    """Create historical ROE and ROCE chart."""
    data = frame.tail(10).copy()

    for column in [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    fig, ax = plt.subplots(
        figsize=(7.2, 2.3)
    )

    ax.plot(
        data["year"].astype(str),
        data["return_on_equity_pct"],
        marker="o",
        label="ROE",
    )

    ax.plot(
        data["year"].astype(str),
        data[
            "return_on_capital_employed_pct"
        ],
        marker="o",
        label="ROCE",
    )

    ax.set_title(
        "ROE and ROCE Trend"
    )

    ax.set_ylabel("%")

    ax.tick_params(
        axis="x",
        rotation=45,
        labelsize=7,
    )

    ax.legend(
        fontsize=7
    )

    ax.grid(
        alpha=0.2
    )

    fig.tight_layout()

    fig.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


def make_balance_sheet_chart(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    """Create latest five-year balance-sheet composition chart."""
    data = frame.tail(5).copy()

    for column in [
        "equity_capital",
        "reserves",
        "borrowings",
        "other_liabilities",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        ).fillna(0)

    data["equity_and_reserves"] = (
        data["equity_capital"]
        + data["reserves"]
    )

    x = range(len(data))

    fig, ax = plt.subplots(
        figsize=(3.6, 2.7)
    )

    ax.bar(
        x,
        data["equity_and_reserves"],
        label="Equity + Reserves",
    )

    ax.bar(
        x,
        data["borrowings"],
        bottom=data["equity_and_reserves"],
        label="Borrowings",
    )

    bottom = (
        data["equity_and_reserves"]
        + data["borrowings"]
    )

    ax.bar(
        x,
        data["other_liabilities"],
        bottom=bottom,
        label="Other Liabilities",
    )

    ax.set_title(
        "Balance Sheet Composition",
        fontsize=9,
    )

    ax.set_xticks(list(x))

    ax.set_xticklabels(
        data["year"].astype(str),
        rotation=45,
        ha="right",
        fontsize=6,
    )

    ax.set_ylabel(
        "Rs Crore",
        fontsize=7,
    )

    ax.tick_params(
        axis="y",
        labelsize=6,
    )

    ax.legend(
        fontsize=5,
    )

    fig.tight_layout()

    fig.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


def make_cashflow_chart(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    """Create latest-year cash-flow bridge chart."""
    data = frame.tail(1)

    if data.empty:
        return

    row = data.iloc[0]

    cfo = safe_number(
        row.get("operating_activity")
    ) or 0

    cfi = safe_number(
        row.get("investing_activity")
    ) or 0

    cff = safe_number(
        row.get("financing_activity")
    ) or 0

    net = cfo + cfi + cff

    changes = [
        cfo,
        cfi,
        cff,
    ]

    labels = [
        "CFO",
        "CFI",
        "CFF",
    ]

    bottoms = []
    running = 0.0

    for change in changes:
        if change >= 0:
            bottoms.append(running)
        else:
            bottoms.append(
                running + change
            )

        running += change

    fig, ax = plt.subplots(
        figsize=(3.6, 2.7)
    )

    ax.bar(
        labels,
        [
            abs(value)
            for value in changes
        ],
        bottom=bottoms,
    )

    ax.bar(
        ["Net"],
        [net],
    )

    ax.axhline(
        0,
        linewidth=0.8,
    )

    ax.set_title(
        f"Cash Flow Bridge - {row.get('year', '')}",
        fontsize=9,
    )

    ax.set_ylabel(
        "Rs Crore",
        fontsize=7,
    )

    ax.tick_params(
        axis="both",
        labelsize=6,
    )

    ax.grid(
        axis="y",
        alpha=0.2,
    )

    fig.tight_layout()

    fig.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


def make_kpi_card(
    label: str,
    value: str,
) -> Paragraph:
    """Create a KPI card paragraph."""
    return Paragraph(
        (
            f"<font size='7'>{html.escape(label)}</font>"
            "<br/>"
            f"<b><font size='11'>{html.escape(value)}</font></b>"
        ),
        CARD_STYLE,
    )


def build_intelligence_table(
    intelligence: dict,
) -> Table:
    """Build cash-flow intelligence table."""
    rows = [
        [
            "CFO Quality",
            str(
                intelligence.get(
                    "cfo_quality_label",
                    "N/A",
                )
            ),
        ],
        [
            "FCF CAGR 5Y",
            fmt_pct(
                intelligence.get(
                    "fcf_cagr_5yr_pct"
                )
            ),
        ],
        [
            "CapEx Intensity",
            (
                f"{fmt_pct(intelligence.get('capex_intensity_pct'))} "
                f"({intelligence.get('capex_intensity_label', 'N/A')})"
            ),
        ],
        [
            "FCF Conversion",
            (
                f"{fmt_pct(intelligence.get('fcf_conversion_pct'))} "
                f"({intelligence.get('fcf_conversion_label', 'N/A')})"
            ),
        ],
        [
            "Capital Allocation",
            str(
                intelligence.get(
                    "capital_allocation_label",
                    "N/A",
                )
            ),
        ],
        [
            "Deleveraging",
            (
                "Yes"
                if intelligence.get(
                    "deleveraging_flag"
                )
                else "No"
            ),
        ],
        [
            "Distress Alert",
            (
                "Yes"
                if intelligence.get(
                    "distress_flag"
                )
                else "No"
            ),
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            4.0 * cm,
            11.5 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (1, 0),
                    (1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7.5,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#BBBBBB"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EAF0F6"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def build_pros_cons_table(
    pros: list[str],
    cons: list[str],
) -> Table:
    """Build pros and cons table."""
    pros = pros or [
        "No qualitative pro available."
    ]

    cons = cons or [
        "No qualitative con available."
    ]

    max_rows = max(
        len(pros),
        len(cons),
    )

    rows = [
        [
            Paragraph(
                "<b>Pros</b>",
                NORMAL_STYLE,
            ),
            Paragraph(
                "<b>Cons / Risks</b>",
                NORMAL_STYLE,
            ),
        ]
    ]

    for index in range(max_rows):
        pro_text = (
            pros[index]
            if index < len(pros)
            else ""
        )

        con_text = (
            cons[index]
            if index < len(cons)
            else ""
        )

        rows.append(
            [
                Paragraph(
                    html.escape(
                        pro_text[:220]
                    ),
                    SMALL_STYLE,
                ),
                Paragraph(
                    html.escape(
                        con_text[:220]
                    ),
                    SMALL_STYLE,
                ),
            ]
        )

    table = Table(
        rows,
        colWidths=[
            7.75 * cm,
            7.75 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#EAF0F6"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#BBBBBB"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def add_page_number(
    canvas,
    doc,
) -> None:
    """Add footer and page number."""
    canvas.saveState()

    canvas.setFont(
        "Helvetica",
        7,
    )

    canvas.setFillColor(
        colors.HexColor("#666666")
    )

    canvas.drawString(
        1.5 * cm,
        0.75 * cm,
        "Nifty 100 Financial Intelligence Platform",
    )

    canvas.drawRightString(
        PAGE_WIDTH - 1.5 * cm,
        0.75 * cm,
        f"Page {doc.page}",
    )

    canvas.restoreState()


def generate_tearsheet(
    ticker: str,
) -> Path:
    """Generate one company tearsheet."""
    ticker = (
        ticker
        .strip()
        .upper()
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    with sqlite3.connect(
        DB_PATH
    ) as conn:
        profile = get_company_profile(
            conn,
            ticker,
        )

        if profile.empty:
            raise ValueError(
                f"Unknown company ticker: {ticker}"
            )

        latest_ratios = get_latest_ratios(
            conn,
            ticker,
        )

        ratio_history = get_ratio_history(
            conn,
            ticker,
        )

        pnl = get_pnl_history(
            conn,
            ticker,
        )

        balance_sheet = get_bs_history(
            conn,
            ticker,
        )

        cashflow = get_cf_history(
            conn,
            ticker,
        )

        market = get_latest_market_data(
            conn,
            ticker,
        )

        original_pros, original_cons = (
            get_original_pros_cons(
                conn,
                ticker,
            )
        )

    generated_pros, generated_cons = (
        get_generated_pros_cons(
            ticker
        )
    )

    pros = unique_text(
        original_pros
        + generated_pros,
        limit=3,
    )

    cons = unique_text(
        original_cons
        + generated_cons,
        limit=3,
    )

    intelligence = (
        get_cashflow_intelligence(
            ticker
        )
    )

    company = profile.iloc[0]

    ratio = (
        latest_ratios.iloc[0]
        if not latest_ratios.empty
        else pd.Series(dtype=object)
    )

    market_row = (
        market.iloc[0]
        if not market.empty
        else pd.Series(dtype=object)
    )

    pdf_path = (
        OUTPUT_DIR
        / f"{ticker}_tearsheet.pdf"
    )

    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)

        revenue_chart = (
            temp_dir
            / "revenue_profit.png"
        )

        returns_chart = (
            temp_dir
            / "returns.png"
        )

        bs_chart = (
            temp_dir
            / "balance_sheet.png"
        )

        cf_chart = (
            temp_dir
            / "cashflow.png"
        )

        make_revenue_profit_chart(
            pnl,
            revenue_chart,
        )

        make_returns_chart(
            ratio_history,
            returns_chart,
        )

        make_balance_sheet_chart(
            balance_sheet,
            bs_chart,
        )

        make_cashflow_chart(
            cashflow,
            cf_chart,
        )

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.35 * cm,
            bottomMargin=1.3 * cm,
            title=(
                f"{ticker} Financial Tearsheet"
            ),
            author=(
                "Nifty 100 Financial "
                "Intelligence Platform"
            ),
        )

        story = []

        # --------------------------------------------------
        # PAGE 1
        # --------------------------------------------------

        story.append(
            Paragraph(
                html.escape(
                    str(
                        company[
                            "company_name"
                        ]
                    )
                ),
                TITLE_STYLE,
            )
        )

        story.append(
            Paragraph(
                (
                    f"<b>{html.escape(ticker)}</b> | "
                    f"{html.escape(str(company['broad_sector']))} | "
                    f"{html.escape(str(company['sub_sector']))}"
                ),
                SUBTITLE_STYLE,
            )
        )

        story.append(
            Paragraph(
                "Financial Snapshot",
                SECTION_STYLE,
            )
        )

        kpi_cards = [
            make_kpi_card(
                "ROE",
                fmt_pct(
                    ratio.get(
                        "return_on_equity_pct"
                    )
                ),
            ),
            make_kpi_card(
                "ROCE",
                fmt_pct(
                    ratio.get(
                        "return_on_capital_employed_pct"
                    )
                ),
            ),
            make_kpi_card(
                "Debt / Equity",
                fmt_multiple(
                    ratio.get(
                        "debt_to_equity"
                    )
                ),
            ),
            make_kpi_card(
                "Revenue CAGR 5Y",
                fmt_pct(
                    ratio.get(
                        "revenue_cagr_5yr"
                    )
                ),
            ),
            make_kpi_card(
                "PAT CAGR 5Y",
                fmt_pct(
                    ratio.get(
                        "pat_cagr_5yr"
                    )
                ),
            ),
            make_kpi_card(
                "Free Cash Flow",
                fmt_cr(
                    ratio.get(
                        "free_cash_flow_cr"
                    )
                ),
            ),
        ]

        kpi_table = Table(
            [
                kpi_cards[:3],
                kpi_cards[3:],
            ],
            colWidths=[
                5.15 * cm,
                5.15 * cm,
                5.15 * cm,
            ],
            rowHeights=[
                1.25 * cm,
                1.25 * cm,
            ],
        )

        kpi_table.setStyle(
            TableStyle(
                [
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor(
                            "#AAB7C4"
                        ),
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor(
                            "#F5F8FB"
                        ),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                ]
            )
        )

        story.append(
            kpi_table
        )

        story.append(
            Spacer(
                1,
                0.15 * cm,
            )
        )

        valuation_data = [
            [
                "Latest FY",
                str(
                    ratio.get(
                        "year",
                        "N/A",
                    )
                ),
                "P/E",
                fmt_multiple(
                    market_row.get(
                        "pe_ratio"
                    )
                ),
                "P/B",
                fmt_multiple(
                    market_row.get(
                        "pb_ratio"
                    )
                ),
            ],
            [
                "EPS",
                fmt_number(
                    ratio.get(
                        "earnings_per_share"
                    )
                ),
                "Book Value / Share",
                fmt_number(
                    ratio.get(
                        "book_value_per_share"
                    )
                ),
                "Dividend Payout",
                fmt_pct(
                    ratio.get(
                        "dividend_payout_ratio_pct"
                    )
                ),
            ],
        ]

        valuation_table = Table(
            valuation_data,
            colWidths=[
                2.3 * cm,
                2.75 * cm,
                2.3 * cm,
                2.75 * cm,
                2.3 * cm,
                3.05 * cm,
            ],
        )

        valuation_table.setStyle(
            TableStyle(
                [
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, -1),
                        "Helvetica",
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (0, -1),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTNAME",
                        (2, 0),
                        (2, -1),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTNAME",
                        (4, 0),
                        (4, -1),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor(
                            "#CCCCCC"
                        ),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        3,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        3,
                    ),
                ]
            )
        )

        story.append(
            valuation_table
        )

        story.append(
            Spacer(
                1,
                0.12 * cm,
            )
        )

        story.append(
            Image(
                str(revenue_chart),
                width=15.5 * cm,
                height=5.15 * cm,
            )
        )

        story.append(
            Spacer(
                1,
                0.05 * cm,
            )
        )

        story.append(
            Image(
                str(returns_chart),
                width=15.5 * cm,
                height=4.65 * cm,
            )
        )

        story.append(
            PageBreak()
        )

        # --------------------------------------------------
        # PAGE 2
        # --------------------------------------------------

        story.append(
            Paragraph(
                "Balance Sheet & Cash Flow",
                SECTION_STYLE,
            )
        )

        chart_table = Table(
            [
                [
                    Image(
                        str(bs_chart),
                        width=7.6 * cm,
                        height=5.3 * cm,
                    ),
                    Image(
                        str(cf_chart),
                        width=7.6 * cm,
                        height=5.3 * cm,
                    ),
                ]
            ],
            colWidths=[
                7.75 * cm,
                7.75 * cm,
            ],
        )

        chart_table.setStyle(
            TableStyle(
                [
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        0,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        0,
                    ),
                ]
            )
        )

        story.append(
            chart_table
        )

        story.append(
            Spacer(
                1,
                0.1 * cm,
            )
        )

        story.append(
            Paragraph(
                "Cash Flow Intelligence",
                SECTION_STYLE,
            )
        )

        story.append(
            build_intelligence_table(
                intelligence
            )
        )

        story.append(
            Spacer(
                1,
                0.18 * cm,
            )
        )

        story.append(
            Paragraph(
                "Qualitative Investment Insights",
                SECTION_STYLE,
            )
        )

        story.append(
            build_pros_cons_table(
                pros,
                cons,
            )
        )

        story.append(
            Spacer(
                1,
                0.2 * cm,
            )
        )

        story.append(
            Paragraph(
                (
                    "<b>Note:</b> This report is generated from "
                    "the project's structured financial datasets. "
                    "Rule-based distress, valuation and qualitative "
                    "signals are analytical indicators and should be "
                    "interpreted with sector and company context."
                ),
                SMALL_STYLE,
            )
        )

        doc.build(
            story,
            onFirstPage=add_page_number,
            onLaterPages=add_page_number,
        )

    return pdf_path


def generate_all() -> None:
    """Generate tearsheets for the full company universe."""
    with sqlite3.connect(
        DB_PATH
    ) as conn:
        companies = query_df(
            conn,
            """
            SELECT id
            FROM companies
            ORDER BY id
            """,
        )

    success = 0
    failures = []

    for ticker in companies["id"]:
        ticker = str(
            ticker
        ).strip().upper()

        try:
            path = generate_tearsheet(
                ticker
            )

            success += 1

            print(
                f"[OK] {ticker}: "
                f"{path.name}"
            )

        except Exception as exc:
            failures.append(
                (
                    ticker,
                    str(exc),
                )
            )

            print(
                f"[FAILED] {ticker}: "
                f"{exc}"
            )

    print()
    print(
        "Generated:",
        success,
    )

    print(
        "Failed:",
        len(failures),
    )

    if failures:
        print()
        print(
            "Failures:"
        )

        for ticker, message in failures:
            print(
                f"  {ticker}: {message}"
            )


def main() -> None:
    """Run company tearsheet generator."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate Nifty 100 "
            "company tearsheet PDFs."
        )
    )

    parser.add_argument(
        "--ticker",
        type=str,
        help=(
            "Company ticker, "
            "for example TCS"
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all company PDFs.",
    )

    args = parser.parse_args()

    if args.all:
        generate_all()
        return

    ticker = (
        args.ticker
        if args.ticker
        else "TCS"
    )

    path = generate_tearsheet(
        ticker
    )

    size_kb = (
        path.stat().st_size
        / 1024
    )

    print(
        "Created:",
        path,
    )

    print(
        "Size:",
        f"{size_kb:.1f} KB",
    )


if __name__ == "__main__":
    main()