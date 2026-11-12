
import hashlib
from datetime import datetime

import pandas as pd


def surrogate_key(value):
    """Generate a deterministic positive 60-bit integer."""
    digest = hashlib.md5(str(value).encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def transform_sales(valid_df, customers, products, stores):
    """Build dimension and fact DataFrames from valid sales."""

    sales = valid_df.copy()

    # Convert data types.
    sales["line_number"] = sales["line_number"].astype(int)
    sales["quantity"] = sales["quantity"].astype(int)
    sales["unit_price"] = sales["unit_price"].astype(float)

    # Use integer cents to calculate money more reliably.
    sales["sales_amount"] = (
        sales["quantity"] * sales["unit_price"]
    ).round(2)

    sales["date"] = pd.to_datetime(
        sales["date"], format="%Y-%m-%d"
    ).dt.strftime("%Y-%m-%d")

    sales["updated_at"] = pd.to_datetime(
        sales["updated_at"]
    ).dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Build customer dimension.
    dim_customer = customers.copy()
    dim_customer["customer_key"] = (
        dim_customer["customer_id"].apply(surrogate_key)
    )
    dim_customer = dim_customer[
        ["customer_key", "customer_id", "customer_name", "region"]
    ]

    # Build product dimension.
    dim_product = products.copy()
    dim_product["product_key"] = (
        dim_product["product_id"].apply(surrogate_key)
    )
    dim_product = dim_product[
        ["product_key", "product_id", "product_name", "category"]
    ]

    # Build store dimension.
    dim_store = stores.copy()
    dim_store["store_key"] = (
        dim_store["store_id"].apply(surrogate_key)
    )
    dim_store = dim_store[
        ["store_key", "store_id", "store_name", "region"]
    ]

    # Build date dimension.
    dates = pd.to_datetime(sales["date"]).drop_duplicates()

    dim_date = pd.DataFrame({
        "date_key": dates.dt.strftime("%Y%m%d").astype(int),
        "full_date": dates.dt.strftime("%Y-%m-%d"),
        "year": dates.dt.year.astype(int),
        "month": dates.dt.month.astype(int),
        "day": dates.dt.day.astype(int),
    })

    # Build sales fact table.
    fact_sales = sales.copy()

    fact_sales["sales_key"] = fact_sales.apply(
        lambda row: surrogate_key(
            f"{row['transaction_id']}|{row['line_number']}"
        ),
        axis=1,
    )

    fact_sales["date_key"] = pd.to_datetime(
        fact_sales["date"]
    ).dt.strftime("%Y%m%d").astype(int)

    fact_sales["customer_key"] = (
        fact_sales["customer_id"].apply(surrogate_key)
    )
    fact_sales["product_key"] = (
        fact_sales["product_id"].apply(surrogate_key)
    )
    fact_sales["store_key"] = (
        fact_sales["store_id"].apply(surrogate_key)
    )

    fact_sales = fact_sales[
        [
            "sales_key",
            "transaction_id",
            "line_number",
            "date_key",
            "customer_key",
            "product_key",
            "store_key",
            "quantity",
            "unit_price",
            "sales_amount",
            "updated_at",
        ]
    ]

    return {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_store": dim_store,
        "dim_date": dim_date,
        "fact_sales": fact_sales,
    }
