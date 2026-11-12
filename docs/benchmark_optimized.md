# ETL Performance Optimization Report

## Dataset
- Input: 100,005 transactions
- Valid: 100,000
- Rejected: 5

## Performance Comparison

| Metric | Baseline | Optimized |
|---|---:|---:|
| Ingestion | 0.119s | 0.266s |
| Validation | 100.836s | 0.359s |
| Transformation | 1.513s | 1.752s |
| Loading | 2.371s | 2.564s |
| Total runtime | 104.839s | 4.942s |
| Throughput | 953.89 rows/s | 20236.79 rows/s |

## Results
- Overall speedup: 21.2x
- Validation speedup: 280.9x
- Runtime reduction: 95.3%
- Automated tests: 23 passed

## Optimization
Replaced row-by-row Pandas validation using
iterrows() with vectorized column operations.

## Limitations
Results were measured on a local Windows machine.
Runtime may vary by hardware and system load.
Large-scale performance and additional edge cases
require further testing.
