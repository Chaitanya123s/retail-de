# Retail ETL Reconciliation Report

Database: `data\output\retail_cli_test.db`
Source: `data\sample\sales_lines.csv`
Run ID: `9468f770-43fa-4ea5-9ec0-311aeb337515`

## Row counts and revenue

- Input records: 105
- Loaded records: 100
- Rejected records: 5
- Skipped records: 0
- Current fact records: 100
- Expected revenue: 1365694.00
- Actual revenue: 1365694.00
- Duplicate keys: 0
- Foreign key violations: 0

## Validation checks

| Check | Result |
|---|---|
| Source row reconciliation | PASS |
| Source input count | PASS |
| Fact row count | PASS |
| Revenue reconciliation | PASS |
| Reject count | PASS |
| Reject reasons | PASS |
| No duplicate business keys | PASS |
| No foreign key violations | PASS |
| Reject traceability | PASS |

## Overall result: PASS

Note: This report compares the current database against the original sample. For multi-batch loads, reconciliation should be scoped to each run and its resulting changes.
