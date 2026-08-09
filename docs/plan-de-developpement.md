# Plan de développement MapFeux

**Dernière mise à jour** : 8 août 2026 — tuiles PMTiles générées, publiées et
vérifiées (compartiment public, cache long, communes au zoom 11 — plafond du
plan gratuit) ; le banc sait reprendre (`--reprendre`), balayage en reprise
après sa troisième mort ; auth admin et territoires livrés la veille.

Ce fichier est la **source unique de l'avancement** et le **seul** endroit où
vit le découpage en jalons.

| Document | Rôle |
|---|---|
| Cahier des charges v2.1 (PDF, 5 août 2026, hors dépôt) | Ce qu'il faut construire — **document maître**. Toute divergence se règle par ADR ou par révision du cahier, jamais en silence. |
| [Cahier de développement v1.1](../MapFeux_Cahier_de_developpement_v1.1.md) | Version précédente du cahier, conservée pour l'historique et les références « cahier §x » des commits antérieurs au 5 août. |
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

**L'ingestion tourne enfin toute seule.** Le 5 août au soir, la chaîne planifiée
a produit sa première passe réussie : 11 détections importées, 2 événements
créés, 9 rattachements, 6 snapshots reconstruits, en 86 s. La fraîcheur affichée
est passée de huit jours à moins d'une minute.

Le blocage n'était pas celui qu'on croyait. `FIRMS_MAP_KEY` était posée depuis
trois jours ; le rôle `mapfeux_ingest` existait avec ses vingt-et-un droits de
table, **mais sans mot de passe** — le pooler répondait
`(EAUTHQUERY) unsupported or invalid secret format`. L'étape 1 des trois du
README avait été sautée, et personne n'avait lu les journaux de la CI.

**Le corpus de quatorze saisons est constitué.** 337 757 détections VIIRS du
20 janvier 2012 au 2 août 2026, France métropolitaine et Corse, empreinte de
contenu `129f0347c2e6f77e`. C'est ce que débloquait la demande d'archive FIRMS,
et cela lève le préalable de la calibration multi-saisons.

**Une détection sur deux n'est pas de la végétation.** 165 629 lignes portent
`type = 2` — source thermique statique : 49,0 % du corpus, sur quatorze ans.
Ce n'est plus une intuition tirée d'une saison dans le Var, et c'est ce qui
fonde le masque des sources statiques. La carte publique montre aujourd'hui
cette moitié sans le dire.

**Le plan est recalé sur la décision D-0 — option A, périmètre intégral**
(cahier v2.1 §26.1, confirmée le 5 août, répercutée ici le 6). La version
précédente de ce fichier suivait le périmètre allégé de la stratégie v1.0 :
sans panache, sans CAMS ni radar, sans périmètres versionnés, sans relecture
ni catalogue. Ces blocs reviennent sous quatre jalons nouveaux (J7 à J10), et
le total restant passe d'environ 21 à environ 51 semaines — le haut de la
fourchette 40-50 que la D-0 annonce en solo.

**L'API et les pages disent désormais « événement ».** `/api/v1/fires` est
devenu `/api/v1/events`, `/detections` est devenu `/observations`, `/commune`
et `/territoire` passent au pluriel (cahier v2.1 §7.1 et §15.2). Le motif
n'est pas cosmétique : le vocabulaire public (§2.4) interdit de présenter une
détection comme un feu, et l'ancienne API s'appelait précisément « fires ».
Renommé avant que la moindre URL ne devienne permanente ; redirections 308
posées dans `next.config.ts` ; la fonction SQL `fires_in_bbox` garde son nom,
interne. Portes repassées après renommage : format, lint, typecheck, tests,
build — vertes.

### Portes de qualité — dernier passage

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 58 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 57 fichiers (worker 41, scripts 16) |
| Worker | `mypy src` + `mypy scripts` | ✅ strict, 25 + 16 fichiers |
| Worker | `pytest` | ✅ 276 tests |
| Migrations | 23 migrations sur base vierge, en CI | ✅ |

⚠️ Aucune de ces portes ne voit la couleur ni la taille effectives d'un
élément. Les 86 classes CSS invalides du §14 les ont toutes passées.

---

## 2. Prochaine action

**Clore la calibration : la validation des finalistes tourne sur le corpus
complet, le dépouillement est rendu.**

Dépouillement du 8 août, sur les 112 jeux et l'inspection des quatre têtes de
liste :

- **La référence `grouping-v1` (r2500, w24, s0.35) gagne.** Trois cribles —
  Landiras intact, pas de chaînage, part étayée — ne laissent que la famille
  `w24 × s0.35-0.50` plus deux compensations extrêmes (`w48-s0.65`).
  L'inspection tranche : la référence capture le plus de Landiras (2 069
  détections, profil quotidien continu, 132 h) tout en tenant La Teste-de-Buch
  **séparée** ; r1500 perd 543 détections du vrai feu sans rien gagner ;
  l'intrus r4000-w48-s0.65 capture *moins* de Landiras que la référence — son
  seuil rejette les bords faibles d'un feu réel. Dominé, éliminé.
- **Aucun jeu ne résout Berre — et c'est la leçon.** Les quatre inspections
  produisent le **même** pseudo-événement industriel : 622 détections,
  **529 h (22 jours)**, diagonale 4,3 km, à 43.443/4.892 (Fos-sur-Mer). Une
  torchère émet chaque jour au même endroit : toute fenêtre qui enjambe les
  nuits d'un vrai feu la chaîne. Le remède n'est pas un paramètre, c'est le
  **masque des sources statiques (J10)** — la strate industrielle du
  sous-corpus a été construite pour prouver exactement cela, et l'événement
  de Fos devient le **test d'acceptation du masque** : après J10, il doit
  être classé source connue, pas servi comme événement.
- La validation des trois finalistes (`r2500/r2000/r1500 × w24-s0.35`) sur
  les quatorze saisons est **en cours** — corpus complet rebasculé
  (`--remplacer`), résultats attendus dans
  `data/calibration/jeux-finalistes.csv`. Si le classement du sous-corpus s'y
  confirme, `grouping-v1` est **gelé** et la prochaine action devient le
  registre spatial des sources statiques (J10).

La question de la taille du balayage est tranchée par la troisième issue de la
version précédente de cette section : **calibrer sur un sous-corpus
représentatif**, et ne rejouer que les finalistes sur quatorze saisons. Le
sous-corpus est en service (voir §5) et la mesure du 6 août au soir a fixé le
coût : **102 à 161 s par jeu** sur ses 16 544 détections — moyenne ~123 s,
réseau dominant, comme toujours — contre plus de dix minutes sur le corpus
complet (`data/calibration/axes-sous-corpus.csv`).

Le balayage croisé à 112 jeux est **en cours de reprise** — quatrième
lancement, le 8 août à 10 h 12, après trois morts instructives : extinction du
poste (6 août, un jeu perdu faute d'écriture au fil de l'eau), timeout mal
traité (7 août 18 h 10), **mise en veille du poste** (7 août 20 h 56, 43 jeux
acquis). Chaque mort a durci le banc : CSV au fil de l'eau, timeout de session,
échec d'un jeu isolé, rollback avant restauration, et désormais
**`--reprendre`** — les jeux déjà sur disque sont sautés, le fichier est
complété au lieu d'être réécrit. L'interruption est devenue banale.

Rythme réel mesuré : **~3,3 min par jeu** (43 jeux en 2 h 21 le 7 au soir).
Reste 69 jeux ≈ 4 h — fin attendue le 8 août en début d'après-midi, **poste
allumé et veille désactivée d'ici là**. Résultats dans
`data/calibration/croise-sous-corpus.csv` ; la base de calibration reste à
tout instant sur le dernier jeu commité, jamais vide.

Au dépouillement :

- retenir au plus une dizaine de finalistes — les indicateurs ne tranchent pas
  seuls, l'inspection du plus gros événement décide, comme pour Pontevès ;
- ⚠️ `≥2 capt` vaut 0 % sur tout le sous-corpus et n'y départage rien : le
  corpus est VIIRS seul, et R2 normalise l'instrument — la colonne mesure les
  capteurs, pas les satellites ;
- la passe de validation est outillée : rebasculer la base sur le corpus
  complet (`import-corpus.py --remplacer`), puis
  `calibrate-clustering.py --jeux <étiquettes> --etiquette finalistes` — les
  étiquettes se copient depuis la colonne `version` du CSV, une nuit au plus.

Côté [phase 0](strategie.md#3-phase-0--préalables-non-techniques) :
**l'autorisation de cumul est accordée depuis le 6 août** — le point d'arrêt
correspondant du [§7](strategie.md#7-conditions-darrêt) est levé — et le cadre
juridique de l'édition est posé. L'estimation du coût d'un pic (§3.5) reste le
dernier préalable non traité. Restent aussi, de votre côté, trois
[décisions ouvertes](strategie.md#8-décisions-ouvertes) : la validation
humaine des informations officielles (§8.3), le préfixe d'identifiant public
(§8.4, à figer avant la première URL durable) et la réponse à la première
erreur publique (§8.5). L'ordonnancement (§8.1) et le calendrier (§8.2, tranché
par D-0 : lancement hors pic saisonnier) ne sont plus ouverts.

---

## 3. Jalons

Hypothèse de charge : développement principalement solo, à temps partiel, en
parallèle d'un service de sapeur-pompier professionnel. Les durées sont en
**semaines calendaires**, pas en jours-homme.

Le découpage suit la **décision D-0 (option A)** : périmètre v2.0 intégral à
l'ouverture publique. La numérotation J1-J6 est historique ; J7 à J10 portent
les blocs réintégrés par D-0. **L'ordre du tableau est l'ordre d'exécution
prévu**, aligné sur les phases du cahier v2.1 (§26.3) rappelées en colonne.

| Jalon | Contenu | Phase cahier v2.1 | Estimé | Reste | État |
|---|---|---|---:|---:|---|
| J1 | Fondations et fiche événement sur données figées | 1-4 (socle) | 8 sem. | **1 sem.** | 🟡 critère de sortie atteint |
| J2 | Ingestion FIRMS et regroupement réel | 2-3 | 6 sem. | **2 sem.** | 🟡 critère de sortie atteint, calibration close |
| J3 | Carte et territoires | 3 | 6 sem. | **2 sem.** | 🟡 pilote livré |
| J7 | Expérience FeuScope complète : catalogue, archives, relecture, partage | 4 — gate G4 Alpha | 10 sem. | 10 sem. | ⬜ |
| J8 | Météo et panache : vent, panache indicatif, communes concernées | 5 — gate G5 | 6 sem. | 6 sem. | ⬜ |
| J9 | CAMS, radar et périmètres versionnés | 6 — gate G6 | 8 sem. | 8 sem. | ⬜ |
| J10 | Sources statiques et réconciliation NRT/standard | 7 | 2 sem. | 2 sem. | ⬜ |
| J4 | Informations officielles automatisées | 8 (partiel) + ajout stratégie §4 | 6 sem. | 6 sem. | ⬜ vigilance déjà en service |
| J5 | Administration, supervision, mode dégradé | 8 — gate G7 | 5 sem. | 5 sem. | ⬜ |
| J6 | Durcissement, recette, pilote et ouverture | 9-11 — gates G8-G10 | 9 sem. | 9 sem. | ⬜ |
| | | | 66 sem. | **≈ 51 sem.** | |

Il reste **environ 51 semaines** — le haut de la fourchette 40-50 que la D-0
annonce pour un développement principalement solo depuis l'état de départ. Le
recalage du 6 août ajoute 30 semaines au total précédent (21) : c'est le prix,
connu et accepté, du périmètre intégral. L'option C (renfort ou partenariat,
24-30 semaines en équipe) reste ouverte à tout moment et resserre le
calendrier sans toucher au périmètre.

Le calendrier par rapport à la saison est
[tranché par D-0](strategie.md#82-calendrier-et-saison--tranché-le-5-août-2026-d-0) :
lancement hors pic saisonnier (automne-hiver), hypercare avant l'été suivant.
⚠️ Le point de vigilance demeure : plusieurs jalons intermédiaires tombent en
pleine saison des feux, au moment où la disponibilité de l'auteur s'effondre.

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
- ✅ `GET /api/v1/events/{publicId}`, `/timeline`, `/observations` — livrés
  sous le nom `fires`/`detections`, renommés le 6 août (cahier v2.1 §15.2),
  redirections 308 posées
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

- ✅ **Authentification administrateur, exercée en production le 7 août** —
  lien magique sans mot de passe (§14.4). Le rôle vit dans `admin.profiles`,
  jamais dans le jeton (doctrine de la migration du 27 juillet) ; le web le
  lit par `api.admin_profile()` (migration `20260807200000`, grant à
  `authenticated` seul). Pièces : `proxy.ts` (rafraîchissement de session,
  périmètre `/admin` seulement — les pages publiques restent sans cookie donc
  cachables), `/admin/connexion` (anti-énumération, `shouldCreateUser:
  false`), `/auth/callback` (PKCE et `token_hash`), layout de garde (profil
  **actif** exigé, impasse explicite sinon), `scripts/grant-admin.py` — seul
  chemin d'entrée d'un administrateur. Cycle complet vérifié sur
  mapfeux.vercel.app : envoi du lien et réception, session par `token_hash`,
  profil et rôle affichés, session active renvoyée de la page de connexion
  vers `/admin`, déconnexion, `/admin` sans session renvoyé à la connexion
- ⚠️ **`PUBLIC_APP_URL` absente de l'environnement Vercel** : l'action de
  connexion retombe sur sa valeur par défaut et les liens des e-mails
  redirigent vers `http://localhost:3000`. Trouvé par le test réel — le lien
  reçu était inutilisable en production. À poser dans Vercel
  (`https://mapfeux.vercel.app`) puis redéployer ; c'est le dernier geste
  avant que le parcours e-mail complet ne fonctionne
- ✅ Jeu historique réel en remplacement de la fixture — la production tourne
  sur données réelles depuis le 5 août (ingestion planifiée, 939 détections
  d'historique) ; la fixture ne vit plus qu'en `seed/dev/` pour le poste local,
  exclue de la calibration comme de la production
- ✅ Rafraîchissement du snapshot déclenché depuis les pipelines — en service
  depuis le 5 août : `run-ingestion.py` reconstruit les seuls snapshots touchés
  à chaque passe (première passe réelle : 6 reconstruits). La ligne était
  restée ouverte alors que l'acquis était déjà consigné au J2
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
- ✅ Archivage du fichier brut **avant** analyse, avec empreinte SHA-256, dans
  le compartiment `raw` — **sur les deux chemins**. La ligne portait cet acquis
  depuis J2 alors que seul l'import manuel l'assurait ; la chaîne planifiée, qui
  alimente le site, ne conservait rien. Depuis le passage chez GitHub Actions,
  « ne rien conserver » était devenu définitif, le disque du runner disparaissant
  avec le passage
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

- ✅ **Planification toutes les dix minutes, en service.** Première passe réussie
  le 5 août : 11 détections, 2 événements, 9 rattachements, 6 snapshots, 86 s.
  Il aura fallu, outre les trois étapes du README, un `grant usage on schema app`
  que la migration du rôle avait omis — le regroupement convertit vers
  `app.confidence_level` et `app.provenance`, et échouait au dernier temps de la
  passe. La panne de connexion masquait ce second défaut
- ✅ Fichiers bruts dans Storage : compartiment `raw`, arborescence par jour,
  chemin et empreinte consignés dans l'`import_run`
- ⬜ Rétention : le compartiment `raw` est annoncé à trente jours, aucun job de
  purge n'existe. `cold` en est exclu par construction et doit le rester
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
- ✅ **Base de calibration en service** — projet Supabase `mapfeux-calibration`,
  eu-west-2. `scripts/setup-calibration-db.py` monte les 23 migrations et le
  seed sans toucher au lien Supabase de production : la cible vient de
  `CALIBRATION_DATABASE_URL`, jamais d'un état enregistré. `seed/dev/` en est
  exclu — des événements inventés fausseraient toutes les mesures
- ✅ **Corpus chargé** : 337 757 détections en 133 s, 2 568 lignes/s à travers
  le pooler, 176 partitions mensuelles, zéro rejet. L'idempotence tient à
  l'échelle — les 20 000 lignes de l'essai préalable ont été reconnues, aucune
  dupliquée
- ✅ **Sous-corpus de calibration stratifié** — `sous-corpus-v1`, 16 544
  détections (4,9 % du corpus), cinq strates éprouvées par 10 tests et
  chacune rattachée à un cas de recette (§24.8) : grand feu de plaine
  (Gironde 2022), grand feu en relief littoral (Gonfaron 2021), zone
  industrielle sur une année (Berre 2023, 86 % type 2), saison pilote 06/83
  2026 (Pontevès, flux NRT sans `type`), été épars (2018). Recouvrement nul,
  empreinte de contenu `033d40568951e882`, compte rendu JSON versionné — le
  Parquet, régénérable à l'identique, ne l'est pas (`.gitignore`). Règles dans
  `geo_worker.subcorpus`, point d'entrée `scripts/build-subcorpus.py`
- ✅ **Bascule de corpus transactionnelle** : `import-corpus.py --remplacer`
  vide événements algorithmiques et détections orphelines **dans la
  transaction du chargement** — tout ou rien, la leçon du 6 août. Le prédicat
  « algorithmique » est factorisé (`delete_algorithmic_events`), partagé avec
  le banc : une seule définition, les décisions humaines survivent partout.
  Exercé en réel : 337 757 retirées, 16 544 insérées, zéro rejet, un commit
- ✅ Le banc étiquette ses résultats (`--etiquette`) : un balayage sur le
  sous-corpus n'écrase pas les mesures du corpus complet
- 🟢 Le banc rejoue une liste de finalistes (`--jeux`), désignés par leur
  étiquette copiée du CSV — retaper des paramètres, c'est se tromper. Doublons
  refusés : dix minutes par jeu sur le corpus complet, une ligne en double
  n'est jamais une intention. Non exercé : attend le dépouillement
- ✅ `cluster-detections.py` reçoit la bascule `--calibration` et affiche sa
  cible avant d'agir — c'était le dernier outil de regroupement resté sur
  `DATABASE_URL` sans le dire
- 🟡 Calibration fine sur plusieurs saisons — le sous-corpus est en service
  sur la base de calibration ; taille du balayage tranchée, voir §2

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
- ⬜ `GET /api/v1/events` avec bbox obligatoire au-delà du seuil national
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
- ✅ Pages `/carte`, `/territoires/[slug]`, `/communes/[insee]`, `/statut` —
  passées au pluriel le 6 août (cahier v2.1 §7.1), redirections 308 posées
- ✅ Couche d'accès partagée : une page rendue serveur n'appelle pas sa propre
  API par HTTP

### Reste ⬜

- ✅ Affichage des événements sur la carte, cliquables vers leur fiche
- ✅ Liste textuelle rendue serveur, fonctionnelle sans JavaScript (§8.6)
- ✅ Légende avec pastille **et** libellé, expliquant que la taille d'un marqueur
  suit le nombre d'observations et non la gravité (FR-049)
- ✅ `GET /api/v1/events`, emprise obligatoire, rechargement au déplacement (FR-007)
- ✅ **Génération et publication PMTiles** (8 août) — trois couches issues de
  la base (`regions` z4-6, `departements` z4-11, `communes` z10-11, statut
  d'ouverture dans les attributs), découpées par PostGIS (`ST_AsMVT`, une
  requête par zoom×bande×couche), assemblées par `geo_worker.tiles` +
  `pipelines/admin_tiles` (12 tests), publiées dans le compartiment public
  `tiles` (migration `20260807220000`) sous nom à empreinte + alias JSON
  mutable — bascule atomique, archive avant alias. 4 569 tuiles, 41,6 Mo,
  189 s de génération ; lecture par requêtes de plage vérifiée (206), cache
  long vérifié en métadonnée (Storage n'accepte que la forme stricte
  `max-age=N`). Les communes s'arrêtent au zoom 11 : plafond d'envoi de 50 Mo
  du plan Supabase gratuit — le sur-zoom MapLibre couvre au-delà, et le
  retour au z12 est une ligne documentée sur le `PLAN`. Aucun GeoJSON
  national ne sera servi en direct : le front n'a plus d'excuse
- 🟢 **Agrégation par département à l'échelle nationale** (8 août) —
  `api.department_event_aggregates` compte depuis la **même vue** que la
  carte (cohérence par construction), rattachement spatial aux territoires
  avec repli sur le préfixe INSEE ; route `GET /api/v1/events/departments`
  (fenêtre 7 jours par défaut) **exercée : 200 en ~200 ms, 69 départements**.
  Côté carte : protocole `pmtiles://`, polygones départementaux depuis
  l'archive publiée (alias → nom à empreinte), comptes posés en
  `feature-state`, lavis thermique translucide jusqu'au zoom 9, contour
  jusqu'au 12, clic vers `/territoires/[slug]` pour les seuls territoires
  ouverts (FR-015). ✅ le 8 août : couche **regardée et vérifiée** sur le
  serveur de dev — lavis nationaux au dézoom, clic 06/83 vers leurs pages
- ⚠️ L'agrégat a révélé une formulation publique fausse : l'accueil
  affirmait « les détections ne sont importées que sur ces départements »
  alors que **l'ingestion FIRMS est nationale depuis le 5 août** — 69
  départements portaient des événements. Corrigé sur l'accueil et sur la
  branche « non ouvert » de la page commune (écrite la veille sur la même
  hypothèse erronée) : « ouvert » parle d'éditorial — page dédiée, liens
  vérifiés — jamais de couverture des données. **Formulations à faire
  valider métier.** Troisième cas du piège « phrase d'attente »
- ✅ **Géométries des régions et départements** — import du 7 août
  (`scripts/import-territories.py`, 71 s) : 94 départements et 12 régions
  créés en `draft`, 06/83 et PACA complétés sans toucher à leur statut ni à
  leur slug. Les contours sont **construits en base par union des communes**
  (simplification ~100 m), jamais téléchargés : une seule source de vérité
  géométrique. Hiérarchie complète (0 orphelin), la vue publique n'expose
  toujours que les 4 territoires ouverts — vérifié sous le rôle `anon`.
  Ouvrir un territoire = passer son statut à `pilot`/`active`, rien d'autre
- ✅ **Le référentiel communal est national** — import des 94 départements
  restants le 7 août au soir : 34 430 communes créées, zéro rejet sur
  l'ensemble, un `import_run` et une transaction par département. En base :
  **34 746 communes actives sur 96 départements** (France métropolitaine et
  Corse), contrôle Bordeaux 33063 concluant. La recherche et la résolution
  de position couvrent désormais tout le territoire de la vague A ;
  l'ingestion FIRMS, elle, reste sur l'emprise pilote — c'est le sélecteur
  de territoires, pas le référentiel, qui dit ce qui est ouvert
- 🟢 Bouton « Autour de moi » posé sur l'accueil (`components/near-me.tsx`) :
  permission au clic seulement, position arrondie à ~100 m avant d'être
  envoyée en corps de requête, aucune coordonnée en état ni en journal, refus
  annoncé sans dégrader la recherche (FR-020 à FR-024, §22.2). Portes
  passées ; à exercer sur un navigateur réel avant ✅
- ✅ La page commune conditionne sa formulation à la donnée : « détections
  importées » sur un territoire ouvert, « département pas encore ouvert »
  ailleurs. L'import national allait rendre l'ancienne phrase fausse sur
  ~34 000 pages ; la bascule est portée par la présence du territoire, pas
  par le calendrier — le motif anti-« phrase d'attente » appliqué avant la
  faute, pour une fois
- ⬜ Sélecteur de territoire groupé par région (FR-012)
- ⬜ Indicateurs de fraîcheur par couche
- ⚠️ `source_version` enregistre le fournisseur et la date d'import, pas un
  millésime COG officiel — assumé en ADR-017.

**Critère de sortie** : chargement initial sous 2,5 s en 4G sur mobile de
milieu de gamme ; la carte reste utilisable si FIRMS est indisponible.

---

## 7. J7 — Expérience FeuScope complète ⬜

Premier des quatre jalons réintégrés par la décision D-0 (phase 4 du cahier
v2.1, gate G4 Alpha) : ce qui transforme une fiche en expérience FeuScope.

- ⬜ Catalogue national `/evenements` : carte et liste synchronisées, filtres
  territoire, période, niveau de vérification, source, capteur, périmètre
  disponible et information officielle, tris explicites (FR-050 à FR-052,
  FR-055)
- ⬜ Archives `/archives` avec pagination par curseur (FR-053)
- ⬜ Vue textuelle complète du catalogue, utilisable sans interaction
  cartographique (FR-054)
- ⬜ Slug éditorial facultatif `/evenements/[publicId]/[slug?]` (FR-042, FR-060)
- ⬜ Relecture temporelle : curseur entre première observation et dernier état,
  lecture automatique, parcours clavier et alternative textuelle, données
  absentes signalées et jamais interpolées sans mention (FR-080 à FR-084,
  FR-087)
- ⬜ URL d'instant `?at=` : le même instant logique s'ouvre sur un autre
  appareil (FR-085)
- ⬜ États générés à la demande d'abord ; une table de frames pré-calculées
  n'est créée que si la performance l'exige (FR-086)
- ⬜ Carte sociale Open Graph générée à partir du snapshot, avec avertissement
  et horodatage (FR-067)
- ⬜ Version imprimable : les faits sourcés, sans navigation inutile (FR-068)
- ⬜ Bouton « Autour de moi » et page dédiée — l'endpoint de résolution existe
  depuis J3
- ⚠️ Le préfixe d'identifiant public
  ([décision §8.4](strategie.md#84-préfixe-didentifiant-public)) doit être figé
  **avant** ce jalon : le catalogue multiplie les URL publiques durables.

**Critère de sortie** (G4) : page événement, chronologie et relecture
fonctionnelles sur plusieurs cas du corpus historique ; une URL `?at=` ouvre le
même instant logique sur un autre appareil.

---

## 8. J8 — Météo et panache ⬜

Phase 5 du cahier v2.1, gate G5. La réserve de la stratégie v1.0 — un vent à
10 m est physiquement fragile en relief — devient une contrainte d'affichage
et d'exploitation, pas un retrait de périmètre
([stratégie §4](strategie.md#4-périmètre-du-mvp)).

- ✅ Archivage froid AROME (PR-1) en service depuis le 5 août — voir le
  chantier transverse. Le corpus de calibration du panache s'accumule déjà.
- ⬜ Tables `meteo.model_runs`, `wind_samples`, `smoke_forecasts`,
  `smoke_steps`, `affected_municipalities` (cahier §13.12 à §13.16)
- ⬜ Ingestion des runs AROME pour le calcul, au-delà de l'archivage : index
  des paramètres et échéances, extraction autour des événements, interpolation
  validée, garde-fous sur valeurs aberrantes (§16.4)
- ⬜ Panache indicatif §18 : advection pas à pas, élargissement latéral,
  garde-fous — distance et surface maximales, `ST_IsValid` obligatoire,
  résultat vide si entrées insuffisantes, jamais de panache sur modèle expiré
- ⬜ Incertitude affichée et croissante ; modèle, run, échéance, résolution et
  période de validité visibles (FR-101 à FR-103)
- ⬜ Versionnement complet : algorithme, commit du worker, run météo,
  paramètres, checksum des entrées (§18.6)
- ⬜ Désactivation globale ou par territoire, immédiate, sans déploiement
  (FR-106, FR-155)
- ⬜ Communes potentiellement concernées : intersection géospatiale, libellé
  « potentiellement concernée » obligatoire, fenêtre temporelle seulement si
  calculable (FR-110 à FR-114)
- ⬜ Formulation publique obligatoire du panache (§22.5), validée métier avant
  toute mise en ligne
- ⬜ Calibration sur cas connus du corpus — Gironde 2022 — avant publication

**Critère de sortie** (G5) : panache reproductible — mêmes entrées, même
sortie — et désactivable en une action ; communes concernées reproductibles
pour une même version d'entrée.

---

## 9. J9 — CAMS, radar et périmètres ⬜

Phase 6 du cahier v2.1, gate G6. Les schémas `air` et `radar`, vides depuis
l'origine, se remplissent ici.

- ⬜ CAMS : connecteur, import par run, PM2,5 et PM10, COG ou tuiles raster,
  publication atomique avec conservation de la version précédente (§16.5,
  FR-120 à FR-121)
- ⬜ Radar : connecteur, frames, conversion contrôlée, timeline, animation de
  12 à 24 frames avec lecture/pause et respect de la réduction des animations,
  expiration automatique (§16.6, §19.3, FR-123 à FR-124)
- ⬜ Panne de CAMS ou du radar sans effet sur la carte des détections — déjà
  la règle pour les sources en service, à vérifier sur les nouvelles (FR-125)
- ⬜ `fire.event_perimeters` : périmètres versionnés multi-sources — officiel,
  institutionnel, EFFIS, estimé, éditorial, historique —, import
  GeoJSON/KML/Shape, validation géométrique, surfaces recalculées avec méthode,
  masquage sans destruction (§13.23, FR-090 à FR-096)
- ⬜ Styles par provenance : un périmètre satellitaire ou estimé n'est jamais
  présenté comme un contour opérationnel (FR-093)
- ⬜ Versions successives affichables dans la relecture (FR-094)

**Critère de sortie** (G6) : couper CAMS puis le radar ne touche ni la carte ni
les fiches ; un périmètre importé porte source, nature, dates, méthode et
confiance, et son remplacement conserve la version précédente.

---

## 10. J10 — Sources statiques et réconciliation ⬜

Phase 7 du cahier v2.1. Le corpus a déjà fourni la matière : 165 629
détections `type = 2` sur quatorze ans.

- ✅ **Registre spatial dérivé du corpus** (8 août) — règles versionnées
  `sources-statiques-v1` dans `geo_worker.static_sources` (G1 grille ~400 m +
  8-connexité, G2 récurrence ≥ 20 détections sur ≥ 6 mois, G3 rayon couvrant
  borné, G4 clé déterministe pour rejeu, G5 catégorie `other` — la récurrence
  se calcule, la nature du site se nomme éditorialement), 9 tests. Sur le
  corpus réel : **45 sources couvrant 165 576 des 165 629 détections type 2**
  (100 %), 468 cellules occupées en quatorze ans, toutes les zones sous 8 km
  de diagonale — les deux géantes (70 797 et 56 053 détections) sont les
  grands complexes industriels. Empreinte `d6da5446072dd50a`, compte rendu
  versionné. Migration `20260808120000` : `source_key` unique, les entrées
  éditoriales (clé nulle) restent intouchables par les rejeux, et un rejeu ne
  réactive jamais une source désactivée par un administrateur
- ✅ Application par proximité : `mark_known_thermal_sources` existait
  (géographie, rayon par source) ; le chaînon manquant est posé — **le
  regroupement ignore désormais les détections classées**
  (`_pending_detections`), inerte tant que le registre est vide, donc
  déployable sans à-coup. FR-036 tenu : classées, jamais supprimées ; leur
  affichage brut (FR-034) viendra avec la couche z13+
- 🟡 Mesure du changement d'empreinte : séquencée juste après la validation
  des finalistes qui occupe la base de calibration — chargement du registre
  (`build-known-sources.py --cible calibration`), reclassement rétroactif,
  regroupement de référence, **test d'acceptation : l'événement de Fos
  (622 détections, 22 jours) doit disparaître en tant qu'événement**
- ⬜ Réconciliation trimestrielle NRT/standard : import de l'archive,
  rapprochement par clés spatiotemporelles, corrections enregistrées comme
  enrichissements, jamais comme réécritures (§16.3, FR-032)
- ⚠️ N21 sans corpus retraité (dette du §15) : la réconciliation résorbera
  progressivement les 8,9 % de lignes non étiquetées.

**Critère de sortie** : la carte publique ne montre plus la moitié
non-végétation du signal sans le dire ; rejouer la réconciliation sur un
trimestre déjà traité ne change rien.

---

## 11. J4 — Informations officielles ⬜

Le jalon différenciant. Capter automatiquement ce que publient les autorités,
sans jamais le réécrire.

- ✅ Modèle `app.official_messages` : organisme, URL source, date de publication,
  période de validité, territoire, événement lié, validateur
- ✅ **Vigilance Météo-France, en service** — format V6, 9 phénomènes,
  96 départements et 25 pourtours littoraux. Import horaire planifié, bulletin
  brut archivé dans `raw`. Éprouvé en production : 1216 niveaux, 38 au-dessus du
  vert, zéro rejet
  - Voie **temps réel**, avec clé. Le dépôt objet de data.gouv.fr avait été
    retenu pour éviter d'ouvrir un compte, et la mesure a montré ce que ce
    raccourci coûtait : le jeu s'appelle `vigilance-meteorologique-archivee`, et
    le nom disait vrai. Sondé le 6 août à 9 h UTC, il s'arrêtait au bulletin du
    5 août 4 h — vingt-neuf heures de retard, contre un seuil de péremption à
    vingt. La vigilance affichait « Trop ancienne » en permanence : un signal
    exact et faux, qui apprend à ignorer l'indicateur
  - L'adaptateur du §9.2 a rendu le basculement local : seule la récupération
    change, `parse_carte` lit la réponse de l'API sans modification, les deux
    voies servant le même produit « carte ». L'archive reste en repli, mais
    **annoncée** — la voie employée est consignée dans `import_run.metrics.acces`
  - Une clé par application au portail Météo-France : la variable porte donc
    l'application, `METEOFRANCE_VIGILANCE_API_KEY`. Poser celle du radar à sa
    place produirait un 403 sans motif visible
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

## 12. J5 — Administration et exploitation ⬜

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

## 13. J6 — Durcissement, recette, pilote et ouverture ⬜

Phases 9 à 11 du cahier v2.1, gates G8 à G10.

- ⬜ **PWA** : installable, cache du shell et du dernier snapshot consulté,
  jamais présenté comme frais — heure et mode hors ligne visibles (FR-160 à
  FR-162)
- ⬜ Architecture i18n en place, français seul activé (FR-166)
- ⬜ Tests E2E Playwright sur les parcours publics et administrateur
- ⬜ Tests de contrat fournisseur avec réponses figées
- ⬜ Tests géospatiaux : enclave, Corse, frontière maritime, point sur limite,
  proximité de Monaco (§24.3)
- ⬜ Test de charge : pic de crise, 200 000 visites/jour sur un département
- ⬜ **CSP avec nonces**, revue RLS, revue des fonctions `security definer`
- ⬜ Revue de sécurité indépendante
- ⬜ Audit RGAA niveau AA et déclaration d'accessibilité
- ⬜ Pages légales, méthodologie, limites, confidentialité
- ⬜ Test de sauvegarde et de restauration
- ⬜ Checklist de mise en production (annexe G)
- ⬜ **Pilote 06/83** (G9) : recette métier sur situations historiques du
  corpus, dont Gironde 2022 (§24.8)
- ⬜ **Bêta nationale puis ouverture** (G10) : hors pic saisonnier, hypercare,
  runbooks, astreinte et page statut prêts

---

## 14. Chantiers transverses

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
- ✅ **`/statut`, `/communes/[insee]`, `/territoires/[slug]`** — la refonte
  couvre désormais toutes les pages
- ⚠️ Le libellé du titre d'accueil n'a pas été touché : une formulation
  publique passe par une validation métier, pas par une passe de style
- ✅ **Le rendu a été regardé**, le 6 août, sur le déploiement
  <https://mapfeux.vercel.app/>. La refonte cesse d'être vérifiée par la seule
  construction — c'est-à-dire par les portes qui avaient laissé passer les 86
  classes invalides
- ✅ Contrôle complémentaire sur la feuille de style **servie en production** :
  zéro déclaration de la forme `propriété: --jeton`. Le défaut n'a pas
  reparu au déploiement, et ce contrôle-là est rejouable sur l'URL publique,
  contrairement à un coup d'œil

#### Une affirmation devenue fausse, trouvée en refondant

`/commune/[insee]` annonçait que « les détections thermiques satellitaires ne
sont pas encore importées ». C'était vrai jusqu'au 5 août ; l'ingestion tourne
depuis, et la phrase était devenue une affirmation fausse sur une page publique.

La page dit maintenant ce qu'elle sait — les détections sont importées et
regroupées, leur affichage par commune reste à écrire — et renvoie vers la carte
et vers `/statut`. Elle rappelle aussi que l'absence d'événement affiché ne
signifie pas qu'il ne s'en produit pas.

⚠️ La leçon dépasse cette page : **une phrase d'attente devient un mensonge le
jour où l'attente cesse.** Il en reste probablement d'autres, écrites quand une
brique manquait, à relire à chaque mise en service.

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
- ✅ **En service.** Dépôt vérifié dans le compartiment `cold`, jamais purgé :
  54,1 Mo téléchargés, 10,42 Mo archivés, `import_run` en `success`, et AROME
  passée d'« Indisponible » à « À jour » sur `/statut`
- ✅ Planifié quotidiennement à 10 h UTC (`arome-archive.yml`)
- ✅ **La date de donnée est celle du run, non celle de l'échéance.** Le script
  écrivait l'échéance de la prévision — un horodatage à venir. La fraîcheur se
  calculant en `now() - source_data_at`, la valeur devenait négative : `/statut`
  affichait « il y a moins d'une minute » pour une heure future, et la détection
  de panne était neutralisée. Migration `20260806110000` pour les passes déjà
  enregistrées : elles sont effacées plutôt que rectifiées, l'heure du run n'y
  ayant jamais été écrite
- ⚠️ **ADR-025 est à corriger sur les deux chiffres.** L'ADR annonce un coût
  « quasi gratuit » ; la mesure du 2 août sur le paquet brut donnait 56 Mo par
  tranche de six heures, soit vingt gigaoctets par an. L'extrait réel pèse
  **10,4 à 12 Mo par jour, environ 4 Go par an** — ni l'un ni l'autre. C'est le
  rapport de cinq entre paquet et extrait qui rend l'archivage quotidien tenable

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
- ✅ **`SUPABASE_SECRET_KEY` régénérée** le 6 août. La cause était corrigée la
  veille, mais une clé imprimée en clair reste compromise tant qu'elle vit :
  corriger la fuite ne révoque pas ce qui a fui

---

## 15. Dettes et points de vigilance

| Sujet | Nature | Échéance |
|---|---|---|
| Décisions ouvertes restantes | Validation humaine des informations officielles (§8.3), préfixe d'identifiant public (§8.4) et réponse à la première erreur publique (§8.5). Ordonnancement (§8.1) et calendrier (§8.2, tranché par D-0) ne sont plus ouverts | Préfixe avant J7 ; validation avant J4 |
| Mesures faussées par le cache Vercel | `Cache-Control: no-cache` ne traverse pas le cache de bordure : on conclut sur un rendu vieux de plusieurs jours en croyant lire l'état courant. Lire `x-vercel-cache` et `age`, ou interroger la base. `/statut` répondait `STALE` le 6 août | Continu |
| Affichage des détections par commune | `/communes/[insee]` renvoie vers la carte faute de le porter. Le rattachement existe en base, la requête et le bloc restent à écrire | J3 |
| Phrases d'attente à relire à chaque mise en service | Une phrase écrite quand une brique manquait devient fausse le jour où elle arrive. Celle de `/commune` a survécu un jour à l'ingestion | Continu |
| Aucune purge de rétention | `raw` est annoncé à trente jours au registre, rien ne l'applique. Le job devra exclure `cold` **explicitement**, et non par omission (§29) | J5 |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | J1 |
| Pas de CSP | En-têtes partiels seulement | J6 |
| Aucun test de composant | Recherche et carte n'ont que le typage | J6 (Playwright) |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des jalons |
| Schémas `air` et `radar` vides | Tables créées en J9 ; le panache arrive en J8 — la décision D-0 a réintégré ces blocs au périmètre d'ouverture. `meteo` porte déjà la vigilance | J9 |
| `app.official_messages` inutilisable par une ingestion | La table exige un `created_by` humain et un `validated_by` : la vigilance a donc ses propres tables. La [décision §8.3](strategie.md#83-validation-humaine-des-informations-officielles) reste ouverte pour les sources en texte libre | J4 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| Schémas `air` et `radar` déclarés au registre | CAMS et radar affichés « à venir » plutôt qu'« indisponibles » : le connecteur n'existe pas, ce n'est pas une panne. Le compteur public ne porte que sur les sources en service. ⚠️ Phrase d'attente à retirer le jour de la mise en service (J9) | J9 |
| Regroupement encore lent | Le coût quadratique des agrégats est levé, mais il reste une requête de candidats par détection. À surveiller avant la montée en charge (§6.3) | J6 |
| Coût d'un jeu de calibration | Borné par le sous-corpus (16 544 détections) : le classement des 112 jeux se fait dessus, le corpus complet ne sert plus qu'à rejouer les finalistes, une nuit au plus. Mesure du 6 août au §2 | Traité |
| `cluster-detections.py` vise encore la production | Traité le 6 août : bascule `--calibration` posée, cible affichée avant d'agir. L'usage production reste légitime — reprise manuelle aux paramètres de référence | Traité |
| N21 sans corpus retraité | 30 180 lignes — 8,9 % du corpus — de janvier 2024 à août 2026, servies en NRT faute d'archive publiée par FIRMS. Ni retraitement scientifique, ni `type` : les deux saisons les plus récentes sont partiellement non étiquetées | J2 |
| La borne de R4 suppose le corpus standard dense | Un satellite indisponible en milieu de période retraitée verrait ses lignes NRT de la panne écartées à tort. FIRMS ne publie pas de calendrier de couverture. La borne employée est consignée dans le compte rendu du corpus | J2 |
| Corpus dérivé versionné | Le Parquet pèse 6,8 Mo et se régénère depuis les zips. Chaque régénération dépose un nouveau blob dans l'historique. À arbitrer : le compte rendu JSON suffit à prouver la provenance | J6 |
| `api.fire_events` expose l'`id` interne | §15.1 demande des identifiants publics opaques. Non exploité par nos réponses, mais lisible via PostgREST | J6 |
| Coût d'un pic non chiffré | Conditionne un point d'arrêt — dernier préalable de phase 0 encore ouvert | Phase 0 |
| Réponse à la première erreur publique | Runbook éditorial absent | Avant J6 |
| MFA super_admin non appliquée | La contrainte en base exige `mfa_required` pour `super_admin`, mais l'enrôlement TOTP n'existe pas (§14.4). D'ici J5, ne pas employer de compte super_admin au quotidien — `grant-admin.py` l'affiche | J5 |
| `fires_in_bbox` sous son nom historique | L'API publique dit désormais `events` (cahier v2.1 §15.2) ; la fonction SQL interne garde son nom — la renommer passe par une migration, sans bénéfice public | Libre |
| Migrations appliquées hors bande | Le chargement direct par script (calibration puis production) casse le `db push` suivant si la migration n'est pas rejouable — vécu le 8 août : 42701 sur `source_key`. Règle : toute migration appliquée hors CLI s'écrit idempotente (`if not exists`, `on conflict`, `create or replace`) | Continu |
| Le banc ne reprend pas où il s'est arrêté | Traité le 8 août : le troisième accident (mise en veille) l'a réclamé, comme prévu. `--reprendre` saute les jeux déjà sur disque et complète le CSV | Traité |

---

## 16. Tenue de ce fichier

À la fin de chaque session :

1. Mettre à jour la date en tête.
2. Faire passer les éléments terminés à 🟢, et à ✅ **seulement** après exécution.
3. Rafraîchir le tableau des portes de qualité si elles ont tourné.
4. Réécrire la section « Prochaine action » — elle ne doit contenir qu'une chose.
5. Ajouter toute dette nouvelle au tableau du §15 plutôt que de la laisser
   implicite dans le code.
6. Consigner dans [docs/adr/](adr/) tout écart au cahier, et l'ajouter à la liste
   du registre.

Le positionnement, le périmètre et les conditions d'arrêt ne se modifient pas
ici mais dans [strategie.md](strategie.md).

Une décision qui touche le périmètre, la séparation public/opérationnel, les
sources de données ou l'exposition des schémas Supabase passe par un ADR
**avant** implémentation, pas après.
