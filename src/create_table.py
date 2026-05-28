"""Create the `default.orders_v1` Iceberg table with hidden partitioning.

À toi de l'implémenter. Le contrat est dans `contracts/orders.json`.

Objectif final :

    python -m src.create_table

doit créer (ou recréer) une table Iceberg `default.orders_v1` dans le catalog
REST local, avec :

  - un schéma qui correspond EXACTEMENT au contrat (8 colonnes, types
    Iceberg attendus),
  - un **partition spec** appliquant la transform `year` sur la colonne
    `event_time` — c'est la « hidden partitioning » d'Iceberg.

Pour rappel sur la hidden partitioning : tu N'AJOUTES PAS de colonne
`order_year` au schéma. Iceberg calcule la valeur de partition à l'écriture,
à partir de `event_time`, parce que la transform vit dans le partition spec
et nulle part ailleurs. C'est la moitié de la promesse Iceberg vs « Parquet
dans un dossier » ; l'autre moitié est l'isolation des snapshots qu'on
exerce dans `src/time_travel_demo.py`.

Indices PyIceberg (≥ 0.7) :
- Schéma : `pyiceberg.schema.Schema(NestedField(field_id=…, name=…, field_type=…, required=…), …)`
  Les types vivent dans `pyiceberg.types` : `LongType()`, `TimestampType()`,
  `StringType()`, `IntegerType()`.
- Partition spec : `PartitionSpec(PartitionField(source_id=…, field_id=…, transform=YearTransform(), name="event_time_year"))`
  importé depuis `pyiceberg.partitioning` et `pyiceberg.transforms`.
- Création : `catalog.create_table(identifier, schema=…, partition_spec=…)`.
- Si la table existe déjà, drop-then-create est acceptable ici (on n'a pas
  encore mis de données critiques en jeu) — `catalog.drop_table(identifier)`.

À la fin du module, affiche un récap clair :
    "table default.orders_v1 ready — schema=[...], partition=[year(event_time)]"
"""

from __future__ import annotations

from src.catalog import TABLE_IDENTIFIER, ensure_namespace, get_catalog


def create_orders_table() -> None:
    """Create (or recreate) the `default.orders_v1` table.

    Doit :
    1. Récupérer le catalog (`get_catalog()`).
    2. Garantir l'existence du namespace `default` (`ensure_namespace()`).
    3. Définir le schéma conforme à contracts/orders.json.
    4. Définir le partition spec avec la transform `year` sur `event_time`.
    5. Créer la table — si elle existe déjà, drop puis recréer.
    """
    catalog = get_catalog()
    ensure_namespace(catalog)

    # TODO: construire le `Schema` PyIceberg (8 NestedField conformes au contrat).
    # TODO: construire le `PartitionSpec` avec YearTransform() sur event_time.
    # TODO: drop-if-exists puis create_table.
    # TODO: print un récap "table … ready" pour le humain qui lance le script.
    raise NotImplementedError(
        "create_orders_table() pas encore implémenté. "
        "Lis contracts/orders.json et l'en-tête de ce module."
    )


def main() -> None:
    create_orders_table()


if __name__ == "__main__":
    main()
