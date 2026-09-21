from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import statistics
import time

BASE = "http://127.0.0.1:8000/api/v1"

QUERIES = [
    {"min_roe": 10, "max_de": 2},
    {"min_roe": 15, "max_de": 1},
    {"min_roe": 20},
    {"max_de": 0.5},
    {"min_fcf": 0},
    {"min_rev_cagr_5yr": 5},
    {"min_pat_cagr_5yr": 5},
    {"max_pe": 30},
    {"min_roe": 12, "max_pe": 40},
    {"min_roe": 10, "max_de": 2, "min_rev_cagr_5yr": 5},
]


def get_json(path, params=None):
    url = BASE + path

    if params:
        url += "?" + urlencode(params)

    start = time.perf_counter()

    with urlopen(url, timeout=15) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )
        elapsed = (
            time.perf_counter() - start
        ) * 1000

        return response.status, data, elapsed


def run_screener(item):
    number, params = item

    try:
        status, data, elapsed = get_json(
            "/screener",
            params,
        )

        return {
            "number": number,
            "status": status,
            "rows": len(data) if isinstance(data, list) else 0,
            "latency": elapsed,
            "passed": status == 200,
        }

    except Exception as exc:
        return {
            "number": number,
            "status": 0,
            "rows": 0,
            "latency": 0,
            "passed": False,
            "error": str(exc),
        }


print("=== D43 INTEGRATION TEST ===")

try:
    health_status, health, health_time = get_json(
        "/health"
    )

    company_status, companies, company_time = get_json(
        "/companies"
    )

except Exception as exc:
    print("API connection failed:", exc)
    raise SystemExit(1)


health_ok = (
    health_status == 200
    and health.get("status") == "healthy"
)

companies_ok = (
    company_status == 200
    and isinstance(companies, list)
    and len(companies) == 92
)

print(
    "Health:",
    health_status,
    health.get("status"),
)

print(
    "Companies:",
    company_status,
    len(companies),
)

print(
    "API -> Dashboard integration:",
    "PASS" if health_ok and companies_ok else "FAIL",
)

print()
print("=== 10 CONCURRENT SCREENER REQUESTS ===")

start_all = time.perf_counter()

with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(
        pool.map(
            run_screener,
            enumerate(QUERIES, start=1),
        )
    )

wall_time = time.perf_counter() - start_all

latencies = [
    r["latency"]
    for r in results
    if r["passed"]
]

success = sum(
    1
    for r in results
    if r["passed"]
)

for r in results:
    print(
        f"Request {r['number']:02}: "
        f"HTTP {r['status']} | "
        f"{r['latency']:.2f} ms | "
        f"rows={r['rows']} | "
        f"{'PASS' if r['passed'] else 'FAIL'}"
    )

average = (
    statistics.mean(latencies)
    if latencies
    else 0
)

maximum = (
    max(latencies)
    if latencies
    else 0
)

overall_pass = (
    health_ok
    and companies_ok
    and success == 10
)

print()
print(f"Successful requests: {success}/10")
print(f"Failed requests: {10 - success}/10")
print(f"Average latency: {average:.2f} ms")
print(f"Maximum latency: {maximum:.2f} ms")
print(f"Total wall time: {wall_time:.2f} seconds")
print(
    "D43 RESULT:",
    "PASS" if overall_pass else "FAIL",
)

report = f"""# D43 Integration and Performance Notes

## Integration Test

- FastAPI health: {health.get("status")}
- Health HTTP status: {health_status}
- Companies returned: {len(companies)}
- API to Dashboard integration: {"PASS" if health_ok and companies_ok else "FAIL"}

## 10-Concurrent Screener Load Test

- Concurrent requests: 10
- Successful requests: {success}/10
- Failed requests: {10 - success}/10
- Average latency: {average:.2f} ms
- Maximum latency: {maximum:.2f} ms
- Total wall time: {wall_time:.2f} seconds

## Final Result

D43 RESULT: {"PASS" if overall_pass else "FAIL"}
"""

Path("perf_notes.md").write_text(
    report,
    encoding="utf-8",
)

print("Created: perf_notes.md")
