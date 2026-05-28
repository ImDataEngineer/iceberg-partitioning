"""Demonstrate snapshot isolation by overwriting the 2025 partition and then
querying the previous snapshot — which must still return the ORIGINAL 2025
row count.

À toi de l'implémenter.

Objectif final :

    python -m src.time_travel_demo

doit :

1. Lire le `current_snapshot_id` avant toute modification — c'est le snapshot
   issu de `src/load.py`, celui que la rubric appelle « snapshot v1 ».

2. Construire une nouvelle table Arrow contenant UNIQUEMENT des lignes 2025
   « corrigées » — par exemple les mêmes order_id que dans la fixture 2025,
   mais avec une autre valeur (peu importe laquelle, du moment qu'elle diffère
   et que la cardinalité change). Indication pédagogique : remplace
   `unit_price_cents` par `9_999` partout. Tu peux aussi changer le row count
   en filtrant la moitié des lignes — la rubric ne fixe pas la valeur cible,
   elle vérifie seulement que la lecture historique reste cohérente avec
   l'avant-overwrite.

3. Appliquer un **overwrite de la partition 2025** : remplacer toutes les
   lignes pour lesquelles `year(event_time) == 2025` par ta nouvelle Arrow
   table. PyIceberg ≥ 0.7 expose `table.overwrite(df, overwrite_filter=...)`.
   Astuce sur le filtre :

       from pyiceberg.expressions import GreaterThanOrEqual, LessThan
       from datetime import datetime
       filter_ = And(
           GreaterThanOrEqual("event_time", datetime(2025, 1, 1)),
           LessThan("event_time", datetime(2026, 1, 1)),
       )
       table.overwrite(new_df, overwrite_filter=filter_)

4. Lire la table à deux moments :
     - `current` : lecture la plus récente (après overwrite) — `table.scan().to_arrow()`.
     - `historic` : lecture au snapshot v1 — `table.scan(snapshot_id=v1).to_arrow()`.

5. Printer un récap :
     "snapshot v1 row count (2025): N_HISTORIC"
     "current   row count (2025): N_CURRENT"
   Ces deux nombres doivent être différents (sinon ton overwrite n'a rien
   fait), et N_HISTORIC doit valoir le nombre de lignes 2025 livrées dans
   les fixtures (40_000).

C'est ce dernier invariant que `tests/test_evaluate.py::test_snapshot_isolation_works`
vérifie automatiquement.
"""

from __future__ import annotations

from datetime import datetime

import pyarrow as pa
from pyiceberg.expressions import And, GreaterThanOrEqual, LessThan

from src.catalog import TABLE_IDENTIFIER, get_catalog


def overwrite_2025_partition() -> tuple[int, int, int]:
    """Effectue l'overwrite et retourne (snapshot_v1_id, n_historic_2025, n_current_2025).

    snapshot_v1_id : id du snapshot AVANT overwrite (à conserver pour le
                     time-travel et pour le test).
    n_historic_2025 : nombre de lignes 2025 vues via le snapshot v1.
    n_current_2025  : nombre de lignes 2025 vues sur le snapshot courant.
    """
    catalog = get_catalog()
    table = catalog.load_table(TABLE_IDENTIFIER)

    # 1. Mémoriser le snapshot courant (sera le « snapshot v1 » côté test).
    snapshot_v1_id = table.current_snapshot().snapshot_id  # noqa: F841

    # 2. TODO: construire une Arrow table de remplacement pour 2025.
    #          Lis d'abord les lignes 2025 existantes via table.scan(...).to_arrow(),
    #          puis modifie une colonne (ex: unit_price_cents = 9_999).
    #          Garde-la dans la même schema que la table.

    # 3. TODO: appeler table.overwrite(new_df_2025, overwrite_filter=...) avec
    #          un filtre sur [2025-01-01, 2026-01-01).

    # 4. TODO: après overwrite, table.refresh() et re-scan pour comparer :
    #          - n_historic_2025 : table.scan(snapshot_id=snapshot_v1_id, row_filter=…).to_arrow()
    #          - n_current_2025  : table.scan(row_filter=…).to_arrow()

    raise NotImplementedError(
        "overwrite_2025_partition() pas encore implémenté. "
        "Lis l'en-tête du module — la séquence est explicite, étape par étape."
    )


def main() -> None:
    snapshot_v1_id, n_hist, n_curr = overwrite_2025_partition()
    print(f"snapshot v1 id          : {snapshot_v1_id}")
    print(f"snapshot v1 rows (2025) : {n_hist}")
    print(f"current   rows (2025)   : {n_curr}")
    if n_hist == n_curr:
        print("WARNING: les deux comptes sont identiques — soit l'overwrite n'a "
              "rien fait, soit tu n'as pas changé la cardinalité. Le test "
              "passera quand même si la valeur historique correspond à la "
              "fixture, mais la démo est plus parlante avec un overwrite "
              "destructif (filtrage d'une partie des lignes).")


if __name__ == "__main__":
    main()
