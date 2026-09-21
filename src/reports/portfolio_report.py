"""Generate the Nifty 100 portfolio summary PDF."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "portfolio"

PAGE_WIDTH, PAGE_HEIGHT = A4

styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "PortfolioTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=17,
    leading=21,
    alignment=TA_CENTER,
    spaceAfter=6,
)

SUBTITLE_STYLE = ParagraphStyle(
    "PortfolioSubtitle",
    parent=styles["Normal"],
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
    textColor=colors.HexColor("#17365D"),
    spaceBefore=5,
    spaceAfter=5,
)

SMALL_STYLE = ParagraphStyle(
    "Small",
    parent=styles["Normal"],
    fontSize=7,
    leading=9,
)


def safe_number(value):
    """Return float value or None."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_pct(value) -> str:
    """Format percentage."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:.1f}%"


def fmt_ratio(value) -> str:
    """Format ratio."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:.2f}x"


def fmt_cr(value) -> str:
    """Format crore value."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f} Cr"


def load_portfolio_data() -> pd.DataFrame:
    """Load latest company and financial data."""

    query = """
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
            ) AS sub_sector,

            r.year,

            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,
            r.net_profit_margin_pct,

            m.market_cap_crore,
            m.pe_ratio,
            m.pb_ratio,
            m.dividend_yield_pct

        FROM companies c

        LEFT JOIN sectors s
            ON s.company_id = c.id

        LEFT JOIN financial_ratios r
            ON r.company_id = c.id
           AND r.year = (
                SELECT MAX(fr.year)
                FROM financial_ratios fr
                WHERE fr.company_id = c.id
                  AND fr.year <> 'TTM'
           )

        LEFT JOIN market_cap m
            ON m.company_id = c.id
           AND m.year = (
                SELECT MAX(mc.year)
                FROM market_cap mc
                WHERE mc.company_id = c.id
           )

        ORDER BY
            s.broad_sector,
            c.id
    """

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            query,
            conn,
        )


def load_three_year_history(
    ticker: str,
) -> pd.DataFrame:
    """Load recent financial-ratio history."""

    query = """
        SELECT
            year,
            return_on_equity_pct,
            free_cash_flow_cr,
            revenue_cagr_3yr,
            pat_cagr_3yr
        FROM financial_ratios
        WHERE company_id = ?
          AND year <> 'TTM'
        ORDER BY year DESC
        LIMIT 4
    """

    with sqlite3.connect(DB_PATH) as conn:
        frame = pd.read_sql_query(
            query,
            conn,
            params=(ticker,),
        )

    return frame.sort_values("year")


def trend_arrow(
    frame: pd.DataFrame,
    column: str,
) -> str:
    """Return up/down/flat trend symbol."""

    if column not in frame.columns:
        return "->"

    values = pd.to_numeric(
        frame[column],
        errors="coerce",
    ).dropna()

    if len(values) < 2:
        return "->"

    start = values.iloc[0]
    end = values.iloc[-1]

    tolerance = max(
        abs(start) * 0.05,
        0.5,
    )

    change = end - start

    if change > tolerance:
        return "UP"

    if change < -tolerance:
        return "DOWN"

    return "FLAT"


def build_kpi_table(row: pd.Series) -> Table:
    """Create company KPI summary."""

    data = [
        [
            "ROE",
            fmt_pct(
                row.get(
                    "return_on_equity_pct"
                )
            ),
            "ROCE",
            fmt_pct(
                row.get(
                    "return_on_capital_employed_pct"
                )
            ),
        ],
        [
            "Debt / Equity",
            fmt_ratio(
                row.get(
                    "debt_to_equity"
                )
            ),
            "Free Cash Flow",
            fmt_cr(
                row.get(
                    "free_cash_flow_cr"
                )
            ),
        ],
        [
            "Revenue CAGR 5Y",
            fmt_pct(
                row.get(
                    "revenue_cagr_5yr"
                )
            ),
            "PAT CAGR 5Y",
            fmt_pct(
                row.get(
                    "pat_cagr_5yr"
                )
            ),
        ],
        [
            "EPS CAGR 5Y",
            fmt_pct(
                row.get(
                    "eps_cagr_5yr"
                )
            ),
            "Net Profit Margin",
            fmt_pct(
                row.get(
                    "net_profit_margin_pct"
                )
            ),
        ],
        [
            "P/E",
            fmt_ratio(
                row.get(
                    "pe_ratio"
                )
            ),
            "P/B",
            fmt_ratio(
                row.get(
                    "pb_ratio"
                )
            ),
        ],
        [
            "Market Cap",
            fmt_cr(
                row.get(
                    "market_cap_crore"
                )
            ),
            "Dividend Yield",
            fmt_pct(
                row.get(
                    "dividend_yield_pct"
                )
            ),
        ],
    ]

    table = Table(
        data,
        colWidths=[
            4.0 * cm,
            3.6 * cm,
            4.0 * cm,
            3.6 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EAF0F6"),
                ),
                (
                    "BACKGROUND",
                    (2, 0),
                    (2, -1),
                    colors.HexColor("#EAF0F6"),
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
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8,
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
                    "MIDDLE",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table


def build_trend_table(
    history: pd.DataFrame,
) -> Table:
    """Create three-year direction table."""

    roe_direction = trend_arrow(
        history,
        "return_on_equity_pct",
    )

    fcf_direction = trend_arrow(
        history,
        "free_cash_flow_cr",
    )

    revenue_direction = trend_arrow(
        history,
        "revenue_cagr_3yr",
    )

    profit_direction = trend_arrow(
        history,
        "pat_cagr_3yr",
    )

    data = [
        [
            "Metric",
            "3-Year Direction",
        ],
        [
            "ROE",
            roe_direction,
        ],
        [
            "Free Cash Flow",
            fcf_direction,
        ],
        [
            "Revenue Growth",
            revenue_direction,
        ],
        [
            "Profit Growth",
            profit_direction,
        ],
    ]

    table = Table(
        data,
        colWidths=[
            8.0 * cm,
            7.2 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#17365D"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (0, 1),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (1, -1),
                    "CENTER",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#BBBBBB"),
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table


def add_footer(
    canvas,
    doc,
) -> None:
    """Add footer to portfolio report."""

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


def generate_portfolio_report() -> Path:
    """Generate one-page summary for every company."""

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame = load_portfolio_data()

    if len(frame) != 92:
        raise RuntimeError(
            "Expected 92 companies, "
            f"found {len(frame)}."
        )

    date_text = datetime.now().strftime(
        "%Y%m%d"
    )

    output_path = (
        OUTPUT_DIR
        / f"portfolio_summary_{date_text}.pdf"
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.4 * cm,
        title="Nifty 100 Portfolio Summary",
        author=(
            "Nifty 100 Financial "
            "Intelligence Platform"
        ),
    )

    story = []

    total_companies = len(frame)

    for index, (_, row) in enumerate(
        frame.iterrows(),
        start=1,
    ):

        ticker = str(
            row["company_id"]
        )

        history = load_three_year_history(
            ticker
        )

        story.append(
            Paragraph(
                str(
                    row["company_name"]
                ),
                TITLE_STYLE,
            )
        )

        story.append(
            Paragraph(
                (
                    f"<b>{ticker}</b> | "
                    f"{row['broad_sector']} | "
                    f"{row['sub_sector']}"
                ),
                SUBTITLE_STYLE,
            )
        )

        story.append(
            Paragraph(
                "Latest Financial Snapshot",
                SECTION_STYLE,
            )
        )

        story.append(
            build_kpi_table(
                row
            )
        )

        story.append(
            Spacer(
                1,
                0.4 * cm,
            )
        )

        story.append(
            Paragraph(
                "Three-Year Direction",
                SECTION_STYLE,
            )
        )

        story.append(
            build_trend_table(
                history
            )
        )

        story.append(
            Spacer(
                1,
                0.4 * cm,
            )
        )

        story.append(
            Paragraph(
                (
                    f"<b>Financial year:</b> "
                    f"{row.get('year', 'N/A')}<br/>"
                    "<b>Direction legend:</b> "
                    "UP = improving, DOWN = declining, "
                    "FLAT = broadly stable.<br/><br/>"
                    "This page is an analytical summary "
                    "generated from the project's structured "
                    "financial datasets. It is not an "
                    "investment recommendation."
                ),
                SMALL_STYLE,
            )
        )

        if index < total_companies:
            story.append(
                PageBreak()
            )

    doc.build(
        story,
        onFirstPage=add_footer,
        onLaterPages=add_footer,
    )

    return output_path


def main() -> None:
    """Run portfolio report generator."""

    path = generate_portfolio_report()

    size_mb = (
        path.stat().st_size
        / (1024 * 1024)
    )

    print(
        "Created:",
        path,
    )

    print(
        "Companies:",
        92,
    )

    print(
        "Expected pages:",
        92,
    )

    print(
        "Size:",
        f"{size_mb:.2f} MB",
    )


if __name__ == "__main__":
    main()