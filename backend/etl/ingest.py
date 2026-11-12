from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple

import pandas as pd


EXPECTED_SALES_COLUMNS = [
    "transaction_id",
    "line_number",
    "date",
    "customer_id",
    "product_id",
    "store_id",
    "quantity",
    "unit_price",
    "updated_at",
]


def compute_sha256(file_path: str | Path) -> str:
    """
    Compute sha256 checksum for a file.
    """
    file_path = Path(file_path)
    sha256 = hashlib.sha256()

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def read_csv_as_strings(file_path: str | Path) -> pd.DataFrame:
    """
    Read a CSV file with all columns as strings.
    Keeps bad values untouched for validation later.
    """
    file_path = Path(file_path)
    return pd.read_csv(file_path, dtype=str)


def check_required_columns(
    df: pd.DataFrame,
    expected_columns: list[str],
) -> Tuple[bool, list[str], list[str]]:
    """
    Returns:
        (is_valid, missing_columns, extra_columns)
    """
    actual_columns = list(df.columns)

    missing_columns = [col for col in expected_columns if col not in actual_columns]
    extra_columns = [col for col in actual_columns if col not in expected_columns]

    return len(missing_columns) == 0, missing_columns, extra_columns


def ingest_sales_file(file_path: str | Path) -> dict:
    """
    Ingest a sales CSV file and return metadata + dataframe.

    Raises:
        ValueError: if required columns are missing.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    checksum = compute_sha256(file_path)
    df = read_csv_as_strings(file_path)

    is_valid, missing_columns, extra_columns = check_required_columns(
        df,
        EXPECTED_SALES_COLUMNS,
    )

    if not is_valid:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # Ignore unexpected columns after recording them.
    df = df[EXPECTED_SALES_COLUMNS].copy()

    return {
        "dataframe": df,
        "checksum": checksum,
        "source_file": str(file_path),
        "rows_read": len(df),
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
    }