# ADR-017 — Source des limites communales pour le pilote

- **Statut** : accepté pour le pilote, à réexaminer avant l'ouverture nationale
- **Date** : 2026-07-28
- **Amende** : cahier §9.5 et §16.7

## Contexte

Le cahier prévoit l'import d'ADMIN EXPRESS COG via l'API de téléchargement de la
Géoplateforme IGN. Cette API sert le produit sous forme d'archives couvrant la
France entière : plusieurs centaines de mégaoctets compressés en 7z, contenant
des shapefiles à décompresser, lire et reprojeter.

Trois conséquences pratiques :

1. Une dépendance supplémentaire pour la décompression 7z, absente de
   conda-forge sous une forme stable pour tous les systèmes.
2. Un téléchargement d'un gigaoctet pour obtenir les 163 communes des
   Alpes-Maritimes, alors que le pilote ne couvre que deux départements.
3. Aucune granularité : impossible de réimporter un seul département après une
   correction.

`geo.api.gouv.fr` — API Découpage administratif, opérée par Etalab — expose la
**même donnée IGN ADMIN EXPRESS**, en GeoJSON, interrogeable par département et
sans clé d'accès.

## Décision

Le connecteur du pilote consomme `geo.api.gouv.fr`, département par département.

L'interface `AdministrativeBoundaryProvider` isole ce choix : le pipeline
d'import ne connaît que des `MunicipalityBoundary` normalisés. Passer aux
archives Géoplateforme ne touchera que l'adaptateur.

## Conséquences

**Favorables**

- Import d'un département en quelques secondes, réimportable isolément.
- Aucune manipulation d'archive, aucune dépendance supplémentaire.
- Même producteur de donnée que la source prescrite.

**Défavorables, à accepter explicitement**

- **La reproductibilité est plus faible que ce que demande le §9.5.** L'API
  n'expose pas la version du COG qu'elle sert. `source_version` enregistre donc
  le fournisseur et la date d'import, pas un millésime officiel. On ne peut pas
  affirmer « ces limites sont celles du COG 2026 » avec la même rigueur qu'en
  téléchargant l'archive versionnée.
- **Une dépendance à un intermédiaire** s'ajoute entre l'IGN et nous. Une panne
  d'Etalab bloque l'import, là où l'archive Géoplateforme aurait pu être
  conservée localement.
- `source_data_at` est renseigné à la date d'import faute de mieux, ce qui
  surestime légèrement la fraîcheur affichée sur `/statut`.

## Condition de réexamen

Avant le jalon F (ouverture nationale), pour l'une de ces raisons :

- besoin d'affirmer publiquement un millésime COG précis ;
- besoin de rejouer un import à l'identique pour un audit ;
- indisponibilité durable de `geo.api.gouv.fr`.

Le basculement consiste alors à écrire un second adaptateur lisant l'archive
Géoplateforme, sans toucher au pipeline ni au schéma.
