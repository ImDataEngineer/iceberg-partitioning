"""Load the three yearly Parquet fixtures into the Iceberg table.

À toi de l'implémenter.

Objectif final :

    python -m src.load

doit lire les 3 fichiers Parquet sous `fixtures/parquet/orders_YYYY.parquet`,
les agréger en une seule table Arrow, et faire UN append Iceberg qui produit
3 partitions (une par année) — sans ajouter de colonne `order_year` au schéma.

Pourquoi un seul append (et pas trois) :
- Chaque commit Iceberg crée un snapshot. Faire un append par année donne
  trois snapshots et trois manifestes, ce qui complique inutilement le test
  d'isolation. Un append unique = un snapshot initial propre.
- Le check `no_small_files` de la rubric vérifie qu'il y a ≤ 10 fichiers par
  partition. Avec un seul append bien formé, tu en auras un seul.

Indices PyIceberg :
- Lecture Parquet : `pyarrow.parquet.read_table(path)`.
- Concat : `pyarrow.concat_tables([t1, t2, t3])`.
- Append : `table.append(arrow_table)` — c'est la nouvelle API ≥ 0.7.
  (Les versions antérieures utilisaient `append_to_table` au niveau du module.)
- Pas besoin de manipuler la partition manuellement : Iceberg dérive
  `event_time_year` à partir de `event_time` via la transform du partition spec.
  Si tu trouves toi-même un `order_year`, tu as fait fausse route.

Pour le check d'isolation qu'on exercera dans `src/time_travel_demo.py`, mémorise
ou re-récupère le snapshot id retourné juste après ce premier append (c'est
`table.current_snapshot().snapshot_id`). Tu en auras besoin.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.catalog import TABLE_IDENTIFIER, get_catalog

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = PROJECT_ROOT / "fixtures" / "parquet"


def read_all_fixtures() -> pa.Table:
    """Lis et concatène les 3 fichiers Parquet livrés sous fixtures/parquet/."""
    # TODO: lister fixtures/parquet/orders_*.parquet (TRIE le résultat pour
    #       garantir un ordre stable entre dev et CI).
    # TODO: pq.read_table sur chacun, pa.concat_tables.
    raise NotImplementedError("read_all_fixtures() pas encore implémenté.")


def load_into_iceberg() -> int:
    """Append la totalité des fixtures dans `default.orders_v1` en un seul commit.

    Retourne le nombre de lignes appendées (utile pour le print final et pour
    valider que la lecture côté Parquet est cohérente avec ce qu'a vu Iceberg).
    """
    catalog = get_catalog()

    # TODO: catalog.load_table(TABLE_IDENTIFIER)
    # TODO: lire les fixtures via read_all_fixtures()
    # TODO: faire UN seul append (table.append(arrow_table))
    # TODO: retourner len(arrow_table)
    raise NotImplementedError(
        "load_into_iceberg() pas encore implémenté. "
        "Lis l'en-tête de ce module pour la stratégie d'append."
    )


def main() -> None:
    n = load_into_iceberg()
    print(f"appended {n} rows into {TABLE_IDENTIFIER}")


if __name__ == "__main__":
    main()
