# Plan de développement MapFeux

**Dernière mise à jour** : 5 août 2026

Ce fichier est la **source unique de l'avancement** et le **seul** endroit où
vit le découpage en jalons.

| Document | Rôle |
|---|---|
| [Cahier de développement v1.1](../MapFeux_Cahier_de_developpement_v1.1.md) | Ce qu'il faut construire. Ne bouge qu'en révision. |
| [Stratégie](strategie.md) | Positionnement, périmètre, préalables, modèle économique, décisions ouvertes. Stable. |
| **Ce fichier** | Où l'on en est, ce qui reste, quelle est la prochaine action. Mis à jour à chaque session. |
| [Registre des ADR](adr/README.md) | Décisions techniques et écarts assumés au cahier. |

## Légende

| Marque | Sens |
|---|---|
| ✅ | Fait **et vérifié par exécution** |
| 🟢 | Fait, mais non exercé sur données réelles |
| 🟡 | En cours |
| ⬜ | À faire |
| ⚠️ | Point de vigilance ou dette assumée |

Un élément ne passe à ✅ que si quelque chose a réellement tourné : un test, un
build, une requête. « Le code est écrit » vaut 🟢, pas ✅.

---

## 1. Où en est le projet

**La chaîne complète répond**, vérifiée de bout en bout contre le projet
Supabase hébergé : navigateur → Next.js → PostgREST → schéma `api` → PostGIS.

**316 communes en base** — 163 dans les Alpes-Maritimes, 153 dans le Var. La
recherche trouve « Nice » comme « st etienne de tinee » sans accent ni tiret, un
point de Nice résout vers 06088, les fiches communales s'affichent.

**La fiche événement est en service**, sur un jeu de démonstration. Elle passe
son critère de sortie : les dix-neuf blocs attendus sont présents dans le HTML
rendu par le serveur, sans exécuter la moindre ligne de JavaScript — statuts,
horodatages, âge de la donnée, provenance, chronologie, tableau des détections,
avertissements.

**Le produit fonctionne de bout en bout sur données réelles.** 939 détections
importées sur 90 jours d'historique du 06 et du 83, regroupées en 124
événements. Les fiches affichent de vrais feux, avec leurs communes, leurs
capteurs, leur chronologie et leur puissance radiative.

**Le critère de sortie de J2 est atteint.** Un recalcul complet redonne
exactement la même empreinte du partitionnement — `66849fb15a6445ff` — et le
regroupement **par tranches** donne le même résultat qu'en bloc. Le contrôle est
rejouable : `scripts/verify-clustering.py`. Le résultat est explicable parce
qu'il est reproductible, et publiable parce que ce qui tourne toutes les dix
minutes produit ce qui a été calibré.

Le plus gros événement — 570 détections, six jours près de Pontevès — présente
un profil quotidien sans trou et des FRP jusqu'à 2197 MW. Un réglage plus serré
l'éclate en cinq foyers contigus et simultanés : c'est un vrai grand feu, pas un
chaînage de l'algorithme.

**Le corpus de quatorze saisons est constitué.** 337 757 détections VIIRS du
20 janvier 2012 au 2 août 2026, France métropolitaine et Corse, empreinte de
contenu `129f0347c2e6f77e`. C'est ce que débloquait la demande d'archive FIRMS,
et cela lève le préalable de la calibration multi-saisons.

**Une détection sur deux n'est pas de la végétation.** 165 629 lignes portent
`type = 2` — source thermique statique : 49,0 % du corpus, sur quatorze ans.
Ce n'est plus une intuition tirée d'une saison dans le Var, et c'est ce qui
fonde le masque des sources statiques. La carte publique montre aujourd'hui
cette moitié sans le dire.

### Portes de qualité — dernier passage

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 50 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 50 fichiers |
| Worker | `mypy src` | ✅ strict, 23 fichiers |
| Worker | `pytest` | ✅ 233 tests |

⚠️ Aucune de ces portes ne voit la couleur ni la taille effectives d'un
élément. Les 86 classes CSS invalides du §9 bis les ont toutes passées.

---

## 2. Prochaine action

**Monter la base de calibration**, puis y charger le corpus. C'est la seule
étape qui reste avant la calibration quatorze saisons, et elle est de votre
côté : un second projet Supabase ou un PostgreSQL local avec PostGIS, les
migrations, le seed, et `CALIBRATION_DATABASE_URL` dans
`services/geo-worker/.env`. La marche à suivre est au
[README](../README.md#base-de-calibration--à-monter-une-fois).

Tout le reste est en place : le plafond de passe est levé, l'importeur écrit,
et les outils qui font tourner des paramètres expérimentaux refusent désormais
de démarrer sur la base que le site public lit.

```bash
micromamba run -n mapfeux-geo python scripts/import-corpus.py --limite 5000
micromamba run -n mapfeux-geo python scripts/import-corpus.py
micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py
```

En parallèle, de votre côté :

- ouvrir les préalables de la [phase 0](strategie.md#3-phase-0--préalables-non-techniques),
  en particulier l'autorisation de cumul — c'est un point d'arrêt du projet ;
- poser le secret `FIRMS_MAP_KEY` côté GitHub : l'ingestion planifiée échoue à
  chaque déclenchement faute de ce secret, et le site affiche une fraîcheur
  exacte et mauvaise ;
- trancher les [décisions ouvertes](strategie.md#8-décisions-ouvertes), dont
  l'ordonnancement et le préfixe d'identifiant public.

---

## 3. Jalons

Hypothèse de charge : développement principalement solo, à temps partiel, en
parallèle d'un service de sapeur-pompier professionnel. Les durées sont en
**semaines calendaires**, pas en jours-homme.

| Jalon | Contenu | Estimé | Reste | État |
|---|---|---:|---:|---|
| J1 | Fondations et fiche événement sur données figées | 8 sem. | **1 sem.** | 🟡 critère de sortie atteint |
| J2 | Ingestion FIRMS et regroupement réel | 6 sem. | **2 sem.** | 🟡 critère de sortie atteint, calibration close |
| J3 | Carte et territoires | 6 sem. | **2 sem.** | 🟡 pilote livré |
| J4 | Informations officielles automatisées | 6 sem. | 6 sem. | ⬜ |
| J5 | Administration, supervision, mode dégradé | 5 sem. | 5 sem. | ⬜ |
| J6 | Recette, charge, sécurité, ouverture | 5 sem. | 5 sem. | ⬜ |
| | | 36 sem. | **21 sem.** | |

Les fondations, la fiche événement, la couche territoriale du pilote et
l'ingestion FIRMS étant livrées, il reste **environ 21 semaines** au lieu de 36.
Le reste de J2 tient à deux choses : déclencher l'ingestion et sortir les
fichiers bruts du disque local.

⚠️ Le phasage par rapport à la saison des feux est une
[décision ouverte](strategie.md#82-calendrier-et-saison) : les premiers jalons
tombent au moment où la disponibilité de l'auteur s'effondre, et une ouverture
au printemps ferait coïncider la première mise en charge réelle avec la première
crise majeure.

---

## 4. J1 — Fondations et fiche événement 🟡

Objectif : une page montrable très tôt, alimentée par un jeu de détections
historiques importé à la main.

### Livré ✅

- ✅ Monorepo pnpm/Turborepo, CI GitHub Actions, TypeScript strict, ruff et mypy
  strict côté Python
- ✅ Projet Supabase, dix schémas dont un seul exposé, grants révoqués par défaut
- ✅ Tables `events`, `detections`, `event_detections`, `event_history`,
  `event_timeline_entries`, `event_aliases`
- ✅ Contraintes en base sur les transitions de statut, dont l'interdiction faite
  aux traitements automatiques de renseigner un statut officiel (FR-047),
  doublée côté domaine — 12 tests
- ✅ `fire.detections` partitionnée dès l'origine ([ADR-015](adr/015-partitionnement-des-detections.md))
- ✅ Composants de statut, provenance et âge de donnée
- ✅ Vocabulaires contrôlés et formulations publiques obligatoires centralisés
- ✅ Dépôt publié : <https://github.com/emifrog/mapfeux>

- ✅ Route `/evenements/[publicId]` rendue côté serveur, avec les trois
  dimensions de statut jamais fusionnées et la provenance sur chaque bloc
- ✅ Chronologie textuelle triée par heure de survenue (FR-055)
- ✅ Tableau accessible des détections membres — alternative textuelle §8.6
- ✅ Redirection permanente des identifiants fusionnés (§13.10)
- ✅ Métadonnées de partage et URL canonique rendue côté serveur
- ✅ `GET /api/v1/fires/{publicId}`, `/timeline`, `/detections`
- ✅ Jeu de démonstration, cantonné à `supabase/seed/dev/` et signalé par un
  bandeau sur la fiche

- ✅ Snapshot public par événement (§21.5). La fiche lit le snapshot en
  priorité et se replie sur les tables vivantes en l'annonçant. Trois
  horodatages distincts et tous affichés : heure de service de la page, heure
  de construction de l'état figé, heure de la donnée elle-même.
- ✅ Bannière d'état figé ancien, conditionnée à la fraîcheur de l'événement :
  un snapshot vieux de trois jours est normal sur un événement sans nouvelle
  observation, et le signaler apprendrait à ignorer la bannière

### Reste ⬜

- ⬜ Authentification administrateur
- ⬜ Jeu historique réel en remplacement de la fixture
- ⬜ Déclencher le rafraîchissement du snapshot depuis les pipelines. Aujourd'hui
  `scripts/refresh-snapshots.py` le fait à la main ; le branchement viendra avec
  l'ingestion FIRMS.
- ⚠️ Aucune politique RLS de lecture pour les administrateurs : l'administration
  passera par des appels serveur privilégiés (§14.2). À confirmer en J5.

**Critère de sortie** : ✅ atteint. Les dix-neuf blocs attendus sont présents
dans le HTML rendu par le serveur, sans JavaScript ; aucun élément n'est affiché
sans provenance ni horodatage.

---

## 5. J2 — Ingestion FIRMS et regroupement 🟡

### Livré ✅

- ✅ Normalisation VIIRS et MODIS, clé d'idempotence, heures FIRMS sans zéro
  initial, rejet ligne à ligne — 23 tests
- ✅ Cycle de vie `import_run` (§16.1), exercé en conditions réelles par l'import
  des communes
- ✅ Environnement micromamba : ecCodes, GDAL, cfgrib, geopandas, rasterio

- ✅ Client HTTP avec gestion du 429 et de son `Retry-After` — 18 tests
- ✅ Détection des réponses 200 qui ne sont pas des CSV. FIRMS répond ainsi sur
  clé invalide : sans ce contrôle, l'import serait déclaré réussi en n'ayant
  rien importé, le pire des résultats puisqu'il est silencieux
- ✅ Découpage spatial de l'emprise avec tampon frontalier
- ✅ Archivage du fichier brut **avant** analyse, avec empreinte SHA-256
- ✅ Insertion idempotente vérifiée sur données réelles : rejeu à zéro doublon
- ✅ Un `import_run` par produit — un capteur indisponible n'empêche pas les
  autres, et `/statut` montre lequel a échoué
- ✅ Rattachement aux sources thermiques connues : classe la détection sans
  jamais la supprimer (FR-036)

- ✅ Chaîne d'ingestion enchaînée : `scripts/run-ingestion.py` importe, regroupe
  et reconstruit les seuls snapshots touchés, en un point d'entrée. Vérifié de
  bout en bout, 6 s sur le chemin incrémental
- ✅ Lecture du DSN factorisée dans `geo_worker.db`, avec 12 tests dont une
  régression sur le double encodage qui avait déjà cassé une connexion
- ✅ Recherche des candidats en mémoire — index de voisinage géodésique, 12
  tests dont une comparaison exhaustive. **Recalcul complet : 120,2 s → 1,8 s**,
  empreinte du partitionnement inchangée ([ADR-024](adr/024-recherche-spatiale-en-memoire.md))
- ✅ Verrou d'exécution : deux passes simultanées créeraient chacune un
  événement pour la même détection orpheline, et le perdant resterait sans
  membre. La seconde passe sort sans erreur, comme doit le faire une tâche
  périodique qui se recouvre
- ✅ Contrôle de reproductibilité rejouable : `scripts/verify-clustering.py`
- ✅ **Le regroupement par tranches donne le même résultat qu'en bloc**, vérifié
  sur 939 détections. Sans cette égalité, la carte servie au public ne serait
  pas celle qu'on a calibrée

### Reste ⬜

- 🟢 Planification toutes les dix minutes — workflow GitHub Actions, rôle
  `mapfeux_ingest` restreint, périmètre vérifié par 23 sondes. En attente des
  trois étapes de mise en service décrites au README : appliquer la migration,
  poser le mot de passe du rôle, déclarer les deux secrets
- ⬜ Déplacer les fichiers bruts vers Storage — ils sont aujourd'hui sur le
  disque local, sans rétention
- ✅ Algorithme de rattachement déterministe, paramètres versionnés (§17.2) —
  26 tests sur les fonctions pures
- ✅ Reproductibilité vérifiée sur 90 jours réels : recalcul complet, empreinte
  identique
- ✅ Score de fiabilité interne et seuils publics versionnés (§17.3)
- ✅ Génération idempotente des entrées de chronologie (FR-058)
- ✅ Import d'historique par tranches, corpus de calibration constitué
- ✅ Banc de calibration croisé : **112 combinaisons** rayon × fenêtre × seuil
  rejouées sur le corpus complet, résultats dans
  [`data/calibration/croise.csv`](../data/calibration/croise.csv)
- ✅ Inspection ciblée : `scripts/inspect-clustering.py` montre le profil
  temporel des plus gros événements, ce que les agrégats ne disent pas
- ✅ **Les paramètres de référence sont confirmés** — voir ci-dessous
- ✅ **Corpus de quatorze saisons constitué** — 337 757 détections VIIRS,
  20 janvier 2012 → 2 août 2026, France métropolitaine et Corse. Règles de
  fusion dans `geo_worker.corpus`, 26 tests ; point d'entrée
  `tools/fusion_corpus_firms.py`, qui lit les zips FIRMS directement et écrit
  un compte rendu à côté du Parquet
- ✅ **Le plafond de passe ne tronque plus en silence.** `cluster_detections`
  bornait chaque passe à 5 000 détections sans que l'appelant puisse le lever
  ni le savoir. Invisible sur 939 détections ; sur le corpus, le banc aurait
  mesuré 1,5 % — la tête, l'ordre étant chronologique — et publié ces chiffres
  sous le nom du corpus. `limit=None` lève la borne, `truncated` la signale, et
  `pending_detection_count` fait échouer banc et contrôle plutôt que d'écrire
  une mesure partielle
- 🟢 **Importeur du corpus vers `fire.detections`.** Chaque ligne repasse par
  `parse_row`, l'analyseur du flux temps réel : une observation du corpus et la
  même reçue en direct portent la même clé d'idempotence, donc le corpus se
  charge sur une base où l'ingestion a déjà tourné, et le script se rejoue sans
  dédoubler. Vérifié sur le corpus entier hors base — 337 757 lignes, **zéro
  rejet, zéro collision de clé**, et l'horodatage reconstruit par la règle R3
  de la fusion coïncide avec celui de l'analyseur sur **les 337 757 lignes**,
  par deux chemins indépendants. L'écriture elle-même n'a pas encore tourné :
  aucune base de calibration n'existe
- ✅ **Les outils expérimentaux ne peuvent plus viser la base publique.**
  `calibrate-clustering.py` et `inspect-clustering.py` exigent
  `CALIBRATION_DATABASE_URL` et refusent de démarrer si elle désigne la même
  base que `DATABASE_URL` — comparaison sur hôte, port et nom de base, non sur
  la chaîne : un rôle distinct sur la base de production est le cas le plus
  facile à confondre. Les deux refus vérifiés sur la configuration réelle
- 🟡 Calibration fine sur plusieurs saisons — il ne manque que la base

#### Ce que le corpus dit avant même d'être calibré

| `type` FIRMS | lignes | part |
|---|---:|---:|
| 2 — source thermique statique | 165 629 | **49,0 %** |
| 0 — végétation | 112 341 | 33,3 % |
| 3 — offshore | 12 526 | 3,7 % |
| absent | 47 261 | 14,0 % |

**Le masque des sources statiques ne peut pas être un filtre sur `type`.** La
colonne n'existe que dans le corpus retraité : `fire_nrt_*.csv` ne la porte
pas, et c'est le flux NRT que l'ingestion lit toutes les dix minutes. Les
165 629 lignes `type = 2` ne sont donc pas un filtre mais **quatorze ans de
vérité terrain** pour bâtir un registre spatial de sources statiques, appliqué
ensuite par proximité aux détections temps réel — la machinerie FR-036, qui
classe sans jamais supprimer.

⚠️ Le masque changera l'empreinte `66849fb15a6445ff`. Le changement doit être
mesuré, pas subi : d'où l'ordre — calibration d'abord, masque ensuite.

#### Ce que le balayage croisé a montré

Le premier banc ne faisait varier qu'un paramètre à la fois — huit jeux — parce
qu'un jeu coûtait deux minutes. Le regroupement en mémoire (ADR-024) ramène ce
coût à deux secondes, ce qui a permis de balayer le produit cartésien. Deux des
trois conclusions de la version précédente ne survivent pas.

**La proportion d'observations isolées bouge, en fait beaucoup** : de 45 % à
67 % selon le réglage. La version précédente la disait figée entre 50 et 56 % ;
c'était l'effet d'une grille trop étroite. Elle *monte* quand on desserre, ce
qui surprend jusqu'à ce qu'on regarde le dénominateur : des paramètres lâches
font absorber les détections corroborantes par quelques événements géants, si
bien que le nombre total d'événements chute plus vite que le nombre d'isolées.

**La corroboration multi-capteurs n'est pas un indicateur de qualité ici.** Elle
passe de 7 % (référence) à 28 % avec un rayon de 1000 m et une fenêtre de 48 h,
ce qui paraît décisif. Ce n'en est pas : le taux est une fraction, et son
dénominateur varie d'un facteur deux entre les jeux. Un réglage qui fragmente
davantage produit mécaniquement plus d'événements à deux capteurs *en
proportion*, sans qu'aucune observation soit mieux corroborée.

**Le chaînage, lui, se voit.** La diagonale maximale et le plus gros événement
croissent nettement avec le rayon et la fenêtre : jusqu'à 717 détections et
21,4 km à 4000 m / 48 h. Une diagonale de 21 km ne décrit plus un feu.

#### Pourquoi la référence est conservée

Le tableau seul ne tranchait pas : les deux fautes possibles produisent les
mêmes chiffres. Un réglage qui **découpe un grand feu réel** et un réglage qui
**sépare correctement deux feux voisins** donnent tous deux « plus d'événements,
plus petits ».

L'inspection du plus gros événement décide. Sous la référence, Pontevès
rassemble 570 détections sur 145 h, profil quotidien continu — 113, 185, 92, 92,
61, 25, 2 — sans un jour de trou, FRP jusqu'à 2197 MW.

Sous le réglage serré (1000 m, 48 h, 0,50), le même feu éclate en au moins cinq
événements : Pontevès 89, Montfort-sur-Argens 50, Correns 33, Pontevès 27,
Cotignac 24. Tous **contigus** — dans une boîte de 4 km sur 5 — et tous
**simultanés**, actifs du 21 au 25 juillet. Des feux distincts se séparent dans
l'espace ou dans le temps ; ceux-là ne se séparent ni dans l'un ni dans l'autre.
C'est un découpage, pas une distinction.

**Limite assumée** : que Pontevès soit un feu unique ou un complexe de foyers
adjacents ne se tranche pas depuis la donnée thermique satellitaire. Il faudra
l'information officielle (J4). D'ici là, la fiche décrit ce qui est observé —
une zone d'anomalies thermiques contiguës et continues — et rien de plus.

**La croissance du rayon reste quasi inerte** ; c'est la seule conclusion de la
version précédente qui tient. Le paramètre est figé hors de la surface de
calibration.

**Les temps mesurés ne sont pas exploitables** : de 116 s à 609 s pour un
travail identique. La variance confirme que le coût est dominé par les
allers-retours réseau, pas par le calcul.

⚠️ Le banc mesure la **sensibilité**, pas la **justesse**. Retenir le réglage
médian se défend — les réglages serrés fragmentent un feu dont on a établi par
ailleurs qu'il était réel — mais rien ici ne prouve que le regroupement est
correct. Cela demande une vérité terrain : ce que la presse et les préfectures
ont effectivement rapporté, c'est-à-dire le jalon J4.

#### La question que le balayage a fait surgir

Répartition des 122 événements de référence :

| fiabilité | événements | dont à 1 détection | détections portées |
|---|---:|---:|---:|
| faible | 103 | 65 | 151 |
| modérée | 12 | 0 | 66 |
| élevée | 7 | 0 | 714 |

**Sept événements portent 77 % des observations. Cent trois en portent 16 %.**

Ce n'est pas un défaut de réglage, c'est la nature du signal satellitaire : une
poignée de vrais feux, et une longue traîne d'anomalies thermiques ponctuelles —
brûlages agricoles, sites industriels, artefacts.

Ce n'est pas une question d'algorithme mais de **politique d'affichage**, et
elle est tranchée :
- ✅ Hiérarchie visuelle : disques pleins pour les événements étayés, anneaux
  creux et rayon réduit pour les observations isolées. Rien n'est masqué — le
  cahier l'interdit (§17.7)
- ✅ Liste scindée en « Événements étayés » et « Observations isolées », chacune
  comptée, avec la phrase qui dit ce que contient la seconde : brûlages
  agricoles, sites industriels, artefacts. Vérifié sur données réelles :
  **20 étayés, 103 isolées**
- ⬜ Fusion et séparation manuelles réversibles
- ⬜ `GET /api/v1/fires` avec bbox obligatoire au-delà du seuil national
- ⬜ Détection des candidats à la fusion, sans fusion silencieuse (§17.2, étape 8)
- ⬜ ADR-006 et ADR-012 à rédiger
- ⚠️ L'ordonnanceur reste une [décision ouverte](strategie.md#81-ordonnancement--revenir-à-celery-et-redis).

**Critère de sortie** : rejouer une saison historique produit des événements
stables ; deux exécutions successives donnent le même résultat.

---

## 6. J3 — Carte et territoires 🟡

### Livré ✅

- ✅ Import des limites communales — 316 communes, aucun rejet
  ([ADR-017](adr/017-source-des-limites-communales.md))
- ✅ Staging, `ST_MakeValid`, `ST_CollectionExtract`, publication
  transactionnelle ; commune disparue datée et non supprimée (§13.2)
- ✅ Carte MapLibre, fond Géoplateforme IGN, attribution permanente — tuiles
  vérifiées dans un navigateur
- ✅ Recherche de commune : combobox ARIA, navigation clavier, annulation des
  requêtes obsolètes, dégradation explicite en cas de panne (FR-026)
- ✅ `GET /api/v1/territories`, `/municipalities/{insee}`, `/search`
- ✅ `POST /api/v1/location/resolve` — position en corps de requête et non en
  URL, car les URL atterrissent dans les journaux des CDN (§22.2)
- ✅ Pages `/carte`, `/territoire/[slug]`, `/commune/[insee]`, `/statut`
- ✅ Couche d'accès partagée : une page rendue serveur n'appelle pas sa propre
  API par HTTP

### Reste ⬜

- ✅ Affichage des événements sur la carte, cliquables vers leur fiche
- ✅ Liste textuelle rendue serveur, fonctionnelle sans JavaScript (§8.6)
- ✅ Légende avec pastille **et** libellé, expliquant que la taille d'un marqueur
  suit le nombre d'observations et non la gravité (FR-049)
- ✅ `GET /api/v1/fires`, emprise obligatoire, rechargement au déplacement (FR-007)
- ⬜ **Génération PMTiles**, sans GeoJSON national servi en direct
- ⬜ Agrégation par département à l'échelle nationale (§21.3)
- ⬜ Géométries des régions et départements : seuls les quatre territoires du
  seed existent, avec un centre mais sans emprise
- ⬜ Import des 99 autres départements
- ⬜ Bouton « Autour de moi » — l'endpoint existe, le bouton reste à poser
- ⬜ Sélecteur de territoire groupé par région (FR-012)
- ⬜ Indicateurs de fraîcheur par couche
- ⚠️ `source_version` enregistre le fournisseur et la date d'import, pas un
  millésime COG officiel — assumé en ADR-017.

**Critère de sortie** : chargement initial sous 2,5 s en 4G sur mobile de
milieu de gamme ; la carte reste utilisable si FIRMS est indisponible.

---

## 7. J4 — Informations officielles ⬜

Le jalon différenciant. Capter automatiquement ce que publient les autorités,
sans jamais le réécrire.

- ✅ Modèle `app.official_messages` : organisme, URL source, date de publication,
  période de validité, territoire, événement lié, validateur
- 🟢 **Vigilance Météo-France** — format V6, 9 phénomènes, 96 départements et
  25 pourtours littoraux. Adaptateur, 23 tests, migration et pipeline validés en
  transaction annulée sur un bulletin réel : 1216 niveaux, zéro rejet, rejeu
  idempotent. Reste à appliquer la migration
  - Voie **sans clé** : l'API temps réel de Météo-France en exige une, le dépôt
    objet de data.gouv.fr sert les mêmes produits sous Licence Ouverte
    Etalab v2. L'adaptateur du cahier §9.2 rend le point d'accès remplaçable
  - Les correspondances de codes viennent du descriptif technique officiel, pas
    d'une supposition : publier « orange » pour le mauvais phénomène serait la
    désinformation que §2.4 interdit
  - ⚠️ Piège du format, explicité par le descriptif : **les crues n'ont jamais
    de chronologie**. Un analyseur lisant `timelaps_items` perdrait toute
    vigilance crue en silence — 194 niveaux sur le seul bulletin d'essai
- ⬜ Connecteurs restants : flux RSS préfectoraux, pages de communiqués,
  arrêtés d'accès aux massifs
- ⬜ Rapprochement géographique entre une information officielle et un événement
- ⬜ Affichage strictement distinct des estimations automatiques (FR-104)
- ⬜ Gestion des contradictions entre observation satellitaire et statut officiel
- ⬜ ADR à rédiger sur la politique de republication
- ⚠️ La validation humaine avant publication est une
  [décision ouverte](strategie.md#83-validation-humaine-des-informations-officielles) :
  telle qu'écrite, elle annule le bénéfice de l'automatisation.

**Critère de sortie** : une information préfectorale publiée est visible sur la
fiche de l'événement correspondant en moins de 30 minutes, attribuée et datée,
sans réécriture.

---

## 8. J5 — Administration et exploitation ⬜

- ⬜ Authentification par lien magique, MFA obligatoire pour `super_admin`
- ⬜ `proxy.ts` pour le rafraîchissement de session
- ⬜ Tableau de bord de santé des sources
- ⬜ Gestion des événements : masquer, fusionner, séparer, classer en source
  thermique connue, corriger
- ⬜ Workflow d'information officielle attribuée, validé par un second regard
- ✅ Journal d'audit append-only, garanti par trigger
- ✅ Page `/statut` publique
- ⬜ Mode dégradé : timeouts, dernier snapshot valide, bannières explicites,
  aucun chargement indéfini (FR-115)
- ⬜ Observabilité : métriques, alertes sur retard d'import et snapshot ancien
- ⬜ Runbooks écrits pour les cinq pannes les plus probables (§23.4)
- ⚠️ Toute mutation exige un motif : la contrainte est en base, l'interface doit
  la respecter et non la contourner.

**Critère de sortie** : couper FIRMS, la météo et le réseau tour à tour ; le
site reste consultable et dit exactement ce qui manque et depuis quand.

---

## 9. J6 — Recette et ouverture ⬜

- ⬜ Tests E2E Playwright sur les parcours publics et administrateur
- ⬜ Tests de contrat fournisseur avec réponses figées
- ⬜ Tests géospatiaux : enclave, Corse, frontière maritime, point sur limite,
  proximité de Monaco (§24.3)
- ⬜ Test de charge : pic de crise, 200 000 visites/jour sur un département
- ⬜ **CSP avec nonces**, revue RLS, revue des fonctions `security definer`
- ⬜ Revue de sécurité indépendante
- ⬜ Audit RGAA 4.1 niveau AA et déclaration d'accessibilité
- ⬜ Pages légales, méthodologie, limites, confidentialité
- ⬜ Test de sauvegarde et de restauration
- ⬜ Checklist de mise en production (annexe G)
- ⬜ Ouverture progressive : 06 et 83, puis Sud-Est, puis national

---

## 9 bis. Chantiers transverses

Deux chantiers ne relèvent d'aucun jalon en particulier et se poursuivent en
parallèle. Ils manquaient à ce fichier ; les voici, à leur état réel.

### Refonte visuelle 🟡

Direction validée en deux règles : l'orange appartient à l'observation
thermique et à elle seule, le site empruntant le bleu d'autorité pour ses
affordances ; ce qui est mesuré passe en chasse fixe, ce qui est affirmé reste
en linéale.

- ✅ Fondations : jetons, échelle typographique de 10,5 à 46 px, bandeau de
  positionnement récrit pour être lu plutôt qu'ignoré
- ✅ Coque et fiche événement
- ✅ Thème sombre éclairci, bascule à trois états — clair, auto, sombre — posée
  sur le document avant la première peinture
- ✅ **Le système s'applique enfin.** 86 classes employaient la syntaxe de
  variables de Tailwind v3, `text-[--text-2]`, que la v4 ne reconnaît plus comme
  une référence : elle compilait en `color: --text-2`, du CSS invalide que le
  navigateur écarte. Couleurs de texte, couleurs de bordure et **toute
  l'échelle typographique** de la refonte tombaient ainsi en silence. Migrées
  vers `text-(--text-2)` ; vérifié sur le CSS produit, zéro déclaration
  invalide restante
- ✅ Garde-fou : `apps/web/src/styles.test.ts` refuse l'ancienne syntaxe. Les
  fichiers de test sortent du balayage Tailwind — sans quoi le test engendrait
  lui-même les règles qu'il proscrit, ses exemples étant lus comme des classes
- ✅ **Carte et liste.** La carte prend toute la largeur de la coque, la lecture
  reste en colonne ; la légende passe à côté d'elle sur grand écran, au lieu de
  tomber hors de vue sous la carte. La liste emprunte les symboles de la carte
  — disque plein pour un événement étayé, anneau creux pour une observation
  isolée — plutôt que d'inventer un second vocabulaire pour la même distinction
- ✅ **Gabarit `Prose`**, qui porte six pages de contenu d'un coup. Surtitre
  classant — « légal », « méthode », « provenance » — parce que six pages au
  même gabarit ne se distinguaient qu'en lisant leur titre
- ✅ **Accueil** : échelle typographique, avertissement au filet orange comme
  les bandeaux d'état de la fiche
- ✅ Utilitaires canonisés : les paliers déclarés dans `@theme` engendrent déjà
  `text-small`, `text-title`, `rounded-md`. Trente classes passaient par la
  valeur arbitraire pour produire exactement la même règle
- ⬜ Restent `/statut`, `/commune/[insee]`, `/territoire/[slug]`
- ⚠️ Le libellé du titre d'accueil n'a pas été touché : une formulation
  publique passe par une validation métier, pas par une passe de style
- ⚠️ Le rendu réel n'a toujours pas été regardé dans un navigateur. Le défaut
  ci-dessus est exactement ce que « vérifié par construction » ne voit pas :
  lint, typage, tests et construction passaient tous

### Archivage AROME 🟡

Champs météo archivés au fil de l'eau, la donnée étant périssable — un jour non
capté est perdu définitivement ([ADR-025](adr/025-plateforme-a-deux-visages.md)).

- ✅ Adaptateur découplé du panache : ADR-025 en faisait dépendre l'archivage
  d'un jalon que la stratégie a supprimé, donc le corpus n'aurait jamais commencé
- ✅ Voie sans clé par le dépôt objet data.gouv.fr, comme pour la vigilance
- ✅ Emprise nationale : réduire l'emprise plus tard reste possible, l'élargir
  rétroactivement non
- ✅ `next_reachable_noon` — à dix-huit heures UTC la mi-journée est hors de
  portée du run, et une exécution d'après-midi sur deux échouait
- ⬜ **`archive-arome.py` échoue au dépôt** : le compartiment `raw` n'existe pas
  — « Bucket not found ». Tout le reste de la chaîne a tourné en conditions
  réelles : paquet de 59,7 Mo téléchargé, cinq champs extraits, emprise
  nationale découpée, extrait NetCDF prêt à déposer
- ⚠️ ADR-025 chiffre l'archivage à un coût « quasi gratuit » que la mesure
  dément : 56 Mo par tranche de six heures. D'où l'extrait, et non le paquet

### Journalisation ✅

Deux fuites de secrets, trouvées en exerçant AROME et corrigées le 5 août.

- ✅ **Les traces ne rendent plus les variables locales.** Aucun script
  n'appelait `configure_logging` : structlog appliquait sa configuration par
  défaut, dont le formateur d'exceptions de `rich`, qui déroule la pile *avec
  le contenu des variables*. Un dépôt Storage refusé a ainsi imprimé la clé
  secrète Supabase en clair. Le paquet se configure désormais à l'import — la
  classe de défaut disparaît au lieu d'une occurrence
- ✅ **`httpx` ne journalise plus les URL.** Il écrivait « HTTP Request: GET
  <url> » à chaque appel, en INFO. Anodin ailleurs, grave pour FIRMS : l'API
  Area porte la clé **dans le chemin**. Le connecteur prenait soin de ne jamais
  l'écrire ; la bibliothèque le faisait à sa place, à chaque requête et non
  seulement en cas d'erreur — donc dans les journaux d'un dépôt public, toutes
  les dix minutes, dès que l'ingestion planifiée démarrera
- ✅ Non-régression : 12 tests, dont un qui journalise une exception portant un
  faux secret en variable locale et vérifie qu'il n'apparaît pas, la trace
  restant exploitable
- ⚠️ La clé exposée reste à régénérer — voir §10

---

## 10. Dettes et points de vigilance

| Sujet | Nature | Échéance |
|---|---|---|
| Préalables de phase 0 non engagés | Autorisation de cumul, cadre juridique — point d'arrêt | Immédiat |
| Décisions ouvertes non tranchées | Ordonnancement, calendrier, validation, préfixe | Avant J2 |
| CI jamais observée en vert | Premier déclenchement au commit initial | Immédiat |
| **`SUPABASE_SECRET_KEY` à régénérer** | Imprimée en clair dans une trace du 5 août. La cause est corrigée, la clé reste compromise | Immédiat |
| Ingestion planifiée en échec à chaque déclenchement | Le secret `FIRMS_MAP_KEY` n'est pas posé côté GitHub | Immédiat |
| Compartiments Storage à créer | `raw` et `derived`, privés. `archive-arome.py` échoue sur « Bucket not found » ; la chaîne fonctionne jusque-là | Immédiat |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | J1 |
| Pas de CSP | En-têtes partiels seulement | J6 |
| Aucun test de composant | Recherche et carte n'ont que le typage | J6 (Playwright) |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des jalons |
| Schémas `air` et `radar` vides | Tables reportées en v2 avec le panache. `meteo` porte désormais la vigilance | v2 |
| `app.official_messages` inutilisable par une ingestion | La table exige un `created_by` humain et un `validated_by` : la vigilance a donc ses propres tables. La [décision §8.3](strategie.md#83-validation-humaine-des-informations-officielles) reste ouverte pour les sources en texte libre | J4 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| Fichiers bruts FIRMS sur disque local | Ni Storage, ni rétention : ils s'accumulent | J2 |
| Regroupement encore lent | Le coût quadratique des agrégats est levé, mais il reste une requête de candidats par détection. À surveiller avant la montée en charge (§6.3) | J6 |
| Base de calibration à monter | Dernier point bloquant la calibration multi-saisons. Le banc efface et réécrit `fire.events` pendant des heures ; les outils refusent désormais la base publique, donc rien ne tourne tant qu'elle n'existe pas | Immédiat |
| Écriture du corpus jamais exercée | L'importeur est couvert sur la normalisation, y compris sur le corpus réel, mais son chemin SQL — `COPY`, table de transit, 176 partitions — n'a jamais atteint une base. Le premier chargement est un essai autant qu'un import | Avec la base de calibration |
| N21 sans corpus retraité | 30 180 lignes — 8,9 % du corpus — de janvier 2024 à août 2026, servies en NRT faute d'archive publiée par FIRMS. Ni retraitement scientifique, ni `type` : les deux saisons les plus récentes sont partiellement non étiquetées | J2 |
| La borne de R4 suppose le corpus standard dense | Un satellite indisponible en milieu de période retraitée verrait ses lignes NRT de la panne écartées à tort. FIRMS ne publie pas de calendrier de couverture. La borne employée est consignée dans le compte rendu du corpus | J2 |
| Corpus dérivé versionné | Le Parquet pèse 6,8 Mo et se régénère depuis les zips. Chaque régénération dépose un nouveau blob dans l'historique. À arbitrer : le compte rendu JSON suffit à prouver la provenance | J6 |
| `api.fire_events` expose l'`id` interne | §15.1 demande des identifiants publics opaques. Non exploité par nos réponses, mais lisible via PostgREST | J6 |
| Coût d'un pic non chiffré | Conditionne un point d'arrêt | Phase 0 |
| Réponse à la première erreur publique | Runbook éditorial absent | Avant J6 |

---

## 11. Tenue de ce fichier

À la fin de chaque session :

1. Mettre à jour la date en tête.
2. Faire passer les éléments terminés à 🟢, et à ✅ **seulement** après exécution.
3. Rafraîchir le tableau des portes de qualité si elles ont tourné.
4. Réécrire la section « Prochaine action » — elle ne doit contenir qu'une chose.
5. Ajouter toute dette nouvelle au tableau du §10 plutôt que de la laisser
   implicite dans le code.
6. Consigner dans [docs/adr/](adr/) tout écart au cahier, et l'ajouter à la liste
   du registre.

Le positionnement, le périmètre et les conditions d'arrêt ne se modifient pas
ici mais dans [strategie.md](strategie.md).

Une décision qui touche le périmètre, la séparation public/opérationnel, les
sources de données ou l'exposition des schémas Supabase passe par un ADR
**avant** implémentation, pas après.
