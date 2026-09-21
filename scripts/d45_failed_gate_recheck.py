from pathlib import Path
import json
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
from pypdf import PdfReader


ROOT = Path.cwd()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


print("=== D45 FAILED-GATE RECHECK ===")
print()


# ------------------------------------------------------------
# AC-07
# Official quality screen:
# ROE > 15, D/E < 1, FCF > 0
# ------------------------------------------------------------

try:
    status, payload = api_get(
        "/screener",
        {
            "min_roe": 15,
            "max_de": 1,
            "min_fcf": 0,
        },
    )

    count = (
        len(payload)
        if isinstance(payload, list)
        else 0
    )

    ac07 = (
        status == 200
        and 10 <= count <= 50
    )

    print(
        "AC-07:",
        "PASS" if ac07 else "FAIL",
        f"| quality_screener_count={count}",
    )

except Exception as exc:
    ac07 = False
    print(
        "AC-07: FAIL |",
        exc,
    )


# ------------------------------------------------------------
# AC-13
# API screener vs Sprint-3 screener engine
# ------------------------------------------------------------

try:
    from src.screener.engine import ScreenerEngine

    engine = ScreenerEngine()

    available = set(
        engine.available_metrics()
    )

    def choose(*names):
        for name in names:
            if name in available:
                return name

        raise KeyError(
            f"No matching metric among: {names}"
        )

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

    _, api_payload = api_get(
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
        for row in api_payload
    }

    diff = api_ids ^ local_ids

    ac13 = (
        api_ids == local_ids
    )

    print(
        "AC-13:",
        "PASS" if ac13 else "FAIL",
        f"| API={len(api_ids)}, "
        f"Module3={len(local_ids)}, "
        f"differences={len(diff)}",
    )

    if diff:
        print(
            "Different tickers:",
            sorted(diff),
        )

except Exception as exc:
    ac13 = False
    print(
        "AC-13: FAIL |",
        exc,
    )


# ------------------------------------------------------------
# AC-16
# Every company needs >=1 pro and >=1 con
# ------------------------------------------------------------

try:
    pc = pd.read_csv(
        ROOT
        / "output"
        / "pros_cons_generated.csv"
    )

    grouped = (
        pc.assign(
            type=pc["type"]
            .astype(str)
            .str.strip()
            .str.lower(),
            text=pc["text"]
            .fillna("")
            .astype(str)
            .str.strip(),
        )
        .query("text != ''")
        .groupby("company_id")["type"]
        .agg(set)
    )

    all_companies = set(
        pc["company_id"]
        .astype(str)
        .str.upper()
    )

    incomplete = []

    for company in sorted(all_companies):

        types = grouped.get(
            company,
            set(),
        )

        if not (
            "pro" in types
            and "con" in types
        ):
            incomplete.append(company)

    ac16 = (
        len(all_companies) == 92
        and len(incomplete) == 0
    )

    print(
        "AC-16:",
        "PASS" if ac16 else "FAIL",
        f"| companies={len(all_companies)}, "
        f"incomplete={len(incomplete)}",
    )

    if incomplete:
        print(
            "Incomplete companies:",
            incomplete,
        )

except Exception as exc:
    ac16 = False
    print(
        "AC-16: FAIL |",
        exc,
    )


# ------------------------------------------------------------
# AC-20
# Analyst guide >=10 pages and contains dashboard+screener
# ------------------------------------------------------------

try:
    guide = (
        ROOT
        / "docs"
        / "analyst_guide.pdf"
    )

    reader = PdfReader(
        str(guide)
    )

    pages = len(
        reader.pages
    )

    text = " ".join(
        page.extract_text() or ""
        for page in reader.pages
    ).lower()

    contains_screener = (
        "screener" in text
    )

    contains_dashboard = (
        "dashboard" in text
    )

    ac20 = (
        pages >= 10
        and contains_screener
        and contains_dashboard
    )

    print(
        "AC-20:",
        "PASS" if ac20 else "FAIL",
        f"| pages={pages}, "
        f"screener={contains_screener}, "
        f"dashboard={contains_dashboard}",
    )

except Exception as exc:
    ac20 = False
    print(
        "AC-20: FAIL |",
        exc,
    )


print()
print("=== RECHECK SUMMARY ===")

passed = sum(
    [ac07, ac13, ac16, ac20]
)

print(
    f"PASS: {passed}/4"
)

print(
    "RESULT:",
    "ALL FIXED"
    if passed == 4
    else "REVIEW REQUIRED",
)
