
# Retail Data Engineering — Design Decisions

## 1. Business Problem

Retail transaction data can contain missing values,
duplicate events, invalid references and inconsistent
data types.

These issues can produce inaccurate revenue reports.

Our solution validates transactions and publishes clean,
reconciled analytical data into SQLite.

## 2. Architecture

CSV Sources
    |
    v
Ingestion
    |
    v
Validation ----> Rejected Records
    |
    v
Transformation
    |
    v
SQLite Star Schema
    |
    +--> SQL Analytics
    +--> Reconciliation

The CLI orchestrator is backend/etl/run.py.

## 3. Fact Grain

One row per unique:

(transaction_id, line_number)

This grain supports orders containing multiple products
without incorrectly merging separate order lines.

## 4. Dimensions

- dim_customer
- dim_product
- dim_store
- dim_date

These dimensions support customer, product, store
and time-based sales analytics.

## 5. Surrogate Keys

Customer, product and store keys are generated
deterministically using the first 15 hexadecimal
characters of an MD5 hash.

Fact keys use transaction_id and line_number.

Date keys use YYYYMMDD format.

This approach produces reproducible keys without
requiring a centralized key-generation service.

Hash collisions remain theoretically possible.

## 6. Measures

Primary measure:

sales_amount = quantity * unit_price

Additional measures:
- quantity
- unit_price

SQLite REAL is used for simplicity. Production financial
systems should use exact decimal or integer-cent values.

## 7. Validation Policy

- Missing required column: fail ingestion
- Extra column: detect and ignore
- Empty input: SUCCESS_EMPTY
- Missing required value: reject
- Invalid type: reject
- Quantity <= 0: reject
- Negative unit price: reject
- Duplicate business key: keep first eligible row
- Invalid customer/product/store reference: reject

Rejected records retain the original source row number,
reason code and raw JSON record.

## 8. Idempotency

The pipeline records a SHA-256 checksum of the sales
input file.

Successfully processed files are not reloaded
when the same checksum is encountered.

Fact records are uniquely identified by:

(transaction_id, line_number)

Incoming updates are applied only when updated_at is
greater than or equal to the stored timestamp.

## 9. Recovery

Database loading uses SQLite transactions.

If loading fails, changes are rolled back.

A separate failure record is written to etl_runs.

A failed run can be retried after correcting the cause.

The system does not provide automatic scheduling
or an external retry queue.

## 10. Monitoring

Every pipeline execution has a unique run_id.

The etl_runs table records:
- Status
- Input file
- File checksum
- Start and end timestamps
- Rows read
- Rows loaded
- Rows rejected
- Rows skipped
- Error details

Zabbix Agent 2 is installed in the hackathon environment,
but custom monitoring of ETL metrics is not implemented.

## 11. Testing

Pytest uses temporary SQLite databases and synthetic data.

Verified:
- 23 automated tests passed
- 9 reconciliation checks passed
- Duplicate-file rerun handled correctly
- Transaction rollback and retry verified
- Late-arriving older updates do not overwrite newer facts

## 12. Performance

Benchmark size: 100,005 source records.

Baseline total runtime: 104.839 seconds.

Optimized total runtime: 4.942 seconds.

Overall speedup: approximately 21.2x.

The primary optimization replaced row-by-row Pandas
validation with vectorized column operations.

## 13. Trade-offs

SQLite:
Simple and reproducible, but not designed for
large multi-user analytical workloads.

Pandas:
Easy to maintain and efficient for moderate datasets,
but in-memory processing limits scalability.

MD5-derived keys:
Stable and deterministic, but not collision-free.

Type 1 dimensions:
Simple to implement, but historical attribute changes
are overwritten.

File checksum idempotency:
Prevents exact sales-file reprocessing, but does not
account for independently changing reference files.

## 14. Future Improvements

- PostgreSQL warehouse
- Historical SCD Type 2 dimensions
- Incremental and streaming ingestion
- Stronger source schema validation
- Multi-batch reconciliation
- Exact monetary arithmetic
- External orchestration
- Zabbix ETL monitoring integration
- FastAPI and Streamlit interfaces
