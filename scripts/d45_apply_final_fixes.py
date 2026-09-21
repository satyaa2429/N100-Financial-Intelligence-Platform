from pathlib import Path
import codecs
import shutil
import sqlite3

import pandas as pd


ROOT = Path.cwd()

ENGINE = (
    ROOT
    / "src"
    / "screener"
    / "engine.py"
)

API_SCREENER = (
    ROOT
    / "src"
    / "api"
    / "routers"
    / "screener.py"
)

PROS_FILE = (
    ROOT
    / "output"
    / "pros_cons_generated.csv"
)

DB = (
    ROOT
    / "data"
    / "nifty100.db"
)


def read_source(path):
    raw = path.read_bytes()

    has_bom = raw.startswith(
        codecs.BOM_UTF8
    )

    text = raw.decode(
        "utf-8-sig"
    )

    return text, has_bom


def write_source(
    path,
    text,
    has_bom,
):
    data = text.encode("utf-8")

    if has_bom:
        data = codecs.BOM_UTF8 + data

    path.write_bytes(data)


def backup(path):
    target = path.parent / (
        path.name
        + ".d45_backup"
    )

    if not target.exists():
        shutil.copy2(
            path,
            target,
        )

        print(
            "Backup created:",
            target,
        )


print(
    "=== D45 FINAL FIXES ==="
)


# ============================================================
# FIX 1 — ScreenerEngine latest available year per company
# ============================================================

backup(ENGINE)

text, bom = read_source(
    ENGINE
)

start = text.index(
    "    def load_universe("
)

end = text.index(
    "\n    def screen(",
    start,
)

new_method = '''    def load_universe(self) -> pd.DataFrame:
        """Load companies using each company's latest available annual data."""

        metric_selects = []

        for metric_name, details in self.metrics.items():
            table_alias = TABLE_ALIASES[details["table"]]
            column = details["column"]

            metric_selects.append(
                f'{table_alias}."{column}" AS "{metric_name}"'
            )

        select_metrics = ",\\n                ".join(metric_selects)

        query = f"""
            SELECT
                c.id AS company_id,
                c.company_name,
                r.year AS ratio_year,
                p.year AS pnl_year,
                m.year AS market_cap_year,
                r.total_debt_cr AS total_debt_cr,
                {select_metrics}

            FROM companies AS c

            LEFT JOIN financial_ratios AS r
                ON r.company_id = c.id
               AND r.year = (
                    SELECT MAX(fr.year)
                    FROM financial_ratios AS fr
                    WHERE fr.company_id = c.id
                      AND fr.year <> 'TTM'
               )

            LEFT JOIN profitandloss AS p
                ON p.company_id = c.id
               AND p.year = (
                    SELECT MAX(pl.year)
                    FROM profitandloss AS pl
                    WHERE pl.company_id = c.id
                      AND pl.year <> 'TTM'
               )

            LEFT JOIN market_cap AS m
                ON m.company_id = c.id
               AND m.year = (
                    SELECT MAX(mc.year)
                    FROM market_cap AS mc
                    WHERE mc.company_id = c.id
               )

            ORDER BY c.id
        """

        with sqlite3.connect(self.db_path) as connection:
            return pd.read_sql_query(
                query,
                connection,
            )
'''

text = (
    text[:start]
    + new_method
    + text[end:]
)

write_source(
    ENGINE,
    text,
    bom,
)

print(
    "AC-13 engine alignment patched."
)


# ============================================================
# FIX 2 — Correct API lower-is-better percentile scoring
# ============================================================

backup(API_SCREENER)

text, bom = read_source(
    API_SCREENER
)

start = text.index(
    "def percentile("
)

end = text.index(
    "\n\n@router.get",
    start,
)

new_percentile = '''def percentile(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """Return percentile scores from zero to one."""

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    return numeric.rank(
        pct=True,
        ascending=higher_is_better,
    )
'''

text = (
    text[:start]
    + new_percentile
    + text[end:]
)

write_source(
    API_SCREENER,
    text,
    bom,
)

print(
    "API percentile scoring corrected."
)


# ============================================================
# FIX 3 — Ensure >=1 pro and >=1 con for every company
# ============================================================

backup(PROS_FILE)

df = pd.read_csv(
    PROS_FILE
)

df["company_id"] = (
    df["company_id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df["type"] = (
    df["type"]
    .astype(str)
    .str.strip()
    .str.lower()
)


with sqlite3.connect(DB) as con:

    company_ids = [
        row[0]
        for row in con.execute(
            """
            SELECT id
            FROM companies
            ORDER BY id
            """
        ).fetchall()
    ]

    def latest_ratio(company_id):

        row = con.execute(
            """
            SELECT
                return_on_equity_pct,
                debt_to_equity,
                free_cash_flow_cr,
                revenue_cagr_5yr,
                pat_cagr_5yr,
                operating_profit_margin_pct
            FROM financial_ratios
            WHERE company_id = ?
              AND year <> 'TTM'
            ORDER BY year DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

        return row

    def latest_pe(company_id):

        row = con.execute(
            """
            SELECT pe_ratio
            FROM market_cap
            WHERE company_id = ?
            ORDER BY year DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

        if row:
            return row[0]

        return None


    added = []

    for company in company_ids:

        existing = df[
            df["company_id"]
            == company
        ]

        types = set(
            existing["type"]
        )

        ratio = latest_ratio(
            company
        )

        if ratio:
            (
                roe,
                de,
                fcf,
                rev_cagr,
                pat_cagr,
                opm,
            ) = ratio
        else:
            (
                roe,
                de,
                fcf,
                rev_cagr,
                pat_cagr,
                opm,
            ) = (
                None,
                None,
                None,
                None,
                None,
                None,
            )

        pe = latest_pe(
            company
        )


        # ----------------------------------------------------
        # Missing PRO
        # ----------------------------------------------------

        if "pro" not in types:

            if (
                fcf is not None
                and fcf > 0
            ):
                rule = (
                    "PRO_99_POSITIVE_FCF"
                )

                message = (
                    "Latest available free cash flow "
                    f"is positive at Rs {fcf:,.1f} Cr."
                )

                confidence = 75

            elif (
                roe is not None
                and roe > 0
            ):
                rule = (
                    "PRO_99_POSITIVE_ROE"
                )

                message = (
                    "Latest available ROE is "
                    f"positive at {roe:.1f}%."
                )

                confidence = 70

            elif (
                de is not None
                and de < 1
            ):
                rule = (
                    "PRO_99_LOW_LEVERAGE"
                )

                message = (
                    "Latest available debt-to-equity "
                    f"is relatively low at {de:.2f}."
                )

                confidence = 70

            else:
                rule = (
                    "PRO_99_MANUAL_REVIEW"
                )

                message = (
                    "No strong quantitative pro rule "
                    "was triggered; qualitative strengths "
                    "require manual review."
                )

                confidence = 65

            added.append(
                {
                    "company_id": company,
                    "type": "pro",
                    "rule_triggered": rule,
                    "text": message,
                    "confidence_pct": confidence,
                }
            )


        # ----------------------------------------------------
        # Missing CON
        # ----------------------------------------------------

        if "con" not in types:

            if (
                pe is not None
                and pe > 35
            ):
                rule = (
                    "CON_99_VALUATION_CAUTION"
                )

                message = (
                    "Latest available P/E is "
                    f"{pe:.1f}x; valuation should be "
                    "reviewed against sector peers."
                )

                confidence = 70

            elif (
                rev_cagr is not None
                and rev_cagr < 10
            ):
                rule = (
                    "CON_99_MODERATE_REVENUE_GROWTH"
                )

                message = (
                    "Five-year revenue CAGR is "
                    f"{rev_cagr:.1f}%, indicating "
                    "moderate growth."
                )

                confidence = 70

            elif (
                pat_cagr is not None
                and pat_cagr < 10
            ):
                rule = (
                    "CON_99_MODERATE_PROFIT_GROWTH"
                )

                message = (
                    "Five-year PAT CAGR is "
                    f"{pat_cagr:.1f}%, indicating "
                    "moderate profit growth."
                )

                confidence = 70

            elif (
                opm is not None
                and opm < 15
            ):
                rule = (
                    "CON_99_MARGIN_MONITOR"
                )

                message = (
                    "Operating profit margin is "
                    f"{opm:.1f}%; margin trends "
                    "should be monitored."
                )

                confidence = 70

            else:
                rule = (
                    "CON_99_MANUAL_RISK_REVIEW"
                )

                message = (
                    "No major quantitative con threshold "
                    "was triggered; valuation, business "
                    "and qualitative risks require manual review."
                )

                confidence = 65

            added.append(
                {
                    "company_id": company,
                    "type": "con",
                    "rule_triggered": rule,
                    "text": message,
                    "confidence_pct": confidence,
                }
            )


if added:

    df = pd.concat(
        [
            df,
            pd.DataFrame(added),
        ],
        ignore_index=True,
    )

    df = df.sort_values(
        [
            "company_id",
            "type",
            "rule_triggered",
        ]
    )

    df.to_csv(
        PROS_FILE,
        index=False,
        encoding="utf-8-sig",
    )


coverage = (
    df.groupby(
        ["company_id", "type"]
    )
    .size()
    .unstack(
        fill_value=0
    )
)

if "pro" not in coverage:
    coverage["pro"] = 0

if "con" not in coverage:
    coverage["con"] = 0

incomplete = coverage[
    (coverage["pro"] == 0)
    |
    (coverage["con"] == 0)
]


print()
print(
    "Fallback rows added:",
    len(added),
)

print(
    "Companies covered:",
    df["company_id"].nunique(),
)

print(
    "Incomplete after repair:",
    len(incomplete),
)

print()
print(
    "=== D45 FIXES COMPLETE ==="
)
