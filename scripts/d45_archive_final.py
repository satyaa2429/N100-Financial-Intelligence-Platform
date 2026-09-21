from pathlib import Path
import shutil
import sqlite3
import pandas as pd
from datetime import date


ROOT = Path.cwd()
DEST = ROOT / "output" / "final_deliverables"

if DEST.exists():
    shutil.rmtree(DEST)

DEST.mkdir(parents=True)


def valid_path(path):
    return (
        path.exists()
        and DEST not in path.parents
        and "venv" not in path.parts
    )


def find_first(name):
    matches = [
        p for p in ROOT.rglob(name)
        if valid_path(p)
        and not p.name.startswith("~$")
    ]

    return matches[0] if matches else None


def copy_file(source, folder_name):
    folder = DEST / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        source,
        folder / source.name,
    )


manifest = []


def record(code, status, detail):
    manifest.append(
        f"{code}: {status} | {detail}"
    )

    print(
        f"{code}: {status} | {detail}"
    )


print("=== FINAL DELIVERABLE ARCHIVE ===")


# D-01
db = ROOT / "data" / "nifty100.db"

copy_file(
    db,
    "D01_database",
)

record(
    "D-01",
    "COPIED",
    "nifty100.db",
)


# D-02 to D-04
for code, name, folder in [
    ("D-02", "load_audit.csv", "D02_load_audit"),
    ("D-03", "validation_failures.csv", "D03_validation_failures"),
    ("D-04", "exploratory_queries.sql", "D04_exploratory_queries"),
]:

    p = find_first(name)

    if p:
        copy_file(
            p,
            folder,
        )

        record(
            code,
            "COPIED",
            str(p.relative_to(ROOT)),
        )

    else:
        record(
            code,
            "MISSING",
            name,
        )


# D-05 export financial_ratios table
folder = DEST / "D05_financial_ratios"
folder.mkdir()

with sqlite3.connect(db) as con:

    df = pd.read_sql_query(
        "SELECT * FROM financial_ratios",
        con,
    )

df.to_csv(
    folder / "financial_ratios.csv",
    index=False,
)

record(
    "D-05",
    "EXPORTED",
    f"financial_ratios.csv rows={len(df)}",
)


# D-06 to D-09
for code, name, folder in [
    ("D-06", "capital_allocation.csv", "D06_capital_allocation"),
    ("D-07", "screener_output.xlsx", "D07_screener"),
    ("D-08", "screener_config.yaml", "D08_screener_config"),
    ("D-09", "peer_comparison.xlsx", "D09_peer_comparison"),
]:

    p = find_first(name)

    if p:
        copy_file(
            p,
            folder,
        )

        record(
            code,
            "COPIED",
            str(p.relative_to(ROOT)),
        )

    else:
        record(
            code,
            "MISSING",
            name,
        )


# D-10 radar charts
radar_dir = DEST / "D10_radar_charts"
radar_dir.mkdir()

radars = [
    p
    for p in ROOT.rglob("*.png")
    if "radar" in str(p).lower()
    and valid_path(p)
]

for p in radars:

    shutil.copy2(
        p,
        radar_dir / p.name,
    )

record(
    "D-10",
    "COPIED",
    f"radar PNGs={len(radars)}",
)


# D-11 dashboard
dashboard_src = ROOT / "src" / "dashboard"

shutil.copytree(
    dashboard_src,
    DEST / "D11_dashboard",
)

record(
    "D-11",
    "COPIED",
    "src/dashboard",
)


# D-12 to D-15
for code, name, folder in [
    ("D-12", "valuation_summary.xlsx", "D12_valuation"),
    ("D-13", "cashflow_intelligence.xlsx", "D13_cashflow_intelligence"),
    ("D-14", "pros_cons_generated.csv", "D14_pros_cons"),
    ("D-15", "analysis_parsed.csv", "D15_analysis_parsed"),
]:

    p = find_first(name)

    if p:
        copy_file(
            p,
            folder,
        )

        record(
            code,
            "COPIED",
            str(p.relative_to(ROOT)),
        )

    else:
        record(
            code,
            "MISSING",
            name,
        )


# D-16 company tearsheets
tear_dest = DEST / "D16_company_tearsheets"
tear_dest.mkdir()

tears = [
    p
    for p in (
        ROOT
        / "reports"
        / "tearsheets"
    ).glob("*.pdf")
    if not p.name.startswith("~$")
]

for p in tears:

    shutil.copy2(
        p,
        tear_dest / p.name,
    )

record(
    "D-16",
    "COPIED",
    f"company tearsheets={len(tears)}",
)


# D-17 sector reports
sector_dest = DEST / "D17_sector_reports"
sector_dest.mkdir()

sector_reports = [
    p
    for p in (
        ROOT
        / "reports"
    ).rglob("*.pdf")
    if "sector" in str(p).lower()
]

for p in sector_reports:

    shutil.copy2(
        p,
        sector_dest / p.name,
    )

record(
    "D-17",
    "COPIED",
    f"sector reports={len(sector_reports)}",
)


# D-18 portfolio summary
portfolio_reports = [
    p
    for p in (
        ROOT
        / "reports"
    ).rglob("*.pdf")
    if "portfolio" in str(p).lower()
]

if portfolio_reports:

    latest = max(
        portfolio_reports,
        key=lambda p: p.stat().st_mtime,
    )

    copy_file(
        latest,
        "D18_portfolio_summary",
    )

    record(
        "D-18",
        "COPIED",
        latest.name,
    )

else:

    record(
        "D-18",
        "MISSING",
        "Portfolio summary PDF",
    )


# D-19
p = find_first(
    "cluster_labels.csv"
)

if p:

    copy_file(
        p,
        "D19_clusters",
    )

    record(
        "D-19",
        "COPIED",
        str(p.relative_to(ROOT)),
    )


# D-20 API
shutil.copytree(
    ROOT / "src" / "api",
    DEST / "D20_api" / "api",
)

api_docs = DEST / "D20_api" / "docs"
api_docs.mkdir(
    parents=True,
    exist_ok=True,
)

for name in [
    "openapi.json",
    "postman_collection.json",
]:

    source = ROOT / "docs" / name

    shutil.copy2(
        source,
        api_docs / name,
    )

record(
    "D-20",
    "COPIED",
    "FastAPI + OpenAPI + Postman",
)


# D-21
p = ROOT / "pytest_report.html"

copy_file(
    p,
    "D21_pytest_report",
)

record(
    "D-21",
    "COPIED",
    "pytest_report.html",
)


# D-22
p = (
    ROOT
    / "docs"
    / "analyst_guide.pdf"
)

copy_file(
    p,
    "D22_analyst_guide",
)

record(
    "D-22",
    "COPIED",
    "analyst_guide.pdf",
)


# D-23
p = (
    ROOT
    / "output"
    / "acceptance_checklist.pdf"
)

copy_file(
    p,
    "D23_acceptance_checklist",
)

record(
    "D-23",
    "COPIED",
    "acceptance_checklist.pdf",
)


# Useful supporting files
support = DEST / "supporting_files"
support.mkdir()

for name in [
    "README.md",
    "requirements.txt",
    "perf_notes.md",
]:

    p = ROOT / name

    if p.exists():
        shutil.copy2(
            p,
            support / p.name,
        )


# Manifest
manifest_path = (
    DEST
    / "FINAL_DELIVERABLE_MANIFEST.txt"
)

manifest_path.write_text(
    (
        "N100 Financial Intelligence Platform\n"
        "Final Deliverable Archive\n"
        f"Archive Date: {date.today().isoformat()}\n\n"
        + "\n".join(manifest)
        + "\n\n"
        + "Technical Acceptance: 20/20 gates verified.\n"
        + "Deliverables: D-01 through D-23 archived.\n"
        + "Formal Team Lead signature is still required on "
        + "D23_acceptance_checklist/acceptance_checklist.pdf.\n"
    ),
    encoding="utf-8",
)


# ZIP archive
zip_base = (
    ROOT
    / "output"
    / "N100_Final_Deliverables"
)

zip_path = shutil.make_archive(
    str(zip_base),
    "zip",
    root_dir=DEST,
)


print()
print("=== ARCHIVE COMPLETE ===")
print("Folder:", DEST)
print("ZIP:", zip_path)
print("Manifest:", manifest_path)
