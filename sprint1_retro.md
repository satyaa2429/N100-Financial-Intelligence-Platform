# Sprint 1 Retrospective – Data Foundation

## Sprint Goal
Build and validate the complete data foundation for the N100 Financial Intelligence Platform using the 7 core and 5 supplementary datasets.

## Completed Work

### Day 1 – Environment Setup
- Created the required project directory structure.
- Created and activated the Python virtual environment.
- Installed project dependencies.
- Configured environment and project configuration files.

### Day 2 – Excel Loader and Normalisation
- Developed the Excel loader for all 7 core datasets.
- Implemented ticker normalisation.
- Implemented financial-year normalisation.
- Successfully loaded the core Excel files.

### Day 3 – Data Quality Validation
- Implemented 16 Data Quality validation rules.
- Generated `validation_failures.csv`.
- Identified duplicate company-year records.
- Identified orphan company IDs.
- Added duplicate removal and orphan-row rejection.
- Resolved all CRITICAL DQ failures.
- Reviewed remaining WARNING-level issues.

### Day 4 – SQLite Database
- Created `db/schema.sql`.
- Created `nifty100.db`.
- Added primary keys, composite keys and foreign-key constraints.
- Implemented the SQLite database loader.
- Verified foreign-key integrity with zero violations.

### Day 5 – Full Data Load
- Loaded all 5 supplementary datasets.
- Completed the full load of all 12 source datasets.
- Generated `output/load_audit.csv`.
- Verified database row counts and integrity.

### Day 6 – Manual Data Quality Review
- Manually reviewed TCS, RELIANCE, HDFCBANK, INFY and ITC.
- Verified P&L, Balance Sheet and Cash Flow historical coverage.
- Identified JIOFIN as having fewer than 5 historical years and retained it as a DQ-16 warning.

### Day 7 – Exploratory SQL
- Created `notebooks/exploratory_queries.sql`.
- Added 10 exploratory SQL queries.
- Covered company counts, table row counts, null checks, duplicate checks, foreign-key checks, year coverage, sector coverage and combined financial analysis.

## Data Quality Summary
- CRITICAL DQ failures after cleaning: 0
- Foreign-key violations: 0
- Duplicate company-year records handled during ETL.
- Orphan records rejected without modifying the original source Excel files.
- Remaining non-critical anomalies retained as warnings for review.

## Key Challenges
- Duplicate historical records in multiple financial datasets.
- Company IDs in child datasets that were not present in the company master.
- Inconsistent source OPM values.
- Different financial-year formats requiring normalisation.

## Resolution
All critical issues were handled through the ETL pipeline while keeping the original source files unchanged.

## Sprint 1 Result
Sprint 1 – Data Foundation completed successfully. The validated SQLite database and ETL foundation are ready for Sprint 2 – Ratio Engine.