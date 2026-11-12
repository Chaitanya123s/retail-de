
import argparse
import json
import logging
import sqlite3
import sys
import uuid

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.etl.ingest import ingest_sales_file
from backend.etl.validate import validate_sales
from backend.etl.transform import transform_sales
from backend.etl.load import load_data, initialize_database


def current_time():
    return datetime.now(timezone.utc).isoformat()


def record_ingestion_failure(
    db_path, run_id, source_file, error, started_at
):
    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO etl_runs (
                run_id, source_file, status,
                started_at, ended_at, error_message
            )
            VALUES (?, ?, 'FAILED', ?, ?, ?)
            """,
            (
                run_id,
                str(source_file),
                started_at,
                current_time(),
                str(error),
            ),
        )


def run_pipeline(input_file, db_path):
    run_id = str(uuid.uuid4())
    started_at = current_time()
    input_file = Path(input_file)
    db_path = Path(db_path)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        stream=sys.stderr,
        force=True,
    )

    logger = logging.getLogger("retail_etl")

    def log(message):
        logger.info("[%s] %s", run_id, message)

    load_started = False

    try:
        # Step 1: Ingest
        log("Starting ingestion")

        sales = ingest_sales_file(input_file)

        log(f"Rows ingested: {sales['rows_read']}")

        if sales["extra_columns"]:
            log(f"Extra columns ignored: {sales['extra_columns']}")

        # Step 2: Read reference data
        log("Reading reference files")

        source_dir = input_file.parent

        customers = pd.read_csv(
            source_dir / "customers.csv", dtype=str
        )
        products = pd.read_csv(
            source_dir / "products.csv", dtype=str
        )
        stores = pd.read_csv(
            source_dir / "stores.csv", dtype=str
        )

        # Step 3: Validate
        log("Starting validation")

        valid, rejects = validate_sales(
            sales["dataframe"],
            customers,
            products,
            stores,
        )

        log(
            f"Valid: {len(valid)}, "
            f"Rejected: {len(rejects)}"
        )

        # Step 4: Transform
        log("Starting transformation")

        tables = transform_sales(
            valid,
            customers,
            products,
            stores,
        )

        log(
            f"Fact rows prepared: "
            f"{len(tables['fact_sales'])}"
        )

        # Step 5: Load
        log("Starting SQLite load")
        load_started = True

        result = load_data(
            db_path=db_path,
            tables=tables,
            rejects=rejects,
            source_file=sales["source_file"],
            checksum=sales["checksum"],
            rows_read=sales["rows_read"],
            run_id=run_id,
        )

        result["rows_read"] = sales["rows_read"]
        result["started_at"] = started_at
        result["ended_at"] = current_time()

        log(f"Pipeline finished: {result['status']}")

        return result

    except Exception as error:
        logger.exception(
            "[%s] Pipeline failed", run_id
        )

        # load.py handles its own rollback and failure audit.
        # Earlier failures must be recorded here.
        if not load_started:
            record_ingestion_failure(
                db_path,
                run_id,
                input_file,
                error,
                started_at,
            )

        return {
            "run_id": run_id,
            "status": "FAILED",
            "rows_read": 0,
            "rows_loaded": 0,
            "rows_rejected": 0,
            "rows_skipped": 0,
            "error_message": str(error),
            "started_at": started_at,
            "ended_at": current_time(),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Retail Data Engineering ETL Pipeline"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to sales_lines.csv",
    )

    parser.add_argument(
        "--db",
        default="data/output/retail.db",
        help="SQLite database path",
    )

    args = parser.parse_args()

    result = run_pipeline(args.input, args.db)

    print(json.dumps(result, indent=2))

    if result["status"] == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
