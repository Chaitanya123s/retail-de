
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42

COLUMNS = [
    "transaction_id", "line_number", "date",
    "customer_id", "product_id", "store_id",
    "quantity", "unit_price", "updated_at"
]


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def generate(output_dir, count):
    rng = random.Random(SEED)
    output_dir = Path(output_dir)

    customers = [
        [f"C{i:04d}", f"Customer {i}", rng.choice(
            ["North", "South", "East", "West"
            ])]
        for i in range(1, 101)
    ]

    products = [
        [f"P{i:04d}", f"Product {i}", rng.choice(
            ["Electronics", "Clothing", "Grocery"
            ])]
        for i in range(1, 51)
    ]

    stores = [
        [f"S{i:03d}", f"Store {i}", rng.choice(
            ["North", "South", "East", "West"
            ])]
        for i in range(1, 11)
    ]

    write_csv(
        output_dir / "customers.csv",
        ["customer_id", "customer_name", "region"],
        customers
    )

    write_csv(
        output_dir / "products.csv",
        ["product_id", "product_name", "category"],
        products
    )

    write_csv(
        output_dir / "stores.csv",
        ["store_id", "store_name", "region"],
        stores
    )

    rows = []
    start = datetime(2026, 1, 1)

    for i in range(1, count + 1):
        date = start + timedelta(days=rng.randint(0, 300))
        updated = date + timedelta(hours=1)

        rows.append([
            f"T{i:08d}",
            1,
            date.date().isoformat(),
            rng.choice(customers)[0],
            rng.choice(products)[0],
            rng.choice(stores)[0],
            rng.randint(1, 10),
            rng.randint(0, 5000),
            updated.isoformat()
        ])

    
    # Deliberately invalid records for validation tests.
    if count >= 10:
        duplicate = rows[0].copy()
        rows.append(duplicate)

        missing_customer = rows[1].copy()
        missing_customer[0] = "T_MISSING_CUSTOMER"
        missing_customer[3] = ""
        rows.append(missing_customer)

        invalid_product = rows[2].copy()
        invalid_product[0] = "T_INVALID_PRODUCT"
        invalid_product[4] = "P9999"
        rows.append(invalid_product)

        negative_quantity = rows[3].copy()
        negative_quantity[0] = "T_NEGATIVE_QUANTITY"
        negative_quantity[6] = -2
        rows.append(negative_quantity)

        negative_price = rows[4].copy()
        negative_price[0] = "T_NEGATIVE_PRICE"
        negative_price[7] = -100
        rows.append(negative_price)

    write_csv(output_dir / "sales_lines.csv", COLUMNS, rows)
    print(f"Generated {len(rows)} sales rows in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sample")
    parser.add_argument("--count", type=int, default=100)

    args = parser.parse_args()
    generate(args.output, args.count)

