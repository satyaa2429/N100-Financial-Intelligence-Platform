# D45 Acceptance Audit

| Gate | Status | Evidence |
|---|---|---|
| AC-01 | PASS | companies=92 |
| AC-02 | PASS | 84/92 companies = 91.3% with >=10 years P&L+BS+CF |
| AC-03 | PASS | foreign_key_errors=0 |
| AC-04 | PASS | rows=1164, populated_KPI_columns=26 |
| AC-05 | MANUAL | Revenue CAGR manual Excel spot-check for 3 companies required |
| AC-06 | MANUAL | ROE manual comparison for 5 companies required |
| AC-07 | FAIL | quality_screener_count=0 |
| AC-08 | MANUAL | Open Company Profile and confirm load time <3 seconds |
| AC-09 | MANUAL | Download Screener CSV and confirm headers/file open correctly |
| AC-10 | MANUAL | Visual review of 5 random tearsheets required |
| AC-11 | PASS | HTTP=200, health=healthy, tables=13 |
| AC-12 | PASS | TCS ratio rows=13 |
| AC-13 | FAIL | comparison error: No module named 'src' |
| AC-14 | PASS | peer_groups=11, orphan_members=0 |
| AC-15 | PASS | rows=92, clusters=[0, 1, 2, 3, 4], nulls=0 |
| AC-16 | FAIL | companies=92, missing=0, incomplete=92 |
| AC-17 | PASS | PDFs=92, below_50KB=0 |
| AC-18 | PASS | collected=94, pytest_exit=0 |
| AC-19 | PASS | file=C:\Users\saisr\OneDrive\Desktop\BlueStock Internship\N100_Financial_Intelligence_Platform\output\validation_failures.csv, rows=344, columns_ok=True |
| AC-20 | FAIL | PDF validation error: No module named 'PyPDF2' |

Automated PASS: 11
FAIL: 4
Manual review required: 5