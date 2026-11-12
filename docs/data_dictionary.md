
# Retail Data Warehouse — Data Dictionary

## 1. Overview

This project uses SQLite and a star schema to store
validated retail sales transactions.

Fact grain: One row per (transaction_id, line_number).

Database tables:
- dim_customer
- dim_product
- dim_store
- dim_date
- fact_sales
- etl_runs
- rejected_records

## 2. dim_customer

| Column | Type | Constraint | Description |
|---|---|---|---|
| customer_key | INTEGER | PK | Deterministic surrogate key |
| customer_id | TEXT | NOT NULL, UNIQUE | Source customer ID |
| customer_name | TEXT | NOT NULL | Customer name |
| region | TEXT | Nullable | Customer region |

## 3. dim_product

| Column | Type | Constraint | Description |
|---|---|---|---|
| product_key | INTEGER | PK | Deterministic surrogate key |
| product_id | TEXT | NOT NULL, UNIQUE | Source product ID |
| product_name | TEXT | NOT NULL | Product name |
| category | TEXT | Nullable | Product category |

## 4. dim_store

| Column | Type | Constraint | Description |
|---|---|---|---|
| store_key | INTEGER | PK | Deterministic surrogate key |
| store_id | TEXT | NOT NULL, UNIQUE | Source store ID |
| store_name | TEXT | NOT NULL | Store name |
| region | TEXT | Nullable | Store region |

## 5. dim_date

| Column | Type | Constraint | Description |
|---|---|---|---|
| date_key | INTEGER | PK | Date in YYYYMMDD format |
| full_date | TEXT | NOT NULL, UNIQUE | ISO date |
| year | INTEGER | NOT NULL | Calendar year |
| month | INTEGER | NOT NULL | Calendar month |
| day | INTEGER | NOT NULL | Calendar day |

## 6. fact_sales

Grain: One row per unique transaction line.

| Column | Type | Constraint | Description |
|---|---|---|---|
| sales_key | INTEGER | PK | Deterministic fact key |
| transaction_id | TEXT | NOT NULL | Source transaction ID |
| line_number | INTEGER | NOT NULL | Transaction line number |
| date_key | INTEGER | FK, NOT NULL | References dim_date |
| customer_key | INTEGER | FK, NOT NULL | References dim_customer |
| product_key | INTEGER | FK, NOT NULL | References dim_product |
| store_key | INTEGER | FK, NOT NULL | References dim_store |
| quantity | INTEGER | NOT NULL, > 0 | Units sold |
| unit_price | REAL | NOT NULL, >= 0 | Price per unit |
| sales_amount | REAL | NOT NULL | quantity * unit_price |
| updated_at | TEXT | NOT NULL | Source update timestamp |
| run_id | TEXT | FK, NOT NULL | References etl_runs |
| source_file | TEXT | NOT NULL | Originating CSV file |

Unique business key:
(transaction_id, line_number).

## 7. etl_runs

| Column | Type | Constraint | Description |
|---|---|---|---|
| run_id | TEXT | PK | Unique execution ID |
| source_file | TEXT | NOT NULL | Input file path |
| file_checksum | TEXT | Nullable | SHA-256 checksum |
| status | TEXT | NOT NULL | Pipeline execution status |
| started_at | TEXT | NOT NULL | UTC start timestamp |
| ended_at | TEXT | Nullable | UTC end timestamp |
| rows_read | INTEGER | Default 0 | Input row count |
| rows_loaded | INTEGER | Default 0 | Inserted or updated facts |
| rows_rejected | INTEGER | Default 0 | Rejected source records |
| rows_skipped | INTEGER | Default 0 | Skipped source records |
| error_message | TEXT | Nullable | Failure details |

Statuses:
- RUNNING
- SUCCESS
- SUCCESS_EMPTY
- SKIPPED_DUPLICATE_FILE
- FAILED

## 8. rejected_records

| Column | Type | Constraint | Description |
|---|---|---|---|
| reject_id | INTEGER | PK, AUTOINCREMENT | Reject identifier |
| run_id | TEXT | FK, NOT NULL | References etl_runs |
| source_file | TEXT | NOT NULL | Original CSV path |
| source_row_number | INTEGER | NOT NULL | CSV row number including header |
| reject_reason | TEXT | NOT NULL | Validation failure code |
| raw_record | TEXT | NOT NULL | Original record as JSON |

## 9. Validation rules

- Required fields cannot be null or blank.
- Quantity must be positive.
- Unit price must be nonnegative.
- Customer, product and store references must exist.
- Duplicate transaction keys are rejected.
- Missing required columns fail ingestion.
- Extra columns are detected and ignored.
- Older updated_at values cannot overwrite newer facts.

## 10. Design assumptions and limitations

- All input data is synthetic.
- Dates use ISO-8601 formatting.
- SQLite is used for local reproducibility.
- Dimension attributes are overwritten (Type 1).
- Historical dimension versions (SCD Type 2) are not implemented.
- Monetary fields use SQLite REAL; integer cents or DECIMAL
  should be used for production financial applications.
- Hash-based surrogate keys have a theoretical collision risk.
- Reconciliation is currently designed for a single input batch.
