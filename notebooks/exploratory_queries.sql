-- ============================================================
-- N100 FINANCIAL INTELLIGENCE PLATFORM
-- SPRINT 1 - DAY 7 EXPLORATORY SQL QUERIES
-- ============================================================


-- QUERY 1: TOTAL NUMBER OF COMPANIES
SELECT COUNT(*) AS total_companies
FROM companies;


-- QUERY 2: ROW COUNTS OF ALL TABLES
SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL
SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL
SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL
SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL
SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL
SELECT 'documents', COUNT(*) FROM documents
UNION ALL
SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL
SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL
SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL
SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL
SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL
SELECT 'peer_groups', COUNT(*) FROM peer_groups;


-- QUERY 3: P&L YEAR COVERAGE PER COMPANY
SELECT
    company_id,
    COUNT(DISTINCT year) AS periods_available,
    MIN(year) AS first_period,
    MAX(year) AS latest_period
FROM profitandloss
GROUP BY company_id
ORDER BY company_id;


-- QUERY 4: BALANCE SHEET YEAR COVERAGE
SELECT
    company_id,
    COUNT(DISTINCT year) AS periods_available,
    MIN(year) AS first_period,
    MAX(year) AS latest_period
FROM balancesheet
GROUP BY company_id
ORDER BY company_id;


-- QUERY 5: CASH FLOW YEAR COVERAGE
SELECT
    company_id,
    COUNT(DISTINCT year) AS periods_available,
    MIN(year) AS first_period,
    MAX(year) AS latest_period
FROM cashflow
GROUP BY company_id
ORDER BY company_id;


-- QUERY 6: CHECK IMPORTANT NULL VALUES
SELECT
    company_id,
    year,
    sales,
    operating_profit,
    net_profit,
    eps
FROM profitandloss
WHERE
    sales IS NULL
    OR operating_profit IS NULL
    OR net_profit IS NULL
    OR eps IS NULL
ORDER BY company_id, year;


-- QUERY 7: CHECK DUPLICATE COMPANY-YEAR RECORDS
SELECT
    'profitandloss' AS table_name,
    company_id,
    year,
    COUNT(*) AS duplicate_count
FROM profitandloss
GROUP BY company_id, year
HAVING COUNT(*) > 1

UNION ALL

SELECT
    'balancesheet',
    company_id,
    year,
    COUNT(*)
FROM balancesheet
GROUP BY company_id, year
HAVING COUNT(*) > 1

UNION ALL

SELECT
    'cashflow',
    company_id,
    year,
    COUNT(*)
FROM cashflow
GROUP BY company_id, year
HAVING COUNT(*) > 1;


-- QUERY 8: CHECK FOREIGN KEY VIOLATIONS
PRAGMA foreign_key_check;


-- QUERY 9: CHECK COMPANY-SECTOR COVERAGE
SELECT
    c.id AS company_id,
    c.company_name
FROM companies c
LEFT JOIN sectors s
    ON c.id = s.company_id
WHERE s.company_id IS NULL
ORDER BY c.id;


-- QUERY 10: COMBINED FINANCIAL VIEW
SELECT
    p.company_id,
    p.year,
    p.sales,
    p.operating_profit,
    p.net_profit,
    b.total_assets,
    b.borrowings,
    c.operating_activity,
    c.investing_activity,
    c.financing_activity
FROM profitandloss p
INNER JOIN balancesheet b
    ON p.company_id = b.company_id
    AND p.year = b.year
INNER JOIN cashflow c
    ON p.company_id = c.company_id
    AND p.year = c.year
ORDER BY p.company_id, p.year;