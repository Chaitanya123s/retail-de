
import json
import sqlite3

import pandas as pd
import pytest

from scripts.generate_data import generate
from backend.etl.ingest import ingest_sales_file
from backend.etl.validate import validate_sales
from backend.etl.transform import transform_sales
from backend.etl.load import load_data
from backend.etl.run import run_pipeline


@pytest.fixture
def sample_data(tmp_path):
    """Create fresh reproducible test data."""
    generate(tmp_path, 100)
    return tmp_path


def prepare_data(folder):
    """Run ingestion, validation and transformation."""
    sales = ingest_sales_file(folder / "sales_lines.csv")

    customers = pd.read_csv(folder / "customers.csv", dtype=str)
    products = pd.read_csv(folder / "products.csv", dtype=str)
    stores = pd.read_csv(folder / "stores.csv", dtype=str)

    valid, rejects = validate_sales(
        sales["dataframe"], customers, products, stores
    )

    tables = transform_sales(valid, customers, products, stores)

    return sales, valid, rejects, tables


def test_happy_path(sample_data):
    db = sample_data / "retail.db"

    result = run_pipeline(sample_data / "sales_lines.csv", db)

    assert result["status"] == "SUCCESS"
    assert result["rows_read"] == 105
    assert result["rows_loaded"] == 100
    assert result["rows_rejected"] == 5

    with sqlite3.connect(db) as conn:
        count, revenue = conn.execute(
            "SELECT COUNT(*), SUM(sales_amount) FROM fact_sales"
        ).fetchone()

        assert count == 100
        assert revenue == pytest.approx(1365694.0)


def test_empty_input(sample_data):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path).iloc[0:0]
    df.to_csv(path, index=False)

    result = run_pipeline(path, sample_data / "empty.db")

    assert result["status"] == "SUCCESS_EMPTY"
    assert result["rows_loaded"] == 0
    assert result["rows_rejected"] == 0


def test_malformed_quantity(sample_data):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df.loc[0, "quantity"] = "abc"
    df.to_csv(path, index=False)

    _, _, rejects, _ = prepare_data(sample_data)

    assert "INVALID_TYPE" in rejects["reject_reason"].values


@pytest.mark.parametrize(
    "column",
    [
        "transaction_id",
        "line_number",
        "date",
        "customer_id",
        "product_id",
        "store_id",
        "quantity",
        "unit_price",
        "updated_at",
    ],
)
def test_missing_required_values(sample_data, column):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df.loc[0, column] = ""
    df.to_csv(path, index=False)

    sales = ingest_sales_file(path)

    customers = pd.read_csv(
        sample_data / "customers.csv", dtype=str
    )
    products = pd.read_csv(
        sample_data / "products.csv", dtype=str
    )
    stores = pd.read_csv(
        sample_data / "stores.csv", dtype=str
    )

    _, rejects = validate_sales(
        sales["dataframe"], customers, products, stores
    )

    assert "MISSING_REQUIRED_FIELD" in rejects["reject_reason"].values


def test_duplicate_transaction(sample_data):
    _, valid, rejects, _ = prepare_data(sample_data)

    assert len(valid) == 100
    assert (
        rejects["reject_reason"] == "DUPLICATE_IN_BATCH"
    ).sum() == 1


def test_same_file_rerun(sample_data):
    db = sample_data / "retail.db"
    path = sample_data / "sales_lines.csv"

    first = run_pipeline(path, db)
    second = run_pipeline(path, db)

    assert first["status"] == "SUCCESS"
    assert second["status"] == "SKIPPED_DUPLICATE_FILE"
    assert second["rows_loaded"] == 0
    assert second["rows_skipped"] == 105

    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM fact_sales"
        ).fetchone()[0] == 100

        assert conn.execute(
            "SELECT COUNT(*) FROM rejected_records"
        ).fetchone()[0] == 5


def test_missing_schema_column(sample_data):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df.drop(columns=["product_id"]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        ingest_sales_file(path)


def test_extra_schema_column(sample_data):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df["unexpected_column"] = "extra"
    df.to_csv(path, index=False)

    result = ingest_sales_file(path)

    assert "unexpected_column" in result["extra_columns"]
    assert "unexpected_column" not in result["dataframe"].columns


@pytest.mark.parametrize(
    "column,invalid_id,expected_reason",
    [
        ("customer_id", "C9999", "INVALID_CUSTOMER_REF"),
        ("product_id", "P9999", "INVALID_PRODUCT_REF"),
        ("store_id", "S9999", "INVALID_STORE_REF"),
    ],
)
def test_invalid_reference(
    sample_data, column, invalid_id, expected_reason
):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df.loc[0, column] = invalid_id
    df.to_csv(path, index=False)

    _, _, rejects, _ = prepare_data(sample_data)

    assert expected_reason in rejects["reject_reason"].values


def test_rejection_reconciliation(sample_data):
    sales, valid, rejects, _ = prepare_data(sample_data)

    assert len(sales["dataframe"]) == len(valid) + len(rejects)
    assert len(valid) == 100
    assert len(rejects) == 5

    expected = {
        "DUPLICATE_IN_BATCH",
        "MISSING_REQUIRED_FIELD",
        "INVALID_PRODUCT_REF",
        "NEGATIVE_OR_ZERO_QUANTITY",
        "NEGATIVE_PRICE",
    }

    assert set(rejects["reject_reason"]) == expected
    assert rejects["source_row_number"].notna().all()

    for record in rejects["raw_record"]:
        assert isinstance(json.loads(record), dict)


def test_partial_failure_and_retry(sample_data):
    db = sample_data / "failure.db"
    sales, _, rejects, tables = prepare_data(sample_data)

    # Intentionally violate the customer foreign key.
    bad_tables = {
        name: frame.copy()
        for name, frame in tables.items()
    }
    bad_tables["fact_sales"].loc[
        bad_tables["fact_sales"].index[0], "customer_key"
    ] = -999999

    with pytest.raises(sqlite3.IntegrityError):
        load_data(
            db, bad_tables, rejects,
            sales["source_file"],
            sales["checksum"],
            sales["rows_read"],
        )

    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM fact_sales"
        ).fetchone()[0] == 0

        assert conn.execute(
            "SELECT COUNT(*) FROM dim_customer"
        ).fetchone()[0] == 0

        assert conn.execute(
            "SELECT COUNT(*) FROM rejected_records"
        ).fetchone()[0] == 0

        assert conn.execute(
            "SELECT COUNT(*) FROM etl_runs WHERE status='FAILED'"
        ).fetchone()[0] == 1

    # Retry using the correct data.
    result = load_data(
        db, tables, rejects,
        sales["source_file"],
        sales["checksum"],
        sales["rows_read"],
    )

    assert result["status"] == "SUCCESS"
    assert result["rows_loaded"] == 100


def test_late_arriving_older_update(sample_data):
    db = sample_data / "late.db"
    original = sample_data / "sales_lines.csv"

    first = run_pipeline(original, db)
    assert first["status"] == "SUCCESS"

    with sqlite3.connect(db) as conn:
        before = conn.execute(
            """
            SELECT sales_amount
            FROM fact_sales
            WHERE transaction_id='T00000001'
            """
        ).fetchone()[0]

    df = pd.read_csv(original, dtype=str).iloc[[0]].copy()

    df["quantity"] = "99"
    df["updated_at"] = "2020-01-01T00:00:00"

    late_file = sample_data / "late_batch.csv"
    df.to_csv(late_file, index=False)

    result = run_pipeline(late_file, db)

    assert result["status"] == "SUCCESS"
    assert result["rows_loaded"] == 0
    assert result["rows_skipped"] == 1

    with sqlite3.connect(db) as conn:
        after = conn.execute(
            """
            SELECT sales_amount
            FROM fact_sales
            WHERE transaction_id='T00000001'
            """
        ).fetchone()[0]

    assert after == before


def test_boundary_values(sample_data):
    path = sample_data / "sales_lines.csv"
    df = pd.read_csv(path, dtype=str)

    df.loc[0, "quantity"] = "1"
    df.loc[0, "unit_price"] = "0"
    df.loc[0, "date"] = "2026-01-31"
    df.loc[0, "updated_at"] = "2026-01-31T00:00:00"

    df.to_csv(path, index=False)

    _, valid, _, tables = prepare_data(sample_data)

    assert len(valid) == 100

    row = tables["fact_sales"].loc[
        tables["fact_sales"]["transaction_id"] == "T00000001"
    ].iloc[0]

    assert row["quantity"] == 1
    assert row["unit_price"] == 0
    assert row["sales_amount"] == 0
    assert row["date_key"] == 20260131
