
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    region TEXT
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY,
    product_id TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS dim_store (
    store_key INTEGER PRIMARY KEY,
    store_id TEXT NOT NULL UNIQUE,
    store_name TEXT NOT NULL,
    region TEXT
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    file_checksum TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    rows_read INTEGER DEFAULT 0,
    rows_loaded INTEGER DEFAULT 0,
    rows_rejected INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key INTEGER PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    store_key INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    sales_amount REAL NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,

    UNIQUE(transaction_id, line_number),
    FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY(customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY(product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY(store_key) REFERENCES dim_store(store_key),
    FOREIGN KEY(run_id) REFERENCES etl_runs(run_id)
);

CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    reject_reason TEXT NOT NULL,
    raw_record TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES etl_runs(run_id)
);
