# Baseline benchmark

Input rows: 100005
Loaded rows: 100000
Rejected rows: 5

Ingestion: 0.119 seconds
Validation: 100.836 seconds
Transformation: 1.513 seconds
Loading: 2.371 seconds
Total: 104.839 seconds
Throughput: 953.89 rows/second

Bottleneck: row-by-row validation using pandas iterrows().
