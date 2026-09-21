from pathlib import Path
import json
import re
import sqlite3
import subprocess
import sys
from urllib.request import urlopen
from urllib.parse import urlencode

import pandas as pd


ROOT = Path.cwd()
DB = ROOT / "data" / "nifty100.db"
rows = []


def record(code, status, details):
    rows.append((code, status, details))
    print(f"{code}: {status} | {details}")


conn = sqlite3.connect(DB)

print("=== D45 ACCEPTANCE AUDIT ===")
print()


# AC-01
count = conn.execute(
    "SELECT COUNT(*) FROM companies"
).fetchone()[0]

record(
    "AC-01",
    "PASS" if count == 92 else "FAIL",
    f"companies={count}",
)


# AC-02
company_ids = {
    r[0]
    for r in conn.execute(
        "SELECT id FROM companies"
    )
}

coverage = {}

for table in [
    "profitandloss",
    "balancesheet",
    "cashflow",
]:
    coverage[table] = dict(
        conn.execute(
            f"""
            SELECT company_id,
                   COUNT(DISTINCT year)
            FROM {table}
            GROUP BY company_id
            """
        ).fetchall()
    )

good = sum(
    1
    for cid in company_ids
    if coverage["profitandloss"].get(cid, 0) >= 10
    and coverage["balancesheet"].get(cid, 0) >= 10
    and coverage["cashflow"].get(cid, 0) >= 10
)

coverage_pct = (
    good / len(company_ids) * 100
)

record(
    "AC-02",
    "PASS" if coverage_pct >= 90 else "FAIL",
    f"{good}/92 companies = {coverage_pct:.1f}% with >=10 years P&L+BS+CF",
)


# AC-03
fk_errors = conn.execute(
    "PRAGMA foreign_key_check"
).fetchall()

record(
    "AC-03",
    "PASS" if not fk_errors else "FAIL",
    f"foreign_key_errors={len(fk_errors)}",
)


# AC-04
ratio_count = conn.execute(
    "SELECT COUNT(*) FROM financial_ratios"
).fetchone()[0]

columns = [
    row[1]
    for row in conn.execute(
        "PRAGMA table_info(financial_ratios)"
    )
]

kpi_columns = [
    c
    for c in columns
    if c not in {"id", "company_id", "year"}
]

populated = 0

for column in kpi_columns:
    non_null = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM financial_ratios
        WHERE "{column}" IS NOT NULL
        """
    ).fetchone()[0]

    if non_null > 0:
        populated += 1

record(
    "AC-04",
    "PASS"
    if ratio_count >= 1100 and populated >= 14
    else "FAIL",
    f"rows={ratio_count}, populated_KPI_columns={populated}",
)


# AC-05
record(
    "AC-05",
    "MANUAL",
    "Revenue CAGR manual Excel spot-check for 3 companies required",
)


# AC-06
record(
    "AC-06",
    "MANUAL",
    "ROE manual comparison for 5 companies required",
)


# AC-07
latest_year = conn.execute(
    "SELECT MAX(year) FROM financial_ratios"
).fetchone()[0]

quality_count = conn.execute(
    """
    SELECT COUNT(*)
    FROM financial_ratios
    WHERE year = ?
      AND return_on_equity_pct > 15
      AND debt_to_equity < 1
      AND free_cash_flow_cr > 0
    """,
    (latest_year,),
).fetchone()[0]

record(
    "AC-07",
    "PASS"
    if 10 <= quality_count <= 50
    else "FAIL",
    f"quality_screener_count={quality_count}",
)


# AC-08
record(
    "AC-08",
    "MANUAL",
    "Open Company Profile and confirm load time <3 seconds",
)


# AC-09
record(
    "AC-09",
    "MANUAL",
    "Download Screener CSV and confirm headers/file open correctly",
)


# AC-10
record(
    "AC-10",
    "MANUAL",
    "Visual review of 5 random tearsheets required",
)


# API helper
def api_get(path, params=None):
    url = (
        "http://127.0.0.1:8000/api/v1"
        + path
    )

    if params:
        url += "?" + urlencode(params)

    with urlopen(
        url,
        timeout=15,
    ) as response:
        return (
            response.status,
            json.loads(
                response.read().decode("utf-8")
            ),
        )


# AC-11
try:
    status, payload = api_get("/health")

    counts = payload.get(
        "db_row_counts",
        {},
    )

    record(
        "AC-11",
        "PASS"
        if status == 200
        and payload.get("status") == "healthy"
        and len(counts) >= 10
        else "FAIL",
        f"HTTP={status}, health={payload.get('status')}, tables={len(counts)}",
    )

except Exception as exc:
    record(
        "AC-11",
        "FAIL",
        f"API unavailable: {exc}",
    )


# AC-12
try:
    status, payload = api_get(
        "/companies/TCS/ratios"
    )

    ratio_rows = (
        len(payload)
        if isinstance(payload, list)
        else 0
    )

    record(
        "AC-12",
        "PASS"
        if status == 200
        and ratio_rows >= 10
        else "FAIL",
        f"TCS ratio rows={ratio_rows}",
    )

except Exception as exc:
    record(
        "AC-12",
        "FAIL",
        str(exc),
    )


# AC-13
try:
    status, api_result = api_get(
        "/screener",
        {
            "min_roe": 15,
            "max_de": 1,
            "min_fcf": 0,
        },
    )

    api_ids = {
        str(
            row.get(
                "company_id",
                row.get("id", ""),
            )
        ).upper()
        for row in api_result
    }

    from src.screener.engine import ScreenerEngine

    engine = ScreenerEngine()
    available = set(
        engine.available_metrics()
    )

    def choose(*names):
        for name in names:
            if name in available:
                return name
        raise KeyError(names)

    roe_key = choose(
        "roe",
        "return_on_equity_pct",
    )

    de_key = choose(
        "debt_to_equity",
        "de",
    )

    fcf_key = choose(
        "free_cash_flow",
        "free_cash_flow_cr",
        "fcf",
    )

    module3 = engine.screen(
        {
            roe_key: 15,
            de_key: 1,
            fcf_key: 0,
        }
    )

    local_ids = set(
        module3["company_id"]
        .astype(str)
        .str.upper()
    )

    record(
        "AC-13",
        "PASS"
        if api_ids == local_ids
        else "FAIL",
        f"API={len(api_ids)}, Module3={len(local_ids)}, differences={len(api_ids ^ local_ids)}",
    )

except Exception as exc:
    record(
        "AC-13",
        "FAIL",
        f"comparison error: {exc}",
    )


# AC-14
groups = conn.execute(
    """
    SELECT COUNT(
        DISTINCT peer_group_name
    )
    FROM peer_groups
    """
).fetchone()[0]

orphans = conn.execute(
    """
    SELECT COUNT(*)
    FROM peer_groups p
    LEFT JOIN companies c
      ON c.id = p.company_id
    WHERE c.id IS NULL
    """
).fetchone()[0]

record(
    "AC-14",
    "PASS"
    if groups == 11
    and orphans == 0
    else "FAIL",
    f"peer_groups={groups}, orphan_members={orphans}",
)


# AC-15
cluster_file = (
    ROOT
    / "output"
    / "cluster_labels.csv"
)

try:
    clusters = pd.read_csv(
        cluster_file
    )

    ids = set(
        pd.to_numeric(
            clusters["cluster_id"],
            errors="coerce",
        ).dropna().astype(int)
    )

    ok = (
        len(clusters) == 92
        and clusters["cluster_id"].isna().sum() == 0
        and ids == {0, 1, 2, 3, 4}
    )

    record(
        "AC-15",
        "PASS" if ok else "FAIL",
        f"rows={len(clusters)}, clusters={sorted(ids)}, nulls={clusters['cluster_id'].isna().sum()}",
    )

except Exception as exc:
    record(
        "AC-15",
        "FAIL",
        str(exc),
    )


# AC-16
pros_file = (
    ROOT
    / "output"
    / "pros_cons_generated.csv"
)

try:
    pc = pd.read_csv(
        pros_file
    )

    pro_cols = [
        c
        for c in pc.columns
        if "pro" in c.lower()
    ]

    con_cols = [
        c
        for c in pc.columns
        if "con" in c.lower()
        and "confidence" not in c.lower()
    ]

    def contains_text(frame, cols):
        if not cols:
            return False

        return any(
            frame[c]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .any()
            for c in cols
        )

    generated_ids = set(
        pc["company_id"]
        .astype(str)
        .str.upper()
    )

    bad = []

    for cid, frame in pc.groupby(
        "company_id"
    ):
        if (
            not contains_text(frame, pro_cols)
            or not contains_text(frame, con_cols)
        ):
            bad.append(cid)

    missing = (
        {str(x).upper() for x in company_ids}
        - generated_ids
    )

    record(
        "AC-16",
        "PASS"
        if not bad and not missing
        else "FAIL",
        f"companies={len(generated_ids)}, missing={len(missing)}, incomplete={len(bad)}",
    )

except Exception as exc:
    record(
        "AC-16",
        "FAIL",
        str(exc),
    )


# AC-17
tear_dir = (
    ROOT
    / "reports"
    / "tearsheets"
)

pdfs = list(
    tear_dir.glob("*.pdf")
)

small = [
    p.name
    for p in pdfs
    if p.stat().st_size < 50 * 1024
]

record(
    "AC-17",
    "PASS"
    if len(pdfs) == 92
    and not small
    else "FAIL",
    f"PDFs={len(pdfs)}, below_50KB={len(small)}",
)


# AC-18
collect = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--collect-only",
        "-q",
    ],
    capture_output=True,
    text=True,
)

match = re.search(
    r"(\d+)\s+tests?\s+collected",
    collect.stdout + collect.stderr,
)

test_count = (
    int(match.group(1))
    if match
    else 0
)

tests = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "--disable-warnings",
    ],
    capture_output=True,
    text=True,
)

record(
    "AC-18",
    "PASS"
    if test_count >= 60
    and tests.returncode == 0
    else "FAIL",
    f"collected={test_count}, pytest_exit={tests.returncode}",
)


# AC-19
validation_files = list(
    ROOT.rglob(
        "validation_failures.csv"
    )
)

if validation_files:
    vf = pd.read_csv(
        validation_files[0]
    )

    required = {
        "company_id",
        "field",
        "issue",
        "severity",
    }

    columns_ok = required.issubset(
        set(vf.columns)
    )

    values_ok = True

    if columns_ok and not vf.empty:
        values_ok = not vf[
            list(required)
        ].isna().any().any()

    record(
        "AC-19",
        "PASS"
        if columns_ok and values_ok
        else "FAIL",
        f"file={validation_files[0]}, rows={len(vf)}, columns_ok={columns_ok}",
    )

else:
    record(
        "AC-19",
        "FAIL",
        "validation_failures.csv not found",
    )


# AC-20
guide = (
    ROOT
    / "docs"
    / "analyst_guide.pdf"
)

try:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader

    reader = PdfReader(
        str(guide)
    )

    pages = len(
        reader.pages
    )

    text = " ".join(
        (page.extract_text() or "")
        for page in reader.pages
    ).lower()

    content_ok = (
        "screener" in text
        and "dashboard" in text
    )

    record(
        "AC-20",
        "PASS"
        if pages >= 10
        and content_ok
        else "FAIL",
        f"pages={pages}, screener+dashboard={content_ok}",
    )

except Exception as exc:
    record(
        "AC-20",
        "FAIL",
        f"PDF validation error: {exc}",
    )


conn.close()


# Summary
passed = sum(
    status == "PASS"
    for _, status, _ in rows
)

failed = sum(
    status == "FAIL"
    for _, status, _ in rows
)

manual = sum(
    status == "MANUAL"
    for _, status, _ in rows
)

print()
print("=== SUMMARY ===")
print("PASS:", passed)
print("FAIL:", failed)
print("MANUAL:", manual)
print("TOTAL:", len(rows))


report = [
    "# D45 Acceptance Audit",
    "",
    "| Gate | Status | Evidence |",
    "|---|---|---|",
]

for code, status, details in rows:
    details = str(details).replace(
        "|",
        "/",
    )

    report.append(
        f"| {code} | {status} | {details} |"
    )

report += [
    "",
    f"Automated PASS: {passed}",
    f"FAIL: {failed}",
    f"Manual review required: {manual}",
]

out = (
    ROOT
    / "output"
    / "d45_acceptance_audit.md"
)

out.write_text(
    "\n".join(report),
    encoding="utf-8",
)

print()
print(
    "Created:",
    out.resolve(),
)
