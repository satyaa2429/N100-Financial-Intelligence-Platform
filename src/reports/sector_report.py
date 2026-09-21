"""Generate sector-level financial intelligence PDF reports."""

from __future__ import annotations

import re
import sqlite3
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

OUTPUT_DIR = PROJECT_ROOT / "reports" / "sector"

PAGE_WIDTH, PAGE_HEIGHT = A4


styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "SectorTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    alignment=TA_CENTER,
    spaceAfter=8,
)

SUBTITLE_STYLE = ParagraphStyle(
    "SectorSubtitle",
    parent=styles["Normal"],
    fontSize=9,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#555555"),
    spaceAfter=12,
)

SECTION_STYLE = ParagraphStyle(
    "SectorSection",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=colors.HexColor("#17365D"),
    spaceBefore=6,
    spaceAfter=6,
)

SMALL_STYLE = ParagraphStyle(
    "Small",
    parent=styles["Normal"],
    fontSize=7,
    leading=9,
)


def safe_number(value):
    """Convert value to float or return None."""
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
    """Format financial ratio."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:.2f}x"


def fmt_cr(value) -> str:
    """Format crore amount."""
    value = safe_number(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f}"


def clean_filename(name: str) -> str:
    """Convert sector name into safe file name."""
    value = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        name.strip(),
    )

    return value.strip("_")


def load_latest_sector_data() -> pd.DataFrame:
    """Load latest-year sector KPI universe."""

    query = """
        SELECT
            c.id AS company_id,
            c.company_name,
            s.broad_sector,
            s.sub_sector,

            r.year,

            r.return_on_equity_pct,
            r.return_on_capital_employed_pct,
            r.net_profit_margin_pct,
            r.operating_profit_margin_pct,
            r.debt_to_equity,
            r.free_cash_flow_cr,
            r.revenue_cagr_5yr,
            r.pat_cagr_5yr,
            r.eps_cagr_5yr,

            m.market_cap_crore,
            m.pe_ratio,
            m.pb_ratio,
            m.dividend_yield_pct

        FROM companies c

        INNER JOIN sectors s
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


def calculate_sector_summary(
    sector_frame: pd.DataFrame,
) -> dict:
    """Calculate sector-level summary metrics."""

    numeric_columns = [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "pe_ratio",
        "pb_ratio",
        "market_cap_crore",
    ]

    data = sector_frame.copy()

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    return {
        "company_count": len(data),

        "median_roe": (
            data["return_on_equity_pct"]
            .median()
        ),

        "median_roce": (
            data["return_on_capital_employed_pct"]
            .median()
        ),

        "median_npm": (
            data["net_profit_margin_pct"]
            .median()
        ),

        "median_de": (
            data["debt_to_equity"]
            .median()
        ),

        "median_fcf": (
            data["free_cash_flow_cr"]
            .median()
        ),

        "median_rev_cagr": (
            data["revenue_cagr_5yr"]
            .median()
        ),

        "median_pat_cagr": (
            data["pat_cagr_5yr"]
            .median()
        ),

        "median_pe": (
            data["pe_ratio"]
            .median()
        ),

        "median_pb": (
            data["pb_ratio"]
            .median()
        ),

        "total_market_cap": (
            data["market_cap_crore"]
            .sum()
        ),
    }


def get_sector_extremes(
    sector_frame: pd.DataFrame,
) -> tuple[str, str]:
    """Return highest and lowest latest ROE company."""

    data = sector_frame.copy()

    data["return_on_equity_pct"] = pd.to_numeric(
        data["return_on_equity_pct"],
        errors="coerce",
    )

    valid = data.dropna(
        subset=["return_on_equity_pct"]
    )

    if valid.empty:
        return "N/A", "N/A"

    highest = valid.loc[
        valid["return_on_equity_pct"].idxmax()
    ]

    lowest = valid.loc[
        valid["return_on_equity_pct"].idxmin()
    ]

    highest_text = (
        f"{highest['company_id']} "
        f"({highest['return_on_equity_pct']:.1f}%)"
    )

    lowest_text = (
        f"{lowest['company_id']} "
        f"({lowest['return_on_equity_pct']:.1f}%)"
    )

    return highest_text, lowest_text


def build_summary_table(
    summary: dict,
) -> Table:
    """Create sector median KPI table."""

    rows = [
        [
            "Metric",
            "Sector Value",
            "Metric",
            "Sector Value",
        ],
        [
            "Companies",
            str(summary["company_count"]),
            "Total Market Cap (Cr)",
            fmt_cr(
                summary["total_market_cap"]
            ),
        ],
        [
            "Median ROE",
            fmt_pct(
                summary["median_roe"]
            ),
            "Median ROCE",
            fmt_pct(
                summary["median_roce"]
            ),
        ],
        [
            "Median Net Margin",
            fmt_pct(
                summary["median_npm"]
            ),
            "Median Debt / Equity",
            fmt_ratio(
                summary["median_de"]
            ),
        ],
        [
            "Median Revenue CAGR 5Y",
            fmt_pct(
                summary["median_rev_cagr"]
            ),
            "Median PAT CAGR 5Y",
            fmt_pct(
                summary["median_pat_cagr"]
            ),
        ],
        [
            "Median Free Cash Flow",
            f"{fmt_cr(summary['median_fcf'])} Cr",
            "Median P/E",
            fmt_ratio(
                summary["median_pe"]
            ),
        ],
        [
            "Median P/B",
            fmt_ratio(
                summary["median_pb"]
            ),
            "",
            "",
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            4.1 * cm,
            3.6 * cm,
            4.1 * cm,
            3.6 * cm,
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
                    "FONTNAME",
                    (2, 1),
                    (2, -1),
                    "Helvetica-Bold",
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
                    0.35,
                    colors.HexColor("#B7B7B7"),
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, -1),
                    colors.HexColor("#F5F8FB"),
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
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def build_company_table(
    sector_frame: pd.DataFrame,
) -> Table:
    """Create table of all companies in the sector."""

    data = sector_frame.copy()

    numeric_columns = [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "free_cash_flow_cr",
        "pe_ratio",
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.sort_values(
        "return_on_equity_pct",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    rows = [
        [
            "Ticker",
            "Company",
            "ROE",
            "ROCE",
            "D/E",
            "Rev CAGR",
            "PAT CAGR",
            "FCF Cr",
            "P/E",
        ]
    ]

    for _, row in data.iterrows():

        company_name = str(
            row["company_name"]
        )

        if len(company_name) > 28:
            company_name = (
                company_name[:25] + "..."
            )

        rows.append(
            [
                str(row["company_id"]),
                company_name,
                fmt_pct(
                    row[
                        "return_on_equity_pct"
                    ]
                ),
                fmt_pct(
                    row[
                        "return_on_capital_employed_pct"
                    ]
                ),
                fmt_ratio(
                    row["debt_to_equity"]
                ),
                fmt_pct(
                    row["revenue_cagr_5yr"]
                ),
                fmt_pct(
                    row["pat_cagr_5yr"]
                ),
                fmt_cr(
                    row["free_cash_flow_cr"]
                ),
                fmt_ratio(
                    row["pe_ratio"]
                ),
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[
            1.7 * cm,
            4.1 * cm,
            1.45 * cm,
            1.45 * cm,
            1.35 * cm,
            1.65 * cm,
            1.65 * cm,
            1.6 * cm,
            1.35 * cm,
        ],
    )

    style_commands = [
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
            (-1, -1),
            "Helvetica",
        ),
        (
            "FONTSIZE",
            (0, 0),
            (-1, -1),
            6.5,
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.25,
            colors.HexColor("#C5C5C5"),
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
            4,
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            4,
        ),
    ]

    if len(rows) > 1:
        # Highest ROE row
        style_commands.append(
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#E8F5E9"),
            )
        )

    if len(rows) > 2:
        # Lowest ROE row
        style_commands.append(
            (
                "BACKGROUND",
                (0, len(rows) - 1),
                (-1, len(rows) - 1),
                colors.HexColor("#FDECEC"),
            )
        )

    table.setStyle(
        TableStyle(style_commands)
    )

    return table


def add_page_number(
    canvas,
    doc,
) -> None:
    """Add report footer."""

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


def generate_sector_report(
    sector_name: str,
    sector_frame: pd.DataFrame,
) -> Path:
    """Generate one sector PDF."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_name = (
        clean_filename(sector_name)
        + "_report.pdf"
    )

    output_path = (
        OUTPUT_DIR / file_name
    )

    summary = calculate_sector_summary(
        sector_frame
    )

    highest_roe, lowest_roe = (
        get_sector_extremes(
            sector_frame
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.3 * cm,
        rightMargin=1.3 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.3 * cm,
        title=f"{sector_name} Sector Report",
        author=(
            "Nifty 100 Financial "
            "Intelligence Platform"
        ),
    )

    story = []

    story.append(
        Paragraph(
            f"{sector_name} Sector Report",
            TITLE_STYLE,
        )
    )

    latest_year = (
        sector_frame["year"]
        .dropna()
        .astype(str)
        .max()
    )

    story.append(
        Paragraph(
            (
                "Nifty 100 Financial Intelligence Platform"
                f"<br/>Latest financial year: {latest_year}"
            ),
            SUBTITLE_STYLE,
        )
    )

    story.append(
        Paragraph(
            "Sector Overview",
            SECTION_STYLE,
        )
    )

    story.append(
        build_summary_table(
            summary
        )
    )

    story.append(
        Spacer(
            1,
            0.25 * cm,
        )
    )

    highlight_rows = [
        [
            "Latest ROE Highlight",
            "Company",
        ],
        [
            "Highest ROE in Sector",
            highest_roe,
        ],
        [
            "Lowest ROE in Sector",
            lowest_roe,
        ],
    ]

    highlight_table = Table(
        highlight_rows,
        colWidths=[
            7.5 * cm,
            7.5 * cm,
        ],
    )

    highlight_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9EAF7"),
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
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#BBBBBB"),
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7.5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(
        highlight_table
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
                "The highlights above are descriptive "
                "latest-year ROE comparisons within this "
                "sector and should not be interpreted as "
                "investment recommendations."
            ),
            SMALL_STYLE,
        )
    )

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "Company Comparison",
            SECTION_STYLE,
        )
    )

    story.append(
        Paragraph(
            (
                "Green row = highest latest-year ROE in "
                "the sector. Red row = lowest latest-year "
                "ROE among companies with available ROE."
            ),
            SMALL_STYLE,
        )
    )

    story.append(
        Spacer(
            1,
            0.1 * cm,
        )
    )

    story.append(
        build_company_table(
            sector_frame
        )
    )

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    return output_path


def generate_all_sector_reports() -> None:
    """Generate reports for every broad sector."""

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    frame = load_latest_sector_data()

    sectors = sorted(
        frame["broad_sector"]
        .dropna()
        .unique()
    )

    print(
        "Sectors found:",
        len(sectors),
    )

    success = 0
    failures = []

    for sector in sectors:

        sector_frame = frame[
            frame["broad_sector"] == sector
        ].copy()

        try:
            path = generate_sector_report(
                str(sector),
                sector_frame,
            )

            success += 1

            print(
                f"[OK] {sector}: "
                f"{len(sector_frame)} companies -> "
                f"{path.name}"
            )

        except Exception as exc:
            failures.append(
                (
                    sector,
                    str(exc),
                )
            )

            print(
                f"[FAILED] {sector}: {exc}"
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
        print(
            "\nFailures:"
        )

        for sector, error in failures:
            print(
                f"  {sector}: {error}"
            )


def main() -> None:
    """Run sector report generator."""

    generate_all_sector_reports()


if __name__ == "__main__":
    main()