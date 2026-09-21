# Sprint 4 Retrospective

## Sprint
Sprint 4 — Dashboard & Valuation

## Completed Work

- Built and validated the Streamlit dashboard.
- Completed all 8 dashboard screens:
  - Home
  - Company Profile
  - Financial Screener
  - Peer Comparison
  - Trend Analysis
  - Sector Analysis
  - Capital Allocation
  - Annual Reports
- Generated valuation_summary.xlsx.
- Generated valuation_flags.csv.
- Completed dashboard integration testing.
- Validated dashboard data using 10 representative companies.

## Issues Found and Fixed

### Screener Preset
The dashboard displayed Turnaround instead of the official Momentum preset.

Fix:
Replaced Turnaround with Momentum using Revenue CAGR 5Y > 15%.

### Sector Coverage
The database originally contained 10 broad sectors instead of the required 11.

Fix:
Created Conglomerates / Other and mapped:
- ADANIENT
- BAJAJHLDNG
- GRASIM
- ITC
- RELIANCE

Final sector count: 11.

## QA Result

All 8 dashboard pages load successfully.

10-company dashboard data validation passed.

No critical dashboard errors remain.

## Sprint 4 Status

PASS — Sprint 4 deliverables completed and validated.
