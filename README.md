
# Retail Sales Data Engineering Pipeline

## 1. Project Overview

A Python-based Data Engineering pipeline that processes retail sales
transactions, validates data quality, builds a dimensional star schema,
and publishes trusted analytical data into SQLite.

The solution includes automated testing, idempotency, rejected-record
tracking, reconciliation, and performance benchmarking.

## 2. Business Problem

Retail organizations generate transaction data from stores, billing
systems, and online platforms.

Raw data may contain:
- Duplicate transactions
- Missing customer information
- Invalid product or store references
- Incorrect quantities or prices
- Out-of-order transaction updates

These problems can produce inaccurate revenue reports and unreliable
business decisions.

## 3. Proposed Solution

Build an Extract, Validate, Transform, Load (ETL) pipeline that:

1. Ingests source CSV files.
2. Validates transaction and reference data.
3. Quarantines invalid records with rejection reasons.
4. Generates deterministic surrogate keys.
5. Creates sales facts and dimension tables.
6. Loads results into SQLite transactionally.
7. Records execution status, row counts and failures.
8. Supports safe reruns and late-arriving updates.
9. Provides SQL analytics and reconciliation reports.

## 4. Technology Stack

- Python 3.12
- Pandas
- SQLite
- Pytest
- Git
- PowerShell / Windows
- Zabbix Agent 2 installed in hackathon environment

Zabbix monitoring integration is not currently implemented.

## 5. Architecture

CSV Source Files
       |
       v
ingest.py
- Read CSV
- Validate schema
- SHA-256 checksum
       |
       v
validate.py
- Required fields
- Data types
- Duplicate detection
- Reference checks
       |
       +----> Rejected records
       |
       v
transform.py
- Type conversion
- Calculate sales revenue
- Generate surrogate keys
- Build fact and dimension tables
       |
       v
load.py
- SQLite transaction
- Dimension upserts
- Fact upserts
- Run audit and reject storage
       |
       v
SQLite Data Warehouse
       |
       +----> SQL analytics
       +----> Reconciliation report

run.py orchestrates the complete pipeline.

## 6. Data Model

Fact table:
- fact_sales

Dimensions:
- dim_customer
- dim_product
- dim_store
- dim_date

Operational tables:
- etl_runs
- rejected_records

Fact grain:
One row per (transaction_id, line_number).

Sales measure:
sales_amount = quantity * unit_price

Surrogate keys:
First 15 hexadecimal characters of MD5 business-key hashes,
converted into integers.

Date key:
YYYYMMDD format.

## 7. Project Structure

retail-de/
    backend/
        etl/
            ingest.py
            validate.py
            transform.py
            load.py
            run.py
        reconcile.py

    database/
        schema.sql
        analytics.sql

    scripts/
        generate_data.py
        benchmark.py

    data/
        sample/
        expected/
        output/

    tests/
        test_pipeline.py

    docs/
        data_dictionary.md
        test_results.txt
        benchmark_baseline.md
        benchmark_optimized.md

    README.md
    requirements.txt
    .gitignore

## 8. Setup Instructions

Requirements:
- Windows with Python 3.12
- Git

Open PowerShell in the project root.

Create virtual environment:

    python -m venv .venv

Install dependencies without requiring activation:

    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Alternatively, activate the environment and use python directly.

SQLite is included with Python.

## 9. Generate Sample Data

    python scripts/generate_data.py --output data/sample --count 100

Expected:
- 100 normal sales records
- 5 deliberately invalid records
- 105 total sales rows

Reference data:
- 100 customers
- 50 products
- 10 stores

Random seed: 42.

## 10. Execute ETL

    python -m backend.etl.run --input data/sample/sales_lines.csv --db data/output/retail.db

Expected first-run results with a fresh database:
- Status: SUCCESS
- Rows read: 105
- Rows loaded: 100
- Rows rejected: 5

The pipeline prints run logs and a JSON summary.

## 11. Idempotency

The loader records SHA-256 checksums for successfully processed files.

When the same input is processed again against the same database,
the load is skipped.

Expected status:

    SKIPPED_DUPLICATE_FILE

Fact upserts use:
(transaction_id, line_number)

An incoming fact replaces the stored record only when its updated_at
is greater than or equal to the stored timestamp.

## 12. Failure Handling and Recovery

Database loading uses transactions.

If loading fails:
- Database changes are rolled back.
- The failure is recorded in etl_runs.
- The error message is retained.

A failed input can be corrected and retried.

Reruns with an already successful file checksum are skipped.

For backfills, generate or supply the required historical source files
and execute the pipeline against the target database.

The design does not currently implement a full production scheduler,
multi-source historical replay manager, or automatic retry service.

## 13. Automated Testing

Run:

    python -m pytest tests/test_pipeline.py -v

Verified result:
- 23 tests passed
- 0 tests failed

Coverage includes:
- Happy path
- Empty input
- Malformed records
- Missing fields
- Duplicate transactions
- Schema changes
- Invalid references
- Same-file reruns
- Partial failure and retry
- Late-arriving older records
- Boundary values
- Rejection reconciliation

Evidence:
docs/test_results.txt

## 14. Reconciliation

Run:

    python -m backend.reconcile --db data/output/retail.db --input data/sample/sales_lines.csv

Verified on the original sample:
- 9/9 reconciliation checks passed
- 100 sales rows
- 5 rejected rows
- Total revenue: 1365694.00

Checks include:
- Input and output row counts
- Revenue consistency
- Duplicate business keys
- Foreign key integrity
- Rejected record traceability

Report:
data/output/reconciliation_report.md

The reconciliation report currently targets a single source batch.

## 15. Analytical Queries

SQL file:
database/analytics.sql

Includes:
- Total revenue
- Revenue by product category
- Monthly revenue
- Top 10 products
- Sales by store region
- Top customers
- Rejection reasons
- ETL run history

Verified sample revenue by category:
- Grocery: 489971.00
- Electronics: 445070.00
- Clothing: 430653.00

Total: 1365694.00

## 16. Performance Benchmark

Generate benchmark data:

    python scripts/generate_data.py --output data/benchmark --count 100000

Run:

    python -m scripts.benchmark

The benchmark requires a fresh output database.
If data/output/benchmark.db already exists, move it to a backup
location before rerunning.

Measured dataset:
- Input records: 100005
- Loaded: 100000
- Rejected: 5

Baseline:
- Validation: 100.836 seconds
- Total: 104.839 seconds
- Throughput: 953.89 rows/second

Optimized:
- Validation: 0.359 seconds
- Total: 4.942 seconds
- Throughput: 20236.79 rows/second

Measured improvements:
- Overall speedup: approximately 21.2x
- Validation speedup: approximately 280.9x
- Total runtime reduction: approximately 95.3%

Optimization:
Replaced row-by-row Pandas validation using iterrows()
with vectorized column operations.

Performance varies by machine and system load.

## 17. Data Quality and Naming

- snake_case names for tables, columns and modules
- ISO-8601 dates and timestamps
- Unique run_id for pipeline executions
- source_file retained for lineage
- Rejects include a reason and original row number
- Primary keys and foreign keys defined in SQLite
- Synthetic data used for reproducibility

## 18. Assumptions and Limitations

- SQLite is used for local deployment.
- Customer/product/store dimensions use Type 1 updates.
- Historical dimension versioning (SCD Type 2) is not implemented.
- Monetary values are stored using SQLite REAL.
- Production financial systems should prefer integer minor units
  or decimal arithmetic.
- Hash-derived surrogate keys have theoretical collision risk.
- Validation assumes reference datasets have valid structures.
- File checksums cover the sales CSV, not an entire reference-data
  snapshot.
- Late-arriving fact rows use timestamp-based last-write rules.
- Same-file success checking is not a substitute for complete
  transactional event history.
- Performance measurements are from a local benchmark.
- API and frontend are optional and not part of the verified
  core implementation.
- Zabbix Agent 2 is installed, but custom ETL monitoring
  metrics have not been integrated.

## 19. Future Improvements

- PostgreSQL or another scalable warehouse
- Streaming or chunked input ingestion
- Complete reference-data validation
- Stronger financial precision
- SCD Type 2 history
- External orchestration and retry scheduling
- FastAPI endpoints
- Streamlit dashboard
- Zabbix ETL monitoring integration
- Multi-batch reconciliation
- More comprehensive edge-case and scalability testing

## 20. Execution Evidence

Verified during development:
- End-to-end ETL: SUCCESS
- Sample load: 100 accepted, 5 rejected
- Automated tests: 23 passed
- Reconciliation checks: 9 passed
- Benchmark: 100000 fact rows loaded
- Performance improvement: 21.2x

See docs/ for testing and benchmark evidence.

## 21. Security and Submission

- Do not commit credentials or secrets.
- Do not commit local SQLite databases.
- Generated benchmark data is excluded from Git.
- Submit through a public GitHub repository.
- Provide repository access only to authorized evaluators.

