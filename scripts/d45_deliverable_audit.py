from pathlib import Path
import sqlite3

import pandas as pd

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


ROOT = Path.cwd()

results = []


def add(code, status, detail):
    results.append((code, status, detail))
    print(f"{code}: {status} | {detail}")


def find_file(name):
    matches = [
        p for p in ROOT.rglob(name)
        if ".d45_backup" not in p.name
    ]
    return matches[0] if matches else None


print("=== D45 DELIVERABLE AUDIT ===")
print()


# D-01
db = ROOT / "data" / "nifty100.db"

if db.exists():
    with sqlite3.connect(db) as con:
        tables = con.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """
        ).fetchall()

    add(
        "D-01",
        "PASS",
        f"nifty100.db exists; tables={len(tables)}",
    )
else:
    add("D-01", "MISSING", "nifty100.db not found")


# D-02
p = find_file("load_audit.csv")
add(
    "D-02",
    "PASS" if p else "MISSING",
    str(p) if p else "load_audit.csv not found",
)


# D-03
p = find_file("validation_failures.csv")
add(
    "D-03",
    "PASS" if p else "MISSING",
    str(p) if p else "validation_failures.csv not found",
)


# D-04
p = find_file("exploratory_queries.sql")
add(
    "D-04",
    "PASS" if p else "MISSING",
    str(p) if p else "exploratory_queries.sql not found",
)


# D-05
try:
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "SELECT COUNT(*) FROM financial_ratios"
        ).fetchone()[0]

        cols = con.execute(
            "PRAGMA table_info(financial_ratios)"
        ).fetchall()

    kpis = max(len(cols) - 3, 0)

    add(
        "D-05",
        "PASS" if rows >= 1100 and kpis >= 14 else "FAIL",
        f"financial_ratios rows={rows}, KPI columns={kpis}",
    )

except Exception as exc:
    add("D-05", "FAIL", str(exc))


# D-06
p = find_file("capital_allocation.csv")

if p:
    try:
        df = pd.read_csv(p)
        companies = (
            df["company_id"].nunique()
            if "company_id" in df.columns
            else 0
        )

        add(
            "D-06",
            "PASS" if companies == 92 else "FAIL",
            f"{p}; companies={companies}; rows={len(df)}",
        )
    except Exception as exc:
        add("D-06", "FAIL", str(exc))
else:
    add("D-06", "MISSING", "capital_allocation.csv not found")


# D-07
p = find_file("screener_output.xlsx")
add(
    "D-07",
    "PASS" if p else "MISSING",
    str(p) if p else "screener_output.xlsx not found",
)


# D-08
p = find_file("screener_config.yaml")
add(
    "D-08",
    "PASS" if p else "MISSING",
    str(p) if p else "screener_config.yaml not found",
)


# D-09
p = find_file("peer_comparison.xlsx")
add(
    "D-09",
    "PASS" if p else "MISSING",
    str(p) if p else "peer_comparison.xlsx not found",
)


# D-10
radars = [
    p for p in ROOT.rglob("*.png")
    if "radar" in str(p).lower()
]

add(
    "D-10",
    "PASS" if len(radars) >= 92 else "FAIL",
    f"radar PNGs found={len(radars)}",
)


# D-11
app = ROOT / "src" / "dashboard" / "app.py"

pages_dir = ROOT / "src" / "dashboard" / "pages"

pages = (
    list(pages_dir.glob("*.py"))
    if pages_dir.exists()
    else []
)

add(
    "D-11",
    "PASS" if app.exists() and len(pages) >= 8 else "FAIL",
    f"app={app.exists()}, dashboard pages={len(pages)}",
)


# D-12
p = find_file("valuation_summary.xlsx")
add(
    "D-12",
    "PASS" if p else "MISSING",
    str(p) if p else "valuation_summary.xlsx not found",
)


# D-13
p = find_file("cashflow_intelligence.xlsx")
add(
    "D-13",
    "PASS" if p else "MISSING",
    str(p) if p else "cashflow_intelligence.xlsx not found",
)


# D-14
p = find_file("pros_cons_generated.csv")

if p:
    df = pd.read_csv(p)

    companies = (
        df["company_id"].nunique()
        if "company_id" in df.columns
        else 0
    )

    low_conf = (
        (
            pd.to_numeric(
                df["confidence_pct"],
                errors="coerce",
            ) <= 60
        ).sum()
        if "confidence_pct" in df.columns
        else -1
    )

    add(
        "D-14",
        "PASS"
        if companies == 92 and low_conf == 0
        else "FAIL",
        f"companies={companies}, confidence<=60 rows={low_conf}",
    )
else:
    add("D-14", "MISSING", "pros_cons_generated.csv not found")


# D-15
p = find_file("analysis_parsed.csv")
add(
    "D-15",
    "PASS" if p else "MISSING",
    str(p) if p else "analysis_parsed.csv not found",
)


# D-16
tear_dir = ROOT / "reports" / "tearsheets"
tearsheets = (
    [
        p
        for p in tear_dir.glob("*.pdf")
        if not p.name.startswith("~$")
    ]
    if tear_dir.exists()
    else []
)

small = [
    p for p in tearsheets
    if p.stat().st_size < 50 * 1024
]

add(
    "D-16",
    "PASS"
    if len(tearsheets) == 92 and len(small) == 0
    else "FAIL",
    f"tearsheets={len(tearsheets)}, below50KB={len(small)}",
)


# D-17
sector_pdfs = [
    p for p in (ROOT / "reports").rglob("*.pdf")
    if "sector" in str(p).lower()
]

add(
    "D-17",
    "PASS" if len(sector_pdfs) >= 11 else "FAIL",
    f"sector PDFs found={len(sector_pdfs)}",
)


# D-18
portfolio_pdfs = [
    p for p in (ROOT / "reports").rglob("*.pdf")
    if "portfolio" in str(p).lower()
]

add(
    "D-18",
    "PASS" if portfolio_pdfs else "MISSING",
    (
        str(portfolio_pdfs[0])
        if portfolio_pdfs
        else "Portfolio summary PDF not found"
    ),
)


# D-19
p = find_file("cluster_labels.csv")

if p:
    df = pd.read_csv(p)

    add(
        "D-19",
        "PASS" if len(df) == 92 else "FAIL",
        f"{p}; rows={len(df)}",
    )
else:
    add("D-19", "MISSING", "cluster_labels.csv not found")


# D-20
api_main = ROOT / "src" / "api" / "main.py"
openapi = ROOT / "docs" / "openapi.json"
postman = ROOT / "docs" / "postman_collection.json"

add(
    "D-20",
    "PASS"
    if api_main.exists() and openapi.exists() and postman.exists()
    else "FAIL",
    (
        f"api_main={api_main.exists()}, "
        f"openapi={openapi.exists()}, "
        f"postman={postman.exists()}"
    ),
)


# D-21
p = find_file("pytest_report.html")

add(
    "D-21",
    "PASS" if p and p.stat().st_size > 0 else "MISSING",
    (
        f"{p}; size={p.stat().st_size}"
        if p
        else "pytest_report.html not found"
    ),
)


# D-22
guide = ROOT / "docs" / "analyst_guide.pdf"

if guide.exists():

    if PdfReader:
        pages = len(PdfReader(str(guide)).pages)
    else:
        pages = -1

    add(
        "D-22",
        "PASS"
        if pages == -1 or 10 <= pages <= 15
        else "FAIL",
        f"analyst_guide.pdf pages={pages}",
    )

else:
    add("D-22", "MISSING", "analyst_guide.pdf not found")


# D-23
checklist = ROOT / "output" / "acceptance_checklist.pdf"

add(
    "D-23",
    "PASS" if checklist.exists() else "PENDING",
    (
        str(checklist)
        if checklist.exists()
        else "Will be generated after this audit"
    ),
)


print()
print("=== SUMMARY ===")

passed = sum(
    status == "PASS"
    for _, status, _ in results
)

problems = [
    row
    for row in results
    if row[1] in {"FAIL", "MISSING"}
]

pending = sum(
    status == "PENDING"
    for _, status, _ in results
)

print("PASS:", passed)
print("FAIL/MISSING:", len(problems))
print("PENDING:", pending)
print("TOTAL:", len(results))

if problems:
    print()
    print("=== NEEDS ATTENTION ===")
    for code, status, detail in problems:
        print(f"{code}: {status} | {detail}")


report = ROOT / "output" / "d45_deliverable_audit.txt"
report.parent.mkdir(parents=True, exist_ok=True)

report.write_text(
    "\n".join(
        f"{c}: {s} | {d}"
        for c, s, d in results
    ),
    encoding="utf-8",
)

print()
print("Created:", report)
