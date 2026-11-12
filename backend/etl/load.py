
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def initialize_database(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_data(
    db_path,
    tables,
    rejects,
    source_file,
    checksum,
    rows_read,
    run_id=None,
):
    """Load one ETL batch using a SQLite transaction."""

    db_path = Path(db_path)
    initialize_database(db_path)

    run_id = run_id or str(uuid.uuid4())
    started_at = now_iso()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Prevent reprocessing a successfully loaded file.
        previous = conn.execute(
            """
            SELECT run_id FROM etl_runs
            WHERE file_checksum = ?
              AND status IN ('SUCCESS', 'SUCCESS_EMPTY')
            LIMIT 1
            """,
            (checksum,),
        ).fetchone()

        if previous:
            status = "SKIPPED_DUPLICATE_FILE"

            conn.execute(
                """
                INSERT INTO etl_runs
                (run_id, source_file, file_checksum, status,
                 started_at, ended_at, rows_read,
                 rows_loaded, rows_rejected, rows_skipped)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (run_id, str(source_file), checksum, status,
                 started_at, now_iso(), rows_read, rows_read),
            )
            conn.commit()

            return {
                "run_id": run_id,
                "status": status,
                "rows_loaded": 0,
                "rows_rejected": 0,
                "rows_skipped": rows_read,
            }

        conn.execute("BEGIN")

        conn.execute(
            """
            INSERT INTO etl_runs
            (run_id, source_file, file_checksum, status, started_at)
            VALUES (?, ?, ?, 'RUNNING', ?)
            """,
            (run_id, str(source_file), checksum, started_at),
        )

        # Insert or update dimensions.
        dimension_columns = {
            "dim_customer": [
                "customer_key", "customer_id", "customer_name", "region"
            ],
            "dim_product": [
                "product_key", "product_id", "product_name", "category"
            ],
            "dim_store": [
                "store_key", "store_id", "store_name", "region"
            ],
            "dim_date": [
                "date_key", "full_date", "year", "month", "day"
            ],
        }

        for table_name, columns in dimension_columns.items():
            frame = tables[table_name]
            placeholders = ", ".join(["?"] * len(columns))
            column_names = ", ".join(columns)
            updates = ", ".join(
                f"{c} = excluded.{c}" for c in columns[1:]
            )

            sql = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT({columns[0]})
                DO UPDATE SET {updates}
            """

            conn.executemany(
                sql,
                list(frame[columns].itertuples(index=False, name=None)),
            )

        # Upsert facts, retaining newer transaction versions.
        fact_sql = """
            INSERT INTO fact_sales (
                sales_key, transaction_id, line_number, date_key,
                customer_key, product_key, store_key, quantity,
                unit_price, sales_amount, updated_at, run_id, source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id, line_number)
            DO UPDATE SET
                date_key = excluded.date_key,
                customer_key = excluded.customer_key,
                product_key = excluded.product_key,
                store_key = excluded.store_key,
                quantity = excluded.quantity,
                unit_price = excluded.unit_price,
                sales_amount = excluded.sales_amount,
                updated_at = excluded.updated_at,
                run_id = excluded.run_id,
                source_file = excluded.source_file
            WHERE excluded.updated_at >= fact_sales.updated_at
        """

        loaded = 0
        skipped = 0

        for row in tables["fact_sales"].itertuples(index=False):
            values = (
                row.sales_key,
                row.transaction_id,
                int(row.line_number),
                int(row.date_key),
                int(row.customer_key),
                int(row.product_key),
                int(row.store_key),
                int(row.quantity),
                float(row.unit_price),
                float(row.sales_amount),
                row.updated_at,
                run_id,
                str(source_file),
            )

            before = conn.total_changes
            conn.execute(fact_sql, values)

            if conn.total_changes > before:
                loaded += 1
            else:
                skipped += 1

        # Save invalid records for investigation.
        reject_rows = [
            (
                run_id,
                str(source_file),
                int(row.source_row_number),
                row.reject_reason,
                row.raw_record,
            )
            for row in rejects.itertuples(index=False)
        ]

        conn.executemany(
            """
            INSERT INTO rejected_records
            (run_id, source_file, source_row_number,
             reject_reason, raw_record)
            VALUES (?, ?, ?, ?, ?)
            """,
            reject_rows,
        )

        rejected_count = len(reject_rows)

        if rows_read != loaded + rejected_count + skipped:
            raise ValueError("Row count reconciliation failed")

        status = "SUCCESS_EMPTY" if rows_read == 0 else "SUCCESS"

        conn.execute(
            """
            UPDATE etl_runs
            SET status = ?, ended_at = ?, rows_read = ?,
                rows_loaded = ?, rows_rejected = ?, rows_skipped = ?
            WHERE run_id = ?
            """,
            (
                status, now_iso(), rows_read, loaded,
                rejected_count, skipped, run_id,
            ),
        )

        conn.commit()

        return {
            "run_id": run_id,
            "status": status,
            "rows_loaded": loaded,
            "rows_rejected": rejected_count,
            "rows_skipped": skipped,
        }

    except Exception as error:
        conn.rollback()

        # Record failures separately so they survive rollback.
        conn.execute(
            """
            INSERT INTO etl_runs
            (run_id, source_file, file_checksum, status,
             started_at, ended_at, rows_read, error_message)
            VALUES (?, ?, ?, 'FAILED', ?, ?, ?, ?)
            """,
            (
                run_id, str(source_file), checksum,
                started_at, now_iso(), rows_read, str(error),
            ),
        )
        conn.commit()
        raise

    finally:
        conn.close()
