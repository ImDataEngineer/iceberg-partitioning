# Your first Iceberg table — `storage.partitioned-lakehouse`

> **Level**: junior · **Estimated time**: ~9 h · **Paid IAmDataEng project**
> **Framework axis**: `storage`

This project is your first contact with a real table format. Not "Parquet
dropped in an S3 folder" — a format with a catalog, snapshots, ACID, and
hidden partitioning. You'll spin up a full lakehouse stack locally (MinIO
+ Apache Iceberg REST catalog), create the table, land 3 years of data in
it, then prove snapshot isolation by overwriting a partition and reading
the previous version back.

You walk out of this knowing why a data engineer picks Iceberg, what
changes vs raw Parquet, and — most importantly — you know how to **wire
it by hand**, without Spark.

---

## The context

You join the data team at **Hauler**, a B2B logistics platform that
aggregates orders from regional warehouses. The analytics team extracts 3
years of orders as Parquet (partitioned by year — `orders_2023.parquet`,
`orders_2024.parquet`, `orders_2025.parquet`) and wants to move to a
"real" table: ACID on appends, time-travel, the ability to overwrite a
partition without breaking concurrent reads from the Finance dashboards.

You have a local stack on hand: MinIO (S3-compatible) and an Iceberg REST
catalog, both started by docker-compose from the devcontainer. No AWS
account, no public network dependency.

Your job:

1. Create the table `default.orders_v1` in the catalog with a partition
   on **`year(event_time)`** — **hidden partitioning**, the transform
   lives in the partition spec, never an `order_year` column stuck in
   the schema.
2. Load all 3 years of data in **a single append**.
3. Overwrite the 2025 partition (overwrite) then prove that the original
   snapshot still returns the historical 40,000 rows for 2025.

---

## What you ship

| Deliverable | Where |
|---|---|
| Table creation | `src/create_table.py` (schema + partition spec) |
| Loading | `src/load.py` (reads `fixtures/parquet/*.parquet`, single append) |
| Time-travel demo | `src/time_travel_demo.py` (overwrite 2025 + historical read) |
| Explanatory note | `notebooks/explain.md` (≤ 200 words, template provided) |
| Local stack | `docker-compose.yml` (provided — don't touch it unless you know what you're doing) |

`notebooks/explain.md` is not an afterthought. It's the first thing a
recruiter reads on your fork. CI doesn't grade it, but it's the piece
that separates a fork that "passes the tests" from a fork that shows
you understood why you did what you did.

---

## Getting started

If you're in GitHub Codespaces (one-click open from the IAmDataEng app),
everything is ready: MinIO and the catalog are running, the Parquet
fixtures are generated, Python dependencies are installed. Verify with
`docker compose ps` — you should see 2 services (`minio`,
`iceberg-rest`) in the `running` state.

Locally:

```bash
# 1. Start the stack
docker compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate deterministic Parquet fixtures (seed = 42)
python -m fixtures.generate_fixtures

# 4. Implement src/create_table.py, src/load.py, src/time_travel_demo.py
#    (they raise NotImplementedError until you wire them up)

# 5. Run the assessment rubric
pytest tests/ -v
```

You can eyeball the data via the MinIO console at
`http://localhost:9001` (admin / password — plaintext, it's local).

Once your 4 tests pass locally, **commit + push** to your fork. GitHub
Actions CI replays the same rubric (it restarts the same docker-compose
stack) and the IAmDataEng app displays the verdict in your dashboard.

---

## The 4 rubric checks

Defined in `tests/test_evaluate.py`. Each failing check prints a clear
pedagogical message.

| # | Id | What we check |
|---|---|---|
| 1 | `catalog_has_table` | The table `default.orders_v1` exists in the REST catalog with **exactly** the 8 columns from the contract and a partition spec **`year(event_time)`**. No `order_year` column in the schema. |
| 2 | `row_count_matches_source` | The table's total row count equals the sum of rows from the 3 delivered Parquet files (120,000 rows by default). If you loaded only one year, this check fails. |
| 3 | `snapshot_isolation_works` | After your `time_travel_demo.py` overwrites the 2025 partition, a read at the original snapshot **still** returns the 40,000 2025 rows from before. That's the core Iceberg invariant. |
| 4 | `no_small_files` | ≤ 10 data files per partition after load + overwrite. The classic trap "I appended row-by-row and now I have 40,000 files" is caught here. |

---

## The traps juniors fall into

Seen a hundred times in code review:

- **Sticking an `order_year` column in the schema and partitioning on it as `identity`.**
  It works, but that is NOT Iceberg — that's Hive-style partitioning.
  Check 1 will refuse this schema. The `year` transform lives in the
  partition spec, and nowhere else. That's what lets Iceberg evolve the
  partitioning without rewriting data or breaking queries.

- **Appending row-by-row in a loop.**
  An Iceberg append = one catalog commit = one manifest. Do that 40,000
  times and you get 40,000 manifests and 40,000 data files. Check 4
  catches you. Concatenate everything pyarrow-side first, then make ONE
  `table.append()`.

- **Confusing `current_snapshot()` and `snapshot(prev_id)` after overwrite.**
  After your `overwrite()`, `table.current_snapshot()` points at the NEW
  snapshot. If you do your "historical read" with that, you read the new
  data — not the history. You need to **memorize the snapshot id BEFORE
  the overwrite** and pass it to `table.scan(snapshot_id=...)`.

- **Writing to MinIO without going through the catalog.**
  If you write Parquet directly to `s3://warehouse/...` without
  committing via PyIceberg, the files exist but the catalog doesn't see
  them. The table stays empty as far as REST is concerned. This is also
  the #1 mistake in production: Iceberg is a **catalog-managed** format,
  not a folder.

- **`table.overwrite()` without `overwrite_filter`.**
  Without a filter, you wipe the WHOLE table, not just the 2025
  partition. Check 3 might still pass by accident (snapshot v1 stays
  immutable), but check 2 will be inconsistent afterward. Always pass a
  filter `year(event_time) == 2025`.

- **Starting from a broken docker-compose stack.**
  If you played with MinIO between runs and your bucket is in a weird
  state, `docker compose down -v && docker compose up -d` resets
  everything. The `-v` destroys the MinIO volume — that's what you want.

---

## The local stack in two sentences

- **MinIO** (`localhost:9000`, console `localhost:9001`, creds
  `admin / password`) — emulates the S3 API. This is where the table's
  Parquet files and manifests live.
- **Iceberg REST catalog** (`localhost:8181`, image
  `tabulario/iceberg-rest`) — the service that knows which tables exist,
  what their current schema is, and which snapshot is `current`. All
  writes go through it.

The warehouse is `s3://warehouse/`, the namespace is `default`, the
table identifier is `default.orders_v1`. All these names are centralized
in `src/catalog.py` — don't touch it, you'd just break the tests.

---

## Going further (references)

No reading is mandatory, but if you want these patterns in context:

- Joe Reis & Matt Housley, *Fundamentals of Data Engineering* (O'Reilly,
  2022) — **ch. 6 "Storage", pp. 210-225** on table formats and ACID on
  object storage.
- Apache Iceberg spec, [Partitioning section](https://iceberg.apache.org/spec/#partitioning)
  and [Snapshots section](https://iceberg.apache.org/spec/#snapshots) —
  the doc that defines what we're manipulating.
- Martin Kleppmann, *Designing Data-Intensive Applications* (O'Reilly,
  2017) — **ch. 3 on storage engines** and the notion of snapshot
  isolation (the term comes from there).
- [PyIceberg docs](https://py.iceberg.apache.org/) — especially the
  `Table API` and `Catalog API`.

---

## If you're stuck

The point is for you to struggle a bit — that's what setting up a
lakehouse by hand actually feels like. But if you've been spinning on
the same check for more than an hour:

1. Re-read the test error message — it almost always points at the cause.
2. Check the stack with `docker compose ps` and
   `docker compose logs iceberg-rest --tail=50`.
3. Inspect the table by hand in a Python REPL:

   ```python
   from src.catalog import get_catalog, TABLE_IDENTIFIER
   t = get_catalog().load_table(TABLE_IDENTIFIER)
   print(t.schema())
   print(t.spec())
   print(t.current_snapshot())
   print(t.inspect.files().to_pandas())
   ```

4. Open an issue on your fork with the `help-wanted` label — the
   IAmDataEng community hangs out there.

Good luck.
