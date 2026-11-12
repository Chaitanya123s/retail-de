
import json

import pandas as pd


REQUIRED_COLUMNS = [
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


def validate_sales(df, customers, products, stores):
    """
    Validate sales transactions.

    Returns:
        valid_df: Valid transaction records.
        rejects_df: Invalid records with reasons and source rows.
    """

    valid_rows = []
    rejected_rows = []
    seen_keys = set()

    customer_ids = set(customers["customer_id"].dropna())
    product_ids = set(products["product_id"].dropna())
    store_ids = set(stores["store_id"].dropna())

    for index, row in df.iterrows():
        reason = None
        record = row.to_dict()

        # 1-based CSV row number, including the header.
        source_row_number = index + 2

        # Check missing required values.
        for column in REQUIRED_COLUMNS:
            value = row[column]
            if pd.isna(value) or str(value).strip() == "":
                reason = "MISSING_REQUIRED_FIELD"
                break

        # Validate data types and dates.
        if reason is None:
            try:
                line_number = int(row["line_number"])
                quantity = int(row["quantity"])
                unit_price = float(row["unit_price"])

                date = pd.to_datetime(
                    row["date"], format="%Y-%m-%d", errors="raise"
                )
                updated_at = pd.to_datetime(
                    row["updated_at"], errors="raise"
                )

                if line_number < 1:
                    reason = "INVALID_TYPE"
                elif pd.isna(date) or pd.isna(updated_at):
                    reason = "INVALID_TYPE"

            except (ValueError, TypeError, OverflowError):
                reason = "INVALID_TYPE"

        # Check duplicate business keys.
        if reason is None:
            key = (row["transaction_id"], line_number)

            if key in seen_keys:
                reason = "DUPLICATE_IN_BATCH"
            else:
                seen_keys.add(key)

        # Apply business rules.
        if reason is None:
            if quantity <= 0:
                reason = "NEGATIVE_OR_ZERO_QUANTITY"
            elif not pd.notna(unit_price) or unit_price < 0:
                reason = "NEGATIVE_PRICE"
            elif row["customer_id"] not in customer_ids:
                reason = "INVALID_CUSTOMER_REF"
            elif row["product_id"] not in product_ids:
                reason = "INVALID_PRODUCT_REF"
            elif row["store_id"] not in store_ids:
                reason = "INVALID_STORE_REF"

        if reason:
            rejected_rows.append({
                "source_row_number": source_row_number,
                "reject_reason": reason,
                "raw_record": json.dumps(record, default=str),
            })
        else:
            valid_rows.append(record)

    valid_df = pd.DataFrame(valid_rows, columns=df.columns)

    rejects_df = pd.DataFrame(
        rejected_rows,
        columns=[
            "source_row_number",
            "reject_reason",
            "raw_record",
        ],
    )

    return valid_df, rejects_df
