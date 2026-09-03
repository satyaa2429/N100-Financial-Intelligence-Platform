PRAGMA foreign_keys = ON;

-- =========================================================
-- N100 FINANCIAL INTELLIGENCE PLATFORM
-- SQLite Database Schema
-- =========================================================


-- =========================================================
-- 1. COMPANIES
-- =========================================================
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    company_logo TEXT,
    company_name TEXT NOT NULL,
    chart_link TEXT,
    about_company TEXT,
    website TEXT,
    nse_profile TEXT,
    bse_profile TEXT,
    face_value REAL,
    book_value REAL,
    roce_percentage REAL,
    roe_percentage REAL
);


-- =========================================================
-- 2. PROFIT AND LOSS
-- =========================================================
CREATE TABLE IF NOT EXISTS profitandloss (
    id INTEGER,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    sales REAL,
    expenses REAL,
    operating_profit REAL,
    opm_percentage REAL,
    other_income REAL,
    interest REAL,
    depreciation REAL,
    profit_before_tax REAL,
    tax_percentage REAL,
    net_profit REAL,
    eps REAL,
    dividend_payout REAL,

    PRIMARY KEY (company_id, year),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 3. BALANCE SHEET
-- =========================================================
CREATE TABLE IF NOT EXISTS balancesheet (
    id INTEGER,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    equity_capital REAL,
    reserves REAL,
    borrowings REAL,
    other_liabilities REAL,
    total_liabilities REAL,
    fixed_assets REAL,
    cwip REAL,
    investments REAL,
    other_asset REAL,
    total_assets REAL,

    PRIMARY KEY (company_id, year),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 4. CASH FLOW
-- =========================================================
CREATE TABLE IF NOT EXISTS cashflow (
    id INTEGER,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    operating_activity REAL,
    investing_activity REAL,
    financing_activity REAL,
    net_cash_flow REAL,

    PRIMARY KEY (company_id, year),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 5. ANALYSIS
-- =========================================================
CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    compounded_sales_growth TEXT,
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 6. DOCUMENTS
-- =========================================================
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    Year INTEGER NOT NULL,
    Annual_Report TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 7. PROS AND CONS
-- =========================================================
CREATE TABLE IF NOT EXISTS prosandcons (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    pros TEXT,
    cons TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 8. SECTORS
-- =========================================================
CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL UNIQUE,
    broad_sector TEXT,
    sub_sector TEXT,
    index_weight_pct REAL,
    market_cap_category TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 9. STOCK PRICES
-- =========================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    date TEXT NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    adjusted_close REAL,

    UNIQUE (company_id, date),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 10. MARKET CAP
-- =========================================================
CREATE TABLE IF NOT EXISTS market_cap (
    id INTEGER,
    company_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    market_cap_crore REAL,
    enterprise_value_crore REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    ev_ebitda REAL,
    dividend_yield_pct REAL,

    PRIMARY KEY (company_id, year),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 11. FINANCIAL RATIOS
-- =========================================================
CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    net_profit_margin_pct REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct REAL,
    debt_to_equity REAL,
    interest_coverage REAL,
    asset_turnover REAL,
    free_cash_flow_cr REAL,
    capex_cr REAL,
    earnings_per_share REAL,
    book_value_per_share REAL,
    dividend_payout_ratio_pct REAL,
    total_debt_cr REAL,
    cash_from_operations_cr REAL,

    PRIMARY KEY (company_id, year),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- 12. PEER GROUPS
-- =========================================================
CREATE TABLE IF NOT EXISTS peer_groups (
    id INTEGER PRIMARY KEY,
    peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL,
    is_benchmark INTEGER,

    UNIQUE (peer_group_name, company_id),

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_profitandloss_company
ON profitandloss(company_id);

CREATE INDEX IF NOT EXISTS idx_profitandloss_year
ON profitandloss(year);

CREATE INDEX IF NOT EXISTS idx_balancesheet_company
ON balancesheet(company_id);

CREATE INDEX IF NOT EXISTS idx_balancesheet_year
ON balancesheet(year);

CREATE INDEX IF NOT EXISTS idx_cashflow_company
ON cashflow(company_id);

CREATE INDEX IF NOT EXISTS idx_cashflow_year
ON cashflow(year);

CREATE INDEX IF NOT EXISTS idx_documents_company
ON documents(company_id);

CREATE INDEX IF NOT EXISTS idx_documents_year
ON documents(Year);

CREATE INDEX IF NOT EXISTS idx_stock_prices_company
ON stock_prices(company_id);

CREATE INDEX IF NOT EXISTS idx_stock_prices_date
ON stock_prices(date);

CREATE INDEX IF NOT EXISTS idx_market_cap_company
ON market_cap(company_id);

CREATE INDEX IF NOT EXISTS idx_market_cap_year
ON market_cap(year);

CREATE INDEX IF NOT EXISTS idx_financial_ratios_company
ON financial_ratios(company_id);

CREATE INDEX IF NOT EXISTS idx_financial_ratios_year
ON financial_ratios(year);

CREATE INDEX IF NOT EXISTS idx_peer_groups_company
ON peer_groups(company_id);

CREATE INDEX IF NOT EXISTS idx_peer_groups_name
ON peer_groups(peer_group_name);