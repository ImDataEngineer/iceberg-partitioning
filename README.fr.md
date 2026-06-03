> *Aussi disponible en [anglais](./README.md).*

[![Template](https://img.shields.io/badge/repo-template-1e293b?style=flat-square)](https://github.com/ImDataEngineer/iceberg-partitioning/generate) [![iamdataeng.com](https://img.shields.io/badge/iamdataeng.com-2563eb?style=flat-square)](https://iamdataeng.com/projects/storage.partitioned-lakehouse)

> **Contexte.** Template pédagogique de [iamdataeng.com/projects/storage.partitioned-lakehouse](https://iamdataeng.com/projects/storage.partitioned-lakehouse). Fork, complète les TODO, push, reçois un verdict CI pédagogique. Pas un projet open source maintenu, un exercice évalué.

# Ta première table Iceberg — `storage.partitioned-lakehouse`

> **Niveau** : junior · **Durée estimée** : ~9 h · **Projet payant IamDataEngineer**
> **Axe framework** : `storage`

Ce projet est ton premier contact avec un vrai format de table. Pas
« Parquet posé dans un dossier S3 » — un format avec catalogue, snapshots,
ACID, et hidden partitioning. Tu vas démarrer une stack lakehouse complète
en local (MinIO + Apache Iceberg REST catalog), créer la table, y déposer
3 ans de données, puis prouver l'isolation des snapshots en écrasant une
partition et en relisant la version d'avant.

Tu sors d'ici en sachant pourquoi un data engineer choisit Iceberg, ce que
ça change face à du Parquet brut, et — c'est le plus important — tu sais le
**câbler à la main**, sans Spark.

---

## Le contexte

Tu rejoins l'équipe data de **Hauler**, une plateforme logistique B2B
qui agrège les commandes de plusieurs entrepôts régionaux. L'équipe
analytique extrait 3 ans de commandes en Parquet (partitionnées à
l'année — `orders_2023.parquet`, `orders_2024.parquet`,
`orders_2025.parquet`) et veut basculer sur une « vraie » table : ACID
sur les appends, time-travel, possibilité d'écraser une partition sans
casser les lectures en cours des dashboards Finance.

Tu as une stack locale sous la main : MinIO (S3-compatible) et un catalog
Iceberg REST, démarrés en docker-compose par le devcontainer. Aucun
compte AWS, aucune dépendance réseau publique.

Ton job :

1. Créer la table `default.orders_v1` dans le catalog avec une partition
   par **`year(event_time)`** — **hidden partitioning**, transform dans le
   partition spec, surtout pas une colonne `order_year` collée dans le
   schéma.
2. Loader les 3 années de données en **un seul append**.
3. Écraser la partition 2025 (overwrite) puis prouver que le snapshot
   d'origine renvoie toujours les 40 000 lignes 2025 historiques.

---

## Ce que tu vas livrer

| Livrable | Où |
|---|---|
| Création de la table | `src/create_table.py` (schéma + partition spec) |
| Chargement | `src/load.py` (lit `fixtures/parquet/*.parquet`, un seul append) |
| Démo time-travel | `src/time_travel_demo.py` (overwrite 2025 + lecture historique) |
| Note explicative | `notebooks/explain.md` (≤ 200 mots, template fourni) |
| Stack locale | `docker-compose.yml` (déjà fourni — n'y touche pas sauf si tu sais ce que tu fais) |

`notebooks/explain.md` n'est pas un détail. C'est ce qu'un recruteur va lire
en premier sur ton fork. La CI ne le lit pas, mais c'est la pièce qui
distingue un fork qui « passe les tests » d'un fork qui montre que tu as
compris pourquoi tu as fait ce que tu as fait.

---

## Comment commencer

Si tu es dans GitHub Codespaces (ouverture en un clic depuis l'app
IamDataEngineer), tout est prêt : MinIO et le catalog tournent, les fixtures
Parquet sont générées, les dépendances Python sont installées. Vérifie avec
`docker compose ps` — tu dois voir 2 services (`minio`, `iceberg-rest`) en
état `running`.

En local :

```bash
# 1. Démarrer la stack
docker compose up -d

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Générer les fixtures Parquet déterministes (seed = 42)
python -m fixtures.generate_fixtures

# 4. Implémenter src/create_table.py, src/load.py, src/time_travel_demo.py
#    (ils lèvent NotImplementedError tant que tu n'as rien câblé)

# 5. Lancer la rubric d'évaluation
pytest tests/ -v
```

Tu peux vérifier visuellement les données via la console MinIO sur
`http://localhost:9001` (admin / password — c'est en clair, c'est local).

Quand tes 4 tests passent en local, **commit + push** sur ton fork. La CI
GitHub Actions rejoue la même rubric (elle relance la même stack
docker-compose) et l'app IamDataEngineer affiche le verdict dans ton dashboard.

---

## Les 4 checks de la rubric

Ils sont définis dans `tests/test_evaluate.py`. Chaque check qui échoue te
crache un message pédagogique en clair.

| # | Id | Ce qu'on vérifie |
|---|---|---|
| 1 | `catalog_has_table` | La table `default.orders_v1` existe dans le catalog REST avec **exactement** les 8 colonnes du contrat et un partition spec **`year(event_time)`**. Pas de colonne `order_year` au schéma. |
| 2 | `row_count_matches_source` | Le row count total de la table == somme des lignes des 3 fichiers Parquet livrés (120 000 lignes par défaut). Si tu n'as loadé qu'une année, tu rates ce check. |
| 3 | `snapshot_isolation_works` | Après overwrite de la partition 2025 par ton `time_travel_demo.py`, une lecture au snapshot d'origine renvoie **toujours** les 40 000 lignes 2025 d'avant. C'est l'invariant cœur d'Iceberg. |
| 4 | `no_small_files` | ≤ 10 fichiers de données par partition après load + overwrite. Le piège classique « j'ai appendé ligne par ligne et j'ai 40 000 fichiers » est attrapé ici. |

---

## Les pièges que les juniors se prennent

Vu cent fois en code review :

- **Coller une colonne `order_year` dans le schéma et la partitionner en `identity`.**
  Ça marche, mais ce n'est PAS Iceberg — c'est Hive style. Le check 1
  refusera ce schéma. La transform `year` vit dans le partition spec, et nulle
  part ailleurs. C'est ce qui permet à Iceberg de faire évoluer le
  partitioning sans réécrire les données ni casser les requêtes.

- **Appendre ligne par ligne dans une boucle.**
  Un append Iceberg = un commit catalog = un manifest. Si tu en fais 40 000
  tu te ramasses 40 000 manifestes et 40 000 fichiers de données. Le check 4
  t'attrape. Concatène TOUT côté pyarrow d'abord, fais UN `table.append()`.

- **Confondre `current_snapshot()` et `snapshot(prev_id)` après overwrite.**
  Après ton `overwrite()`, `table.current_snapshot()` pointe sur le NOUVEAU
  snapshot. Si tu fais ta « lecture historique » avec ça, tu lis les
  nouvelles données — pas l'historique. Tu dois **mémoriser le snapshot id
  AVANT l'overwrite** puis le passer à `table.scan(snapshot_id=...)`.

- **Écrire dans MinIO sans passer par le catalog.**
  Si tu écris du Parquet directement sur `s3://warehouse/...` sans committer
  via PyIceberg, les fichiers existent mais le catalog ne les voit pas. La
  table reste vide vue du REST. C'est l'erreur n°1 en prod aussi : Iceberg
  est un format **catalog-géré**, pas un dossier.

- **`table.overwrite()` sans `overwrite_filter`.**
  Sans filtre, tu écrases TOUTE la table, pas juste la partition 2025. Le
  check 3 passera quand même peut-être par accident (le snapshot v1 reste
  immuable), mais le check 2 sera incohérent après. Toujours passer un
  filtre `year(event_time) == 2025`.

- **Repartir d'une stack docker-compose pourrie.**
  Si tu as joué avec MinIO entre deux runs et que ton bucket est dans un
  état weird, `docker compose down -v && docker compose up -d` remet
  tout à zéro. Le `-v` détruit le volume MinIO, c'est ça que tu veux.

---

## La stack locale en deux phrases

- **MinIO** (`localhost:9000`, console `localhost:9001`, creds
  `admin / password`) — émule l'API S3. C'est là que vivent les fichiers
  Parquet de la table et ses manifestes.
- **Iceberg REST catalog** (`localhost:8181`, image `tabulario/iceberg-rest`)
  — c'est le service qui sait quelle table existe, quel est son schéma
  courant, et quel snapshot est le `current`. Toutes les écritures passent
  par lui.

Le warehouse est `s3://warehouse/`, le namespace `default`, l'identifiant
de table `default.orders_v1`. Tous ces noms sont centralisés dans
`src/catalog.py` — n'y touche pas, tu casserais juste les tests.

---

## Pour aller plus loin (références)

Aucune lecture n'est obligatoire, mais si tu veux remettre ces patterns
dans un cadre :

- Joe Reis & Matt Housley, *Fundamentals of Data Engineering* (O'Reilly,
  2022) — **chap. 6 « Storage », pp. 210-225** sur les formats de table et
  l'ACID sur object storage.
- Apache Iceberg spec, [section Partitioning](https://iceberg.apache.org/spec/#partitioning)
  et [section Snapshots](https://iceberg.apache.org/spec/#snapshots) — c'est
  la doc qui définit ce qu'on manipule.
- Martin Kleppmann, *Designing Data-Intensive Applications* (O'Reilly,
  2017) — **chap. 3 sur les storage engines** et la notion de snapshot
  isolation (le terme vient de là).
- [PyIceberg docs](https://py.iceberg.apache.org/) — particulièrement
  `Table API` et `Catalog API`.

---

## Si tu es bloqué

L'objectif est que tu galères un peu — c'est ça, mettre en place un
lakehouse à la main. Mais si tu tournes en rond plus d'une heure sur un
check précis :

1. Relis le message d'erreur du test — il pointe presque toujours la cause.
2. Vérifie la stack avec `docker compose ps` et `docker compose logs iceberg-rest --tail=50`.
3. Inspecte la table à la main dans un Python REPL :

   ```python
   from src.catalog import get_catalog, TABLE_IDENTIFIER
   t = get_catalog().load_table(TABLE_IDENTIFIER)
   print(t.schema())
   print(t.spec())
   print(t.current_snapshot())
   print(t.inspect.files().to_pandas())
   ```

4. Ouvre une issue dans ton fork avec le label `help-wanted` — la
   communauté IamDataEngineer y passe.

Bonne route.
