
import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from backend.etl.ingest import ingest_sales_file
from backend.etl.validate import validate_sales
from backend.etl.transform import transform_sales


def reconcile(db_path, input_file, report_path):
    db_path = Path(db_path)
    input_file = Path(input_file)
    report_path = Path(report_path)

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Recalculate the expected results from source data.
    sales = ingest_sales_file(input_file)
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

    valid, rejects = validate_sales(
        sales["dataframe"], customers, products, stores
    )
    tables = transform_sales(valid, customers, products, stores)

    expected_count = len(valid)
    expected_rejects = len(rejects)
    expected_revenue = round(
        float(tables["fact_sales"]["sales_amount"].sum()), 2
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        run = conn.execute(
            """
            SELECT run_id, rows_read, rows_loaded,
                   rows_rejected, rows_skipped
            FROM etl_runs
            WHERE file_checksum = ? AND status = 'SUCCESS'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (sales["checksum"],),
        ).fetchone()

        if run is None:
            raise ValueError(
                "No successful initial load for this source checksum"
            )

        run_id, read_count, loaded, rejected, skipped = run

        fact_count, actual_revenue = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(sales_amount), 0)
            FROM fact_sales
            """
        ).fetchone()

        actual_revenue = round(actual_revenue, 2)

        duplicate_count = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT transaction_id, line_number
                FROM fact_sales
                GROUP BY transaction_id, line_number
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        foreign_key_errors = len(
            conn.execute("PRAGMA foreign_key_check").fetchall()
        )

        reject_count = conn.execute(
            """
            SELECT COUNT(*) FROM rejected_records
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()[0]

        missing_reject_details = conn.execute(
            """
            SELECT COUNT(*) FROM rejected_records
            WHERE run_id = ?
              AND (
                  reject_reason IS NULL
                  OR TRIM(reject_reason) = ''
                  OR source_row_number IS NULL
                  OR source_row_number < 2
                  OR raw_record IS NULL
              )
            """,
            (run_id,),
        ).fetchone()[0]

        actual_reasons = dict(conn.execute(
            """
            SELECT reject_reason, COUNT(*)
            FROM rejected_records
            WHERE run_id = ?
            GROUP BY reject_reason
            """,
            (run_id,),
        ).fetchall())

    expected_reasons = (
        rejects["reject_reason"].value_counts().to_dict()
    )

    checks = {
        "Source row reconciliation":
            read_count == loaded + rejected + skipped,
        "Source input count":
            read_count == len(sales["dataframe"]),
        "Fact row count":
            fact_count == expected_count,
        "Revenue reconciliation":
            abs(actual_revenue - expected_revenue) < 0.01,
        "Reject count":
            reject_count == expected_rejects == rejected,
        "Reject reasons":
            actual_reasons == expected_reasons,
        "No duplicate business keys":
            duplicate_count == 0,
        "No foreign key violations":
            foreign_key_errors == 0,
        "Reject traceability":
            missing_reject_details == 0,
    }

    passed = all(checks.values())

    lines = [
        "# Retail ETL Reconciliation Report",
        "",
        f"Database: `{db_path}`",
        f"Source: `{input_file}`",
        f"Run ID: `{run_id}`",
        "",
        "## Row counts and revenue",
        "",
        f"- Input records: {read_count}",
        f"- Loaded records: {loaded}",
        f"- Rejected records: {rejected}",
        f"- Skipped records: {skipped}",
        f"- Current fact records: {fact_count}",
        f"- Expected revenue: {expected_revenue:.2f}",
        f"- Actual revenue: {actual_revenue:.2f}",
        f"- Duplicate keys: {duplicate_count}",
        f"- Foreign key violations: {foreign_key_errors}",
        "",
        "## Validation checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]

    for name, success in checks.items():
        lines.append(
            f"| {name} | {'PASS' if success else 'FAIL'} |"
        )

    lines.extend([
        "",
        f"## Overall result: {'PASS' if passed else 'FAIL'}",
        "",
        "Note: This report compares the current database "
        "against the original sample. For multi-batch "
        "loads, reconciliation should be scoped to each "
        "run and its resulting changes.",
    ])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(f"Report saved: {report_path}")
    print(f"Checks passed: {sum(checks.values())}/{len(checks)}")
    print(f"Overall result: {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db", default="data/output/retail.db"
    )
    parser.add_argument(
        "--input", default="data/sample/sales_lines.csv"
    )
    parser.add_argument(
        "--report",
        default="data/output/reconciliation_report.md"
    )
    args = parser.parse_args()

    if not reconcile(args.db, args.input, args.report):
        raise SystemExit(1)
