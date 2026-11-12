
import time
import sqlite3
from pathlib import Path

import pandas as pd

from backend.etl.ingest import ingest_sales_file
from backend.etl.validate import validate_sales
from backend.etl.transform import transform_sales
from backend.etl.load import load_data


def benchmark():
    base = Path("data/benchmark")
    db_path = Path("data/output/benchmark.db")

    # Use a fresh database for reproducible timing.
    if db_path.exists():
        raise FileExistsError(
            f"{db_path} already exists. "
            "Move or delete it before running a fresh benchmark."
        )

    timings = {}

    start = time.perf_counter()

    # Ingestion
    t = time.perf_counter()
    sales = ingest_sales_file(base / "sales_lines.csv")
    customers = pd.read_csv(base / "customers.csv", dtype=str)
    products = pd.read_csv(base / "products.csv", dtype=str)
    stores = pd.read_csv(base / "stores.csv", dtype=str)
    timings["ingestion"] = time.perf_counter() - t

    # Validation
    t = time.perf_counter()
    valid, rejects = validate_sales(
        sales["dataframe"], customers, products, stores
    )
    timings["validation"] = time.perf_counter() - t

    # Transformation
    t = time.perf_counter()
    tables = transform_sales(
        valid, customers, products, stores
    )
    timings["transformation"] = time.perf_counter() - t

    # SQLite loading
    t = time.perf_counter()
    result = load_data(
        db_path=db_path,
        tables=tables,
        rejects=rejects,
        source_file=sales["source_file"],
        checksum=sales["checksum"],
        rows_read=sales["rows_read"],
    )
    timings["loading"] = time.perf_counter() - t

    timings["total"] = time.perf_counter() - start

    with sqlite3.connect(db_path) as conn:
        actual_rows = conn.execute(
            "SELECT COUNT(*) FROM fact_sales"
        ).fetchone()[0]

    print("\n--- BENCHMARK RESULTS ---")
    print("Status:", result["status"])
    print("Input rows:", sales["rows_read"])
    print("Loaded rows:", result["rows_loaded"])
    print("Rejected rows:", result["rows_rejected"])
    print("Fact rows in database:", actual_rows)

    for stage, seconds in timings.items():
        print(f"{stage}: {seconds:.3f} seconds")

    throughput = (
        sales["rows_read"] / timings["total"]
        if timings["total"] > 0 else 0
    )

    print(f"Throughput: {throughput:.2f} rows/second")

    if result["status"] != "SUCCESS":
        raise RuntimeError("Benchmark pipeline did not succeed")

    if actual_rows != 100000:
        raise AssertionError("Unexpected fact row count")

    if result["rows_rejected"] != 5:
        raise AssertionError("Unexpected rejected row count")


if __name__ == "__main__":
    benchmark()
