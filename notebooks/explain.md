# Pourquoi Iceberg, et pas « Parquet dans un dossier S3 »

> Note du learner : remplis cette page (≤ 200 mots) une fois que les 4 checks
> de la rubric passent. C'est ce qu'un recruteur lira sur ton fork — vise la
> clarté brutale, pas la pédagogie de manuel. La CI ne lit pas ce fichier,
> mais il vaut son poids dans un dossier de candidature.

## 1. Le problème de « Parquet dans un dossier »

<!--
2-3 phrases. Évoque la course aux écritures concurrentes, l'absence de
catalogue, le fait qu'un `LIST` S3 est ta seule source de vérité pour savoir
quelles données existent, et ce qui se passe si un consumer lit pendant
qu'un writer renomme.
-->

…

## 2. Ce que les snapshots Iceberg changent

<!--
2-3 phrases. Explique avec tes mots ce qu'est un snapshot (manifest + manifest
list + data files), pourquoi c'est immuable, et comment ça donne du
time-travel + de l'isolation de lecture sans verrou.
-->

…

## 3. Hidden partitioning — la vraie raison

<!--
2-3 phrases. Pourquoi `year(event_time)` dans le partition spec bat
`partition_by('order_year')` après dérivation manuelle dans le pipeline.
Pense « évolution du partitioning sans casser les requêtes ».
-->

…

## 4. Quand NE PAS choisir Iceberg

<!--
1-2 phrases. Sois honnête : opérationnellement, c'est plus lourd qu'un dossier
Parquet. Quand est-ce que ça ne vaut pas le coup ?
-->

…
