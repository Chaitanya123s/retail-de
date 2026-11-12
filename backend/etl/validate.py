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

    working = df.copy()
    working["source_row_number"] = working.index + 2

    # Keep one rejection reason per row.
    working["reject_reason"] = pd.Series(index=working.index, dtype="object")

    # ---------------------------------------------------------
    # 1) Missing required field
    # ---------------------------------------------------------
    required_as_str = working[REQUIRED_COLUMNS].fillna("").astype(str)
    missing_required_mask = required_as_str.apply(
        lambda col: col.str.strip() == ""
    ).any(axis=1)

    working.loc[
        missing_required_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "MISSING_REQUIRED_FIELD"

    # ---------------------------------------------------------
    # 2) Invalid type
    # ---------------------------------------------------------
    line_number_num = pd.to_numeric(
        working["line_number"], errors="coerce"
    )
    quantity_num = pd.to_numeric(
        working["quantity"], errors="coerce"
    )
    unit_price_num = pd.to_numeric(
        working["unit_price"], errors="coerce"
    )
    date_parsed = pd.to_datetime(
        working["date"], format="%Y-%m-%d", errors="coerce"
    )
    updated_at_parsed = pd.to_datetime(
        working["updated_at"], errors="coerce"
    )

    invalid_type_mask = (
        line_number_num.isna()
        | quantity_num.isna()
        | unit_price_num.isna()
        | date_parsed.isna()
        | updated_at_parsed.isna()
        | (line_number_num < 1)
    )

    working.loc[
        invalid_type_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "INVALID_TYPE"

    # ---------------------------------------------------------
    # 3) Duplicate in batch
    # Keep first, reject later duplicates
    # Use parsed line_number to match original logic
    # ---------------------------------------------------------
    duplicate_scope = working["reject_reason"].isna()

    duplicate_mask = pd.Series(False, index=working.index)
    duplicate_mask.loc[duplicate_scope] = working.loc[
        duplicate_scope,
        ["transaction_id"]
    ].assign(line_number_num=line_number_num.loc[duplicate_scope]).duplicated(
        subset=["transaction_id", "line_number_num"],
        keep="first"
    )

    working.loc[
        duplicate_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "DUPLICATE_IN_BATCH"

    # ---------------------------------------------------------
    # 4) Business-rule checks
    # ---------------------------------------------------------
    customer_ids = set(customers["customer_id"].dropna())
    product_ids = set(products["product_id"].dropna())
    store_ids = set(stores["store_id"].dropna())

    negative_or_zero_quantity_mask = quantity_num <= 0
    negative_price_mask = unit_price_num < 0
    invalid_customer_mask = ~working["customer_id"].isin(customer_ids)
    invalid_product_mask = ~working["product_id"].isin(product_ids)
    invalid_store_mask = ~working["store_id"].isin(store_ids)

    working.loc[
        negative_or_zero_quantity_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "NEGATIVE_OR_ZERO_QUANTITY"

    working.loc[
        negative_price_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "NEGATIVE_PRICE"

    working.loc[
        invalid_customer_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "INVALID_CUSTOMER_REF"

    working.loc[
        invalid_product_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "INVALID_PRODUCT_REF"

    working.loc[
        invalid_store_mask & working["reject_reason"].isna(),
        "reject_reason"
    ] = "INVALID_STORE_REF"

    # ---------------------------------------------------------
    # Split valid and rejected rows
    # ---------------------------------------------------------
    valid_mask = working["reject_reason"].isna()

    valid_df = working.loc[valid_mask, df.columns].copy()

    rejected = working.loc[
        ~valid_mask,
        df.columns.tolist() + ["source_row_number", "reject_reason"]
    ].copy()

    rejected["raw_record"] = rejected[df.columns].apply(
        lambda row: json.dumps(row.to_dict(), default=str),
        axis=1
    )

    rejects_df = rejected[
        ["source_row_number", "reject_reason", "raw_record"]
    ].reset_index(drop=True)

    valid_df = valid_df.reset_index(drop=True)

    return valid_df, rejects_df