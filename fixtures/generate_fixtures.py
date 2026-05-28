"""Deterministic Parquet fixture generator for the orders dataset.

Run from the project root:

    python -m fixtures.generate_fixtures

Output: one Parquet file per year under `fixtures/parquet/`:
    fixtures/parquet/orders_2023.parquet
    fixtures/parquet/orders_2024.parquet
    fixtures/parquet/orders_2025.parquet

Why three files (one per year) and not 1.2M rows in one file?
- It mirrors the realistic "partitioned Parquet handed over from upstream"
  scenario in the project brief.
- It makes per-year row counts trivially auditable from the file system.
- The fixture is small enough to live in the repo (~3MB total) and large enough
  to exercise partitioning (3 partitions) and snapshot isolation in CI.

We use 120_000 rows total (40k per year) rather than the catalog's nominal
1.2M — same shape, an order of magnitude faster to write and to ingest in CI.
The test rubric counts rows IN THE FIXTURES, not against a hardcoded constant,
so a learner who wants to scale up locally can regenerate with more rows
without breaking the rubric.

Determinism:
- A fixed `random.Random(42)` provides every random draw.
- pyarrow writes Parquet with stable defaults (snappy compression, no row-group
  randomness). The same input produces byte-stable Parquet on any platform.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SEED = 42
ROWS_PER_YEAR = 40_000
YEARS = [2023, 2024, 2025]

FIXTURES_DIR = Path(__file__).resolve().parent / "parquet"

PRODUCT_NAMES = [
    "espresso-machine",
    "bluetooth-headphones",
    "running-shoes",
    "yoga-mat",
    "kitchen-knife",
    "winter-jacket",
    "cookbook",
    "table-lamp",
    "backpack",
    "water-bottle",
]
COUNTRIES = ["FR", "FR", "FR", "BE", "CH", "DE", "ES", "IT"]
PAYMENT_METHODS = ["card", "card", "card", "paypal", "transfer"]


def _gen_year(year: int) -> pa.Table:
    """Build one year of synthetic orders as an Arrow table.

    Columns:
      order_id        int64   — globally unique, no overlap across years
      event_time      timestamp[us]  — spread over the full year
      customer_id     int64   — 1..50_000
      product_name    string
      country         string
      payment_method  string
      quantity        int32
      unit_price_cents int32
    """
    rng = random.Random(SEED + year)
    year_start = datetime(year, 1, 1, 0, 0, 0)
    seconds_in_year = 365 * 24 * 3600  # close enough; not a leap-year accurate spread

    base_id = year * 1_000_000  # 2023 → 2_023_000_000+, no overlap
    order_ids: list[int] = []
    event_times: list[datetime] = []
    customer_ids: list[int] = []
    products: list[str] = []
    countries: list[str] = []
    payments: list[str] = []
    quantities: list[int] = []
    prices: list[int] = []

    for i in range(ROWS_PER_YEAR):
        order_ids.append(base_id + i)
        offset_s = rng.randint(0, seconds_in_year - 1)
        event_times.append(year_start + timedelta(seconds=offset_s))
        customer_ids.append(rng.randint(1, 50_000))
        products.append(rng.choice(PRODUCT_NAMES))
        countries.append(rng.choice(COUNTRIES))
        payments.append(rng.choice(PAYMENT_METHODS))
        quantities.append(rng.randint(1, 5))
        prices.append(rng.randint(500, 25_000))  # 5,00 EUR to 250,00 EUR

    return pa.table(
        {
            "order_id": pa.array(order_ids, type=pa.int64()),
            "event_time": pa.array(event_times, type=pa.timestamp("us")),
            "customer_id": pa.array(customer_ids, type=pa.int64()),
            "product_name": pa.array(products, type=pa.string()),
            "country": pa.array(countries, type=pa.string()),
            "payment_method": pa.array(payments, type=pa.string()),
            "quantity": pa.array(quantities, type=pa.int32()),
            "unit_price_cents": pa.array(prices, type=pa.int32()),
        }
    )


def generate() -> list[Path]:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for year in YEARS:
        table = _gen_year(year)
        path = FIXTURES_DIR / f"orders_{year}.parquet"
        # Single row-group, snappy: stable Parquet output.
        pq.write_table(table, path, compression="snappy", row_group_size=ROWS_PER_YEAR)
        written.append(path)
    return written


def main() -> None:
    paths = generate()
    for p in paths:
        size = p.stat().st_size
        print(f"wrote {p}  ({ROWS_PER_YEAR} rows, {size} bytes)")


if __name__ == "__main__":
    main()
