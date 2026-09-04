# Sprint 3 Retrospective — Screener & Peer Comparison

## Sprint
Sprint 3 — Days 15–21

## Status
COMPLETED

## Completed Work

### Day 15 — Custom Screener Engine
- Implemented analyst-editable `config/screener_config.yaml`.
- Added 15 configurable screening metrics.
- Built `src/screener/engine.py`.
- Screener operates on the full 92-company universe.
- Fixed CAGR population so 5-year growth metrics survive full ratio-table rebuilds.

### Day 16 — Six Preset Screeners
Implemented and verified:
- Quality
- Value
- Growth
- Dividend
- Momentum
- Debt-Free

Verified result counts:
- Quality: 36
- Value: 2
- Growth: 36
- Dividend: 47
- Momentum: 31
- Debt-Free: 3

### Day 17 — Ranking Engine
- Implemented `src/screener/ranking.py`.
- Composite scoring:
  - Profitability: 50%
  - Growth: 30%
  - Valuation: 20%
- Sector-relative percentile normalisation implemented.
- All 92 companies receive a composite score and rank.
- Generated `output/screener_output.xlsx`.
- Workbook includes:
  - Composite Ranking
  - 6 preset sheets
  - Sector sheets
  - 20+ KPI fields

### Day 18 — Peer Percentile Engine
- Implemented `src/analytics/peer.py`.
- Processed all 11 official peer groups.
- 56 official peer-group memberships.
- 20 metrics.
- Generated 1,093 valid percentile records.
- Percentile range: 0.0–1.0.
- Duplicate keys: 0.
- Foreign-key violations: 0.
- Created SQLite `peer_percentiles` table.

### Day 19 — Radar Charts
- Implemented `src/analytics/radar.py`.
- Generated 92 radar-chart PNGs.
- Eight axes:
  - ROE
  - ROCE
  - Net Profit Margin
  - Debt-to-Equity
  - Free Cash Flow
  - PAT CAGR 5Y
  - Revenue CAGR 5Y
  - EPS CAGR 5Y
- 56 companies use official peer-group comparison.
- 36 companies use a clearly labelled broad-sector fallback because the supplied peer-group dataset is partial.
- Missing company metrics are retained as N/A rather than fabricated.
- 6 charts contain genuine N/A company axes.
- Zero zero-byte PNGs.
- Generated `output/radar_chart_manifest.csv`.

### Day 20 — Peer Comparison Workbook
- Implemented `src/analytics/peer_export.py`.
- Generated `output/peer_comparison.xlsx`.
- 11 peer-group sheets.
- 20 metrics per sheet.
- 43 columns per sheet.
- Exactly one benchmark company per group.
- 20 percentile conditional-format rules per sheet.
- Validation errors: 0.

### Day 21 — QA
- Added explicit tests for DQ-01 through DQ-16.
- DQ tests: 16 passed.
- Full regression suite: 129 passed.
- Failures: 0.
- Errors: 0.

## Data Notes

### Peer Group Coverage
The supplied peer-group dataset contains 56 memberships across 11 groups rather than all 92 companies.

The official peer assignments were preserved without modification.

For the Day 19 requirement of 92 radar charts, companies without an official peer assignment use a clearly identified broad-sector comparison fallback. No artificial peer memberships were inserted into the source data.

### Radar Missing Data
Six companies do not have all eight requested radar metrics available in any suitable annual record.

Unavailable metrics remain N/A and are documented in `output/radar_chart_manifest.csv`. No financial values were imputed or fabricated.

### Sector Mapping
The current database contains 10 populated broad-sector labels across the 92-company universe, although project documentation describes 11 intended broad sectors. Existing source mappings were preserved rather than inventing a new category.

## Sprint 3 Deliverables
- `config/screener_config.yaml`
- `src/screener/engine.py`
- `src/screener/ranking.py`
- `src/screener/export.py`
- `src/analytics/peer.py`
- `src/analytics/radar.py`
- `src/analytics/peer_export.py`
- `output/screener_output.xlsx`
- `output/peer_comparison.xlsx`
- `output/radar_chart_manifest.csv`
- `reports/radar_charts/` — 92 PNGs
- `peer_percentiles` SQLite table
- `tests/dq/test_validator.py`
- `sprint3_retro.md`

## Final QA Result
129 passed, 0 failed.

## Sprint 3 Outcome
Sprint 3 requirements for the screener, ranking engine, peer percentile engine, radar-chart generation, peer-comparison workbook, and DQ regression testing are complete.
