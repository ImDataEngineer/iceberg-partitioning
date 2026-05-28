"""IAmDataEng — rubric d'évaluation pour `storage.partitioned-lakehouse`.

Quatre checks déterministes alignés sur la spec projet :

  1. catalog_has_table        — la table existe avec le bon schéma + partition spec.
  2. row_count_matches_source — le compte total == somme des lignes des 3 fichiers Parquet.
  3. snapshot_isolation_works — après overwrite de la partition 2025, le snapshot
                                d'origine renvoie toujours le row count d'origine.
  4. no_small_files           — ≤ 10 fichiers par partition après load.

Tous les tests s'appuient sur le catalog REST + MinIO démarrés par le
devcontainer (ou par le job `stack` dans le workflow CI). Aucun appel réseau
public ; tout tourne sur le loopback.

Important — l'ordre des tests COMPTE :
- On lance `create_table` puis `load` en fixture `module`.
- `test_snapshot_isolation_works` lance `time_travel_demo` ; il modifie la
  table de manière irréversible (overwrite 2025). C'est pour ça qu'il est
  exécuté APRÈS les deux premiers checks (pytest exécute par ordre de
  définition dans le module).
- `test_no_small_files` est compatible avec l'état post-overwrite : il
  inspecte le snapshot courant et la borne de 10 fichiers/partition reste
  largement respectée.

Si tu lances pytest avec `-p no:randomly` (recommandé) ou simplement avec la
config par défaut, cet ordre est respecté.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import urllib.error
import urllib.request

# We import from src/ lazily inside tests where needed, to give a useful error
# message if the learner hasn't installed dependencies yet (rather than a hard
# ImportError at collection time).

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_PARQUET_DIR = PROJECT_ROOT / "fixtures" / "parquet"

REST_HEALTH_URL = "http://localhost:8181/v1/config"
MINIO_HEALTH_URL = "http://localhost:9000/minio/health/live"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_url(url: str, timeout_s: int = 60) -> bool:
    """Poll an HTTP endpoint until it returns 2xx or the timeout elapses."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    return False


def _run(module: str) -> None:
    """Run `python -m <module>` as a subprocess, fail fatally if it errors."""
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"`python -m {module}` a planté.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
            "Astuce : ce module lève NotImplementedError par défaut ; "
            "il faut l'implémenter avant que la rubric puisse passer."
        )


def _fixture_total_rows() -> int:
    """Somme des row counts des 3 fichiers Parquet livrés."""
    files = sorted(FIXTURES_PARQUET_DIR.glob("orders_*.parquet"))
    if not files:
        pytest.fail(
            "Aucun fichier Parquet trouvé sous fixtures/parquet/. "
            "Lance `python -m fixtures.generate_fixtures` "
            "(le devcontainer le fait normalement au boot)."
        )
    return sum(pq.read_metadata(p).num_rows for p in files)


def _fixture_2025_rows() -> int:
    p = FIXTURES_PARQUET_DIR / "orders_2025.parquet"
    if not p.exists():
        pytest.fail(
            "fixtures/parquet/orders_2025.parquet absent. "
            "Régénère les fixtures avant de relancer la rubric."
        )
    return pq.read_metadata(p).num_rows


# ---------------------------------------------------------------------------
# Module-level fixture : crée la table + load une fois pour tous les tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_table():
    """Démarre la rubric : (1) vérifie que la stack est up, (2) appelle
    `create_table`, (3) appelle `load`, (4) retourne le PyIceberg `Table`
    et l'id du snapshot v1 (le snapshot d'origine, AVANT overwrite)."""
    if not _wait_for_url(MINIO_HEALTH_URL, timeout_s=30):
        pytest.fail(
            "MinIO n'est pas joignable sur http://localhost:9000. "
            "Vérifie que la stack docker-compose tourne (`docker compose ps`). "
            "Le devcontainer la démarre normalement au postCreateCommand ; "
            "en CI c'est le job qui la lance."
        )
    if not _wait_for_url(REST_HEALTH_URL, timeout_s=30):
        pytest.fail(
            "Le catalog Iceberg REST n'est pas joignable sur http://localhost:8181. "
            "Vérifie `docker compose logs iceberg-rest`."
        )

    # Lancer les scripts learner. Les deux doivent passer sans exception.
    _run("src.create_table")
    _run("src.load")

    from src.catalog import TABLE_IDENTIFIER, get_catalog

    catalog = get_catalog()
    try:
        table = catalog.load_table(TABLE_IDENTIFIER)
    except Exception as e:  # noqa: BLE001
        pytest.fail(
            f"Impossible de charger la table `{TABLE_IDENTIFIER}` depuis le catalog "
            f"après exécution de src.create_table : {e}\n"
            "Vérifie que ton CREATE utilise bien l'identifiant `default.orders_v1` "
            "et que tu n'as pas modifié src/catalog.py."
        )

    snapshot_v1 = table.current_snapshot()
    if snapshot_v1 is None:
        pytest.fail(
            "La table existe mais n'a aucun snapshot — l'append n'a pas eu lieu. "
            "Vérifie que src/load.py appelle bien `table.append(...)`."
        )

    return table, snapshot_v1.snapshot_id


# ---------------------------------------------------------------------------
# Check 1 — catalog_has_table
# ---------------------------------------------------------------------------


def test_catalog_has_table(loaded_table):
    """La table existe avec le schéma + le partition spec attendus."""
    table, _ = loaded_table

    # 1.a — colonnes et types
    expected_columns = [
        ("order_id", "long"),
        ("event_time", "timestamp"),
        ("customer_id", "long"),
        ("product_name", "string"),
        ("country", "string"),
        ("payment_method", "string"),
        ("quantity", "int"),
        ("unit_price_cents", "int"),
    ]
    actual_columns = [(f.name, str(f.field_type)) for f in table.schema().fields]

    if actual_columns != expected_columns:
        # On accepte que l'ordre des champs diffère légèrement seulement si
        # les paires (nom, type) sont identiques en set. Sinon, on fait sortir
        # la différence proprement.
        if set(actual_columns) != set(expected_columns):
            missing = set(expected_columns) - set(actual_columns)
            extra = set(actual_columns) - set(expected_columns)
            pytest.fail(
                "Le schéma de `default.orders_v1` ne correspond pas au contrat.\n"
                f"Attendu : {expected_columns}\n"
                f"Obtenu  : {actual_columns}\n"
                f"Manquant : {sorted(missing)}\n"
                f"En trop  : {sorted(extra)}\n"
                "Indice : les types doivent être les types Iceberg "
                "(LongType, TimestampType, StringType, IntegerType). "
                "N'ajoute PAS de colonne `order_year` — la partition est dérivée."
            )

    # 1.b — partition spec : exactement UN champ, transform `year` sur event_time.
    spec = table.spec()
    pf = list(spec.fields)
    if len(pf) != 1:
        pytest.fail(
            f"Le partition spec doit avoir EXACTEMENT 1 champ ; obtenu : {len(pf)}.\n"
            "Indice : un seul PartitionField sur event_time avec YearTransform()."
        )

    schema = table.schema()
    src_field = schema.find_field(pf[0].source_id)
    transform_repr = str(pf[0].transform).lower()

    if src_field.name != "event_time":
        pytest.fail(
            f"Le partition spec porte sur la colonne `{src_field.name}` ; "
            "il doit porter sur `event_time`. "
            "Tu as probablement partitionné sur la mauvaise colonne — "
            "vérifie le `source_id` du PartitionField."
        )

    if "year" not in transform_repr:
        pytest.fail(
            f"La transform de partition est `{pf[0].transform}` ; "
            "elle doit être `year`. "
            "Indice PyIceberg : `from pyiceberg.transforms import YearTransform`. "
            "C'est ÇA le hidden partitioning — la transform vit dans le partition "
            "spec, pas dans le schéma."
        )


# ---------------------------------------------------------------------------
# Check 2 — row_count_matches_source
# ---------------------------------------------------------------------------


def test_row_count_matches_source(loaded_table):
    """Le row count de la table == somme des lignes des 3 fichiers Parquet."""
    table, _ = loaded_table
    expected = _fixture_total_rows()

    actual = table.scan().to_arrow().num_rows

    if actual != expected:
        diff = actual - expected
        if diff < 0:
            hint = (
                f"Il te manque {-diff} ligne(s). Tu as probablement loadé "
                "un sous-ensemble des fixtures (une seule année ?), ou un "
                "filtre s'est appliqué silencieusement."
            )
        else:
            hint = (
                f"Tu as {diff} ligne(s) en trop. Tu as appendé deux fois — "
                "src.load n'est pas idempotent. Re-créer la table dans "
                "src.create_table avant chaque load est une approche acceptable."
            )
        pytest.fail(
            f"Row count incorrect — attendu {expected} (somme des Parquet), "
            f"obtenu {actual}.\n{hint}"
        )


# ---------------------------------------------------------------------------
# Check 3 — snapshot_isolation_works
# ---------------------------------------------------------------------------


def test_snapshot_isolation_works(loaded_table):
    """Après overwrite de la partition 2025, le snapshot v1 retourne TOUJOURS
    le row count d'origine (40_000) pour 2025.

    C'est l'invariant cœur d'Iceberg : un snapshot est immuable. Time-travel
    veut dire « lire à un point dans le temps », pas « lire la dernière
    version » — un piège classique est d'utiliser `table.current_snapshot()`
    après l'overwrite, ce qui renvoie le NOUVEAU snapshot et donc les
    nouvelles données.
    """
    table, snapshot_v1_id = loaded_table
    expected_2025 = _fixture_2025_rows()

    # Lance le module learner — c'est lui qui doit faire l'overwrite.
    _run("src.time_travel_demo")

    # Rafraîchir notre handle Python : un autre process a écrit.
    table.refresh()

    # Lecture historique au snapshot v1, filtrée sur 2025.
    from datetime import datetime
    from pyiceberg.expressions import And, GreaterThanOrEqual, LessThan

    filter_2025 = And(
        GreaterThanOrEqual("event_time", datetime(2025, 1, 1)),
        LessThan("event_time", datetime(2026, 1, 1)),
    )

    try:
        historic = table.scan(snapshot_id=snapshot_v1_id, row_filter=filter_2025).to_arrow()
    except Exception as e:  # noqa: BLE001
        pytest.fail(
            f"Impossible de scanner la table au snapshot v1 ({snapshot_v1_id}) : {e}\n"
            "Indice : `table.scan(snapshot_id=<id>)` requiert que le snapshot "
            "soit toujours présent dans l'historique — vérifie que tu ne fais "
            "pas d'expire_snapshots avant ce test."
        )

    historic_rows = historic.num_rows

    # Sanity check côté courant : la lecture la plus récente ne doit PAS
    # retourner le même nombre de lignes (sinon l'overwrite n'a rien fait).
    current = table.scan(row_filter=filter_2025).to_arrow()
    current_rows = current.num_rows

    if historic_rows != expected_2025:
        pytest.fail(
            f"Lecture au snapshot v1 (avant overwrite) : {historic_rows} lignes pour 2025.\n"
            f"Attendu : {expected_2025} (le row count d'origine de la fixture 2025).\n"
            "Piège classique : tu as fait `table.scan(snapshot_id=table.current_snapshot().snapshot_id)` "
            "APRÈS l'overwrite — ce snapshot id est le NOUVEAU, pas l'ancien. "
            "Mémorise l'id du snapshot AVANT l'overwrite."
        )

    if current_rows == historic_rows:
        pytest.fail(
            f"La lecture courante et la lecture historique retournent toutes "
            f"les deux {historic_rows} lignes pour 2025 — ton overwrite n'a "
            "rien changé.\n"
            "Indice : `table.overwrite(new_df, overwrite_filter=...)` doit "
            "remplacer les lignes 2025 par un dataset de cardinalité différente, "
            "pour que la démo soit visible. Si tu remplaces lignes-pour-lignes "
            "à l'identique, l'isolation n'est pas démontrée."
        )


# ---------------------------------------------------------------------------
# Check 4 — no_small_files
# ---------------------------------------------------------------------------


def test_no_small_files(loaded_table):
    """≤ 10 fichiers de données par partition après le load + overwrite.

    Ce check attrape le bug classique « j'ai appendé ligne par ligne dans
    une boucle, j'ai produit 40_000 fichiers ».
    """
    table, _ = loaded_table
    table.refresh()

    files = table.inspect.files()  # arrow Table, une ligne par data file

    # Convertir en dict Python pour grouper par partition.
    # `partition` est un struct {event_time_year: int}.
    file_count_per_partition: dict = {}

    try:
        partitions = files.column("partition").to_pylist()
        contents = files.column("content").to_pylist() if "content" in files.column_names else [0] * len(partitions)
    except KeyError:
        pytest.fail(
            "Le résultat de `table.inspect.files()` n'a pas la colonne attendue. "
            "Possible incompatibilité PyIceberg — vérifie la version dans requirements.txt."
        )

    for part, content_type in zip(partitions, contents):
        # content == 0 → data file ; 1 → position delete ; 2 → equality delete.
        # On ne compte que les data files.
        if content_type != 0:
            continue
        key = tuple(sorted(part.items())) if isinstance(part, dict) else (part,)
        file_count_per_partition[key] = file_count_per_partition.get(key, 0) + 1

    if not file_count_per_partition:
        pytest.fail(
            "Aucun data file trouvé dans la table. Le load n'a manifestement "
            "rien committé."
        )

    too_many = {k: v for k, v in file_count_per_partition.items() if v > 10}
    if too_many:
        pretty = ", ".join(f"{k} → {v} files" for k, v in too_many.items())
        pytest.fail(
            "Des partitions ont plus de 10 fichiers de données :\n"
            f"  {pretty}\n"
            "Piège classique : tu as appendé ligne par ligne, ou un append par "
            "année. Concatène toutes les fixtures côté Arrow puis fais UN seul "
            "`table.append(arrow_table)` — Iceberg gère le découpage en "
            "partitions tout seul."
        )
