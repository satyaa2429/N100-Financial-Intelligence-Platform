\# N100 Financial Intelligence Platform



A financial analytics platform for 92 Nifty 100 companies using Python, SQLite, Streamlit, financial ratio analysis, screeners, peer comparison, sector analytics, valuation and automated reporting.



\## Project Structure



\- data/ — raw, supporting and SQLite data

\- src/etl/ — ETL, normalization and validation

\- src/analytics/ — ratio, CAGR, cash-flow and peer analytics

\- src/screener/ — screener engine and ranking

\- src/dashboard/ — Streamlit dashboard

\- tests/ — ETL, DQ and KPI tests

\- output/ — generated Excel/CSV outputs

\- reports/ — generated charts and reports



\## Run the Dashboard



Open PowerShell inside the project folder:



cd "C:\\Users\\saisr\\OneDrive\\Desktop\\BlueStock Internship\\N100\_Financial\_Intelligence\_Platform"



Activate the virtual environment:



.\\venv\\Scripts\\Activate.ps1



Start Streamlit:



streamlit run .\\src\\dashboard\\app.py



The application will open in the browser, usually at:



http://localhost:8501



If port 8501 is already in use, Streamlit may use another available port.



\## Dashboard Screens



1\. Home

2\. Company Profile

3\. Financial Screener

4\. Peer Comparison

5\. Trend Analysis

6\. Sector Analysis

7\. Capital Allocation

8\. Annual Reports



\## Sprint 4 Status



Sprint 4 — Dashboard \& Valuation: Complete



Key outputs:



\- output/valuation\_summary.xlsx

\- output/valuation\_flags.csv

\- dashboard\_qa.md

\- sprint4\_retro.md



Dashboard QA completed across all 8 pages and 10 representative companies.

---

## Platform Quick Start

### Start FastAPI

Run: python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

Swagger: http://127.0.0.1:8000/docs

Health: http://127.0.0.1:8000/api/v1/health

### Start Dashboard

Run: streamlit run src/dashboard/app.py

The dashboard contains 8 screens: Home, Company Profile, Financial Screener, Peer Comparison, Trend Analysis, Sector Analysis, Capital Allocation, and Annual Reports.

### Testing

Run: python -m pytest tests -q --html=pytest_report.html --self-contained-html

Current status: 94 automated tests passing, 16 FastAPI endpoints, 92 companies available through the API, 5 machine-learning clusters, and 10/10 concurrent screener requests passed.

### Integration

Dashboard API client: src/dashboard/utils/api_client.py

Performance test: scripts/d43_integration_perf_test.py

Performance report: perf_notes.md

### Main Outputs

- data/nifty100.db
- output/cluster_labels.csv
- output/cashflow_intelligence.xlsx
- output/pros_cons_generated.csv
- reports/tearsheets/
- reports/sector/
- reports/portfolio/
- docs/openapi.json
- docs/postman_collection.json
- pytest_report.html
- perf_notes.md
- docs/analyst_guide.pdf

### Project Status

Days 29-43 complete. Current phase: Day 44 Documentation. Final phase: Day 45 Acceptance and Sign-Off.

