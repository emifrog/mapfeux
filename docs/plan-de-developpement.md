# Plan de développement MapFeux

**Dernière mise à jour** : 10 août 2026 — J8 entamé : les cinq tables météo
(§13.12-16) en production, le registre des runs vivant (6 runs, amorçage
compris) ; la fuite de l'archivage AROME colmatée — les 404 des 8-9 août
compris et les **trois jours perdus récupérés**. Plus tôt le même jour :
masque des sources statiques appliqué en production (Fos éteint),
`DEMO-2607A1` retiré, FR-067/FR-068 livrés, préfixe `MPF-` figé (ADR-021).

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
fonde le masque des sources statiques. **Le masque est appliqué en production
depuis le 10 août** : les récurrences industrielles sont classées dès
l'ingestion, les pseudo-événements existants ne sont plus alimentés et
s'archiveront en sept jours (voir J10).

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

### Portes de qualité — dernier passage (10 août)

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 58 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 68 fichiers (worker 48, scripts 20) |
| Worker | `mypy src` + `mypy scripts` | ✅ strict, 29 + 20 fichiers |
| Worker | `pytest` | ✅ 305 tests |
| Migrations | 23 migrations sur base vierge, en CI | ✅ |

⚠️ Aucune de ces portes ne voit la couleur ni la taille effectives d'un
élément. Les 86 classes CSS invalides du §14 les ont toutes passées.

---

## 2. Prochaine action

**J8, suite : l'extraction du vent autour des événements (`wind_samples`).**

La première marche de J8 est posée : les cinq tables (§13.12-16) sont en
production et le registre des runs est vivant — voir J8. La marche suivante
est l'extraction : lire les extraits NetCDF du stockage froid, interpoler
U/V au point représentatif d'un événement (bilinéaire ou plus proche voisin,
selon validation — §16.4), normaliser les directions, garde-fous sur valeurs
aberrantes, et consigner méthode et distance à la cellule dans
`meteo.wind_samples`. C'est le dernier préalable du calcul de panache (§18).

La spécification de J8 est lue dans le cahier **v1.1**, dont les §13.12-16,
§16.4 et §18 portent les mêmes numéros que le v2.1 cité par ce plan. ⚠️ À
confirmer d'un coup d'œil sur le PDF v2.1 : si ces sections y ont bougé,
l'écart passe par ADR.

Restent aussi à J7, sans bloquer J8 : slug éditorial (FR-042), relecture v2
(FR-082), page « Autour de moi », plafond parlant du tableau des détections.

⚠️ Contrôle sous sept jours (au plus tard le 17 août) : les pseudo-événements
industriels privés d'alimentation par le masque — Fos `MPF-V7NPXN72`,
Dunkerque `MPF-GCWYFMCW` — doivent basculer `archived` d'eux-mêmes par le
cycle de vie. S'ils ne le font pas, c'est `refresh_freshness` qui a un trou,
pas le masque.

Le dossier de la calibration close — balayage croisé, inspections, mesure du
masque — est consigné en J10 ; l'historique du banc et ses trois morts, en J2.

Côté [phase 0](strategie.md#3-phase-0--préalables-non-techniques) :
**l'autorisation de cumul est accordée depuis le 6 août** — le point d'arrêt
correspondant du [§7](strategie.md#7-conditions-darrêt) est levé — et le cadre
juridique de l'édition est posé. L'estimation du coût d'un pic (§3.5) reste le
dernier préalable non traité. Restent aussi, de votre côté, deux
[décisions ouvertes](strategie.md#8-décisions-ouvertes) : la validation
humaine des informations officielles (§8.3) et la réponse à la première
erreur publique (§8.5). Le préfixe d'identifiant public est
[tranché le 10 août](strategie.md#84-préfixe-didentifiant-public--tranché-le-10-août-2026) —
`MPF-`, définitivement ([ADR-021](adr/021-prefixe-didentifiant-public.md)) ;
l'ordonnancement (§8.1) et le calendrier (§8.2, tranché par D-0 : lancement
hors pic saisonnier) ne sont plus ouverts.

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
- ⚠️ **`PUBLIC_APP_URL` dans Vercel : posée, parcours e-mail à rejouer.**
  L'absence de la variable envoyait les liens des e-mails de connexion vers
  `http://localhost:3000`. Constat du 10 août : la fiche de production
  affiche son URL permanente sans localhost — la variable est donc posée et
  déployée. Le parcours e-mail complet (envoi, lien, session) n'a pas été
  rejoué depuis ; ⚠️ maintenu tant qu'un lien reçu n'a pas été suivi avec
  succès en production.
  **Le contrôle ne demande pas de jugement** : `select max(last_sign_in_at)
  from auth.users`. Toute valeur postérieure au 10 août prouve qu'un lien a
  été suivi depuis que la variable est posée, et lève l'avertissement. Relevé
  du 15 août : **7 août 17:32 UTC**, donc aucune connexion depuis — l'anomalie
  n'est pas levée, et cinq jours de silence ne l'ont pas rendue moins vraie
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
- ✅ Calibration fine sur plusieurs saisons — **close le 9 août** :
  `grouping-v1` gelé sur le dossier consigné en J10 (balayage croisé 112 jeux
  sur le sous-corpus, inspections, mesure du masque ; validation corpus
  complet abandonnée en connaissance de cause)

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

- ✅ **Catalogue national `/evenements`** (9 août) — liste SSR nationale triée
  par dernière observation (FR-052, aucun classement par « importance » —
  FR-055), filtres période (fenêtres FR-005), département et niveau de
  vérification, **pagination par jeu de clés** sur
  (`last_detected_at`, `public_id`) — le curseur, opaque mais décodable, ne
  transporte que des valeurs publiques, jamais l'identifiant interne. Fonction
  `api.events_catalog` (migration rejouable), endpoint unique `GET
  /api/v1/events` à deux régimes — avec `bbox` la carte, sans `bbox` le
  catalogue (§15.2). Exercé sur serveur local contre la production : liste
  nationale, filtre Moselle 24 h (23 évts), pagination aller-retour à 50 par
  page, formulaire et curseur fonctionnels **sans JavaScript** (FR-054 tenue
  par construction). Carte de page : les composants de /carte, agrégats
  compris. Filtres source/capteur/périmètre/info officielle : quand les
  objets existeront (J9, J4)
- ✅ **Cycle de vie de la fraîcheur** (9 août, préalable des archives) — il
  n'existait pas : 932 événements sur 933 figés en « nouvel événement »
  depuis leur création, la fiche disant « créé récemment » sur des événements
  de quatre jours. Règles `cycle-de-vie-v1` dans `fire.refresh_freshness`
  (migration `20260809140000`, source unique — la chaîne l'appelle, ne la
  recopie jamais) : new < 24 h, recent < 48 h, not_recent ≥ 48 h, archived ≥
  7 j (terminal), hidden intouchable. Requalification initiale : 786
  événements, 933 snapshots reconstruits, second passage à zéro (idempotent).
  Branchée dans `run-ingestion.py`, snapshots des requalifiés compris
- ✅ **Archives `/archives`** (FR-048, FR-053) — même mécanique que le
  catalogue (`freshness=archived`), filtre département, pagination par
  curseur, sans JavaScript. 124 archives réelles dès l'ouverture — l'été
  varois de l'import historique, Pontevès en tête. « L'archivage est un état
  technique : il ne dit pas qu'un feu est éteint »
- ✅ **Relecture temporelle, v1** (FR-080 à FR-087, §15.5) —
  `/evenements/[publicId]/relecture?at=` reconstruit l'état **à la demande**
  depuis les observations membres et la chronologie (FR-086, aucune table de
  frames) : compteurs, capteurs, FRP max, carte des points colorés par l'âge
  **à l'instant rejoué**, chronologie connue à cet instant. La navigation est
  une liste de liens — passages satellitaires, précédent/suivant — donc
  clavier et sans JavaScript par construction (FR-083), et `?at=` s'ouvre à
  l'identique ailleurs (FR-085). API `GET …/state?at=` avec
  `requestedAt`/`effectiveAt` distincts (FR-084 : rien n'est interpolé).
  Vérifié sur Pontevès : à mi-feu, 312 observations sur 570, `effectiveAt`
  ramené au passage réel. Le plafond de 2 000 observations est **parlant**
  (bandeau « relecture partielle ») — la première passe tronquait à 500 en
  silence. Reste pour la v2 : curseur glissant et lecture automatique
  (FR-082), en amélioration progressive au-dessus des mêmes URL
- ⬜ Slug éditorial facultatif `/evenements/[publicId]/[slug?]` (FR-042, FR-060)
- ⬜ Relecture temporelle : curseur entre première observation et dernier état,
  lecture automatique, parcours clavier et alternative textuelle, données
  absentes signalées et jamais interpolées sans mention (FR-080 à FR-084,
  FR-087)
- ⬜ URL d'instant `?at=` : le même instant logique s'ouvre sur un autre
  appareil (FR-085)
- ⬜ États générés à la demande d'abord ; une table de frames pré-calculées
  n'est créée que si la performance l'exige (FR-086)
- ✅ **Carte sociale Open Graph** (10 août, FR-067) —
  `opengraph-image.tsx` colocalisée sur la fiche, générée depuis le
  **snapshot** (`fetchEventView`, même chemin que la page) : identifiant,
  niveau de vérification, grandeurs mesurées en chasse fixe, pastille à
  l'échelle d'âge thermique, **deux horodatages** (dernière observation, état
  figé) et l'avertissement §22.5 — l'heure de service est volontairement
  absente, une image en cache la transformerait en mensonge. Satori ne lit ni
  woff2 ni variables CSS : jetons recopiés (dette §15), polices WOFF **dans
  `assets/og-fonts/`** avec leurs licences OFL. La première version les
  lisait dans node_modules par chemins composés : parfaite en local — dev
  **et** build de production —, **500 au premier déploiement** (ENOENT au
  journal Vercel : intraçable statiquement, et les globs d'inclusion n'ont
  pas compensé à travers les liens pnpm). Leçon : ce que `readFile` lit doit
  être une ressource du projet à chemin littéral. `twitter:card` ajouté aux
  métadonnées de la fiche. Vérifié de bout en bout : PNG 1200×630 rendu et
  regardé (La Brigue), balises `og:image` complètes, 404 sur identifiant
  inconnu, et **200 en production** après correctif — même image à l'octet
  près qu'en local
- ✅ **Version imprimable** (10 août, FR-068) — feuille de style d'impression
  sur la fiche elle-même, pas de page dupliquée : `print:hidden` masque
  l'en-tête, la navigation, la carte WebGL, le bouton de copie et les liens
  morts ; restent les faits, leurs provenances, les trois horodatages, l'URL
  permanente et l'attribution obligatoire (§9.5). Les jetons clairs sont
  réimposés sous `@media print` — imprimer en thème sombre donnait des aplats
  sombres. Vérifié sur styles calculés dans un navigateur réel, règles
  `print` basculées en `all` : douze masquages effectifs, contenu intact,
  fond blanc
- ⬜ Bouton « Autour de moi » et page dédiée — l'endpoint de résolution existe
  depuis J3
- ✅ Préfixe d'identifiant public **figé : `MPF-`**, le 10 août
  ([ADR-021](adr/021-prefixe-didentifiant-public.md)). La fenêtre « avant la
  première URL durable » s'était refermée avec le catalogue ; la décision
  ratifie l'état servi plutôt que de payer un renommage cosmétique. FR-067
  peut graver les URL dans les partages sociaux.

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
  chantier transverse, y compris la fuite des 8-9 août colmatée le 10. Le
  corpus du panache s'accumule, **continu et sans trou** ; l'archive porte
  bien `u10`/`v10`, le vent dont le §18 a besoin
- ✅ **Les cinq tables météo, en production** (10 août) — migration
  `20260810150000` : `model_runs`, `wind_samples`, `smoke_forecasts`,
  `smoke_steps`, `affected_municipalities` (§13.12-16, lus dans le v1.1 à
  numérotation identique). `st_isvalid` en **contrainte** (§18.5), une seule
  prévision courante par événement (index partiel sur `is_current`),
  `on delete restrict` du run porteur (§18.6 : une prévision sans provenance
  est interdite), RLS partout, grants `mapfeux_ingest` limités au registre
  des runs — un droit sans écrivain est une surface d'attaque sans bénéfice.
  Appliquée **et rejouée** sur la production : l'idempotence est vérifiée,
  pas promise
- ✅ **Le registre des runs est vivant** (§13.12) — `meteo.model_runs` compte
  6 runs continus du 5 au 10 août : `record_model_run` (fusion des échéances
  en union, inventaire des fichiers par chemin, verrou de ligne) est branché
  dans `archive-arome.py`, et `backfill-meteo-runs.py` a reporté les passes
  antérieures depuis `ingest.import_runs` — 8 passes, 6 runs, les doublons
  convergent vers la même ligne. Les échéances par tranche sont **vérifiées
  sur les extraits réels** : `00H06H` porte 7 pas horaires (0-6), `19H24H`
  en porte 6 (19-24) — l'extraction conserve toute la tranche, pas seulement
  la mi-journée visée, ce qui donne déjà 6 à 7 heures de vent par jour au
  panache
- 🟡 Ingestion des runs pour le calcul (§16.4) : index des paramètres et
  échéances ✅ (le registre) ; extraction autour des événements, interpolation
  validée et garde-fous sur valeurs aberrantes ⬜ — c'est la prochaine action
  (§2)
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
- ✅ **Mesure du masque, test d'acceptation réussi** (9 août, sur le
  sous-corpus) — 45 sources chargées, **6 890 détections classées** (41,6 %
  du sous-corpus), regroupement de référence rejoué : **331 événements
  contre 701**, arithmétique exacte (6 890 classées + 9 654 regroupées =
  16 544, zéro fuite). Le pseudo-événement de Fos (622 détections, 22 jours)
  **n'existe plus** : il ne reste autour du site que des résidus de 1 à 3
  détections sur 2 h au plus, la traîne honnête. Landiras intact **au point
  près** (2 069), La Teste séparée (1 000) : le masque n'a mangé aucun feu
  réel. FR-036 tenu : les 6 890 classées restent toutes publiables.
  L'empreinte de référence change par construction — ce dossier est la
  nouvelle base de comparaison
- ✅ **`grouping-v1` gelé.** Dossier : balayage croisé 112 jeux, inspections
  des quatre têtes de liste, mesure du masque. La validation sur corpus
  complet a été **abandonnée en connaissance de cause** : le premier jeu
  comptait 11,2 h de CPU saturé sans terminer — deux tentatives, deux
  interruptions de session, un constat. Le classement était déjà établi par
  deux voies indépendantes ; payer trois fois dix heures n'aurait rien
  départagé. Le chiffre nourrit la dette « regroupement encore lent » (§15)
- ✅ **Masque appliqué en production** (10 août, décision d'exploitation) —
  `build-known-sources.py --cible production` : 45 sources posées (empreinte
  `d6da5446072dd50a`, identique à la calibration — dérivation déterministe,
  le compte rendu versionné n'a pas bougé au rejeu), **776 détections
  classées** rétroactivement, toutes membres d'événements existants, zéro
  orpheline. Vérifié en base : Fos est bien `MPF-V7NPXN72` (166 membres,
  100 % classés, 43.440/4.892) ; l'autre géant `MPF-GCWYFMCW` (299 membres,
  100 % classés) est le complexe industriel de Dunkerque — l'ingestion est
  nationale. Les deux restent servis jusqu'à leur archivage par le cycle de
  vie, sept jours sans observation — contrôle au §2. FR-036 tenu de bout en
  bout : classées, jamais supprimées, toutes publiables
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

- ✅ Authentification par lien magique — livrée en J1 le 7 août, pas ici. La
  ligne est restée ⬜ huit jours après coup : un jalon ne garde pas la propriété
  de ce qu'un autre a livré avant lui
- ⬜ MFA obligatoire pour `super_admin` — seule moitié encore due. La contrainte
  existe en base, l'enrôlement TOTP non (§14.4)
- ✅ `proxy.ts` pour le rafraîchissement de session — livré en J1 le 7 août,
  périmètre `/admin` seulement
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
| Décisions ouvertes restantes | Validation humaine des informations officielles (§8.3) et réponse à la première erreur publique (§8.5). Préfixe (§8.4) tranché le 10 août — `MPF-`, [ADR-021](adr/021-prefixe-didentifiant-public.md) ; ordonnancement (§8.1) et calendrier (§8.2, D-0) tranchés antérieurement | Validation avant J4 ; réponse avant J6 |
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
| Regroupement encore lent | Chiffré le 9 août : **11,2 h de CPU saturé sans terminer un seul regroupement complet des quatorze saisons** (337 757 détections, recherche de candidats en mémoire). Les passes incrémentales de production restent rapides (orphelines seules), mais tout recalcul complet à l'échelle est impraticable — la structure de voisinage se paie par détection × événements. À traiter avant la montée en charge (§6.3) | J6 |
| Coût d'un jeu de calibration | Borné par le sous-corpus (16 544 détections) : 102 à 161 s par jeu (mesure du 6 août, `data/calibration/axes-sous-corpus.csv`). La calibration est close ; le banc reste prêt pour une v2 des règles | Traité |
| `cluster-detections.py` vise encore la production | Traité le 6 août : bascule `--calibration` posée, cible affichée avant d'agir. L'usage production reste légitime — reprise manuelle aux paramètres de référence | Traité |
| N21 sans corpus retraité | 30 180 lignes — 8,9 % du corpus — de janvier 2024 à août 2026, servies en NRT faute d'archive publiée par FIRMS. Ni retraitement scientifique, ni `type` : les deux saisons les plus récentes sont partiellement non étiquetées | J2 |
| La borne de R4 suppose le corpus standard dense | Un satellite indisponible en milieu de période retraitée verrait ses lignes NRT de la panne écartées à tort. FIRMS ne publie pas de calendrier de couverture. La borne employée est consignée dans le compte rendu du corpus | J2 |
| Corpus dérivé versionné | Le Parquet pèse 6,8 Mo et se régénère depuis les zips. Chaque régénération dépose un nouveau blob dans l'historique. À arbitrer : le compte rendu JSON suffit à prouver la provenance | J6 |
| `api.fire_events` expose l'`id` interne | §15.1 demande des identifiants publics opaques. Non exploité par nos réponses, mais lisible via PostgREST | J6 |
| Coût d'un pic non chiffré | Conditionne un point d'arrêt — dernier préalable de phase 0 encore ouvert | Phase 0 |
| Réponse à la première erreur publique | Runbook éditorial absent | Avant J6 |
| MFA super_admin non appliquée | La contrainte en base exige `mfa_required` pour `super_admin`, mais l'enrôlement TOTP n'existe pas (§14.4). D'ici J5, ne pas employer de compte super_admin au quotidien — `grant-admin.py` l'affiche | J5 |
| `fires_in_bbox` sous son nom historique | L'API publique dit désormais `events` (cahier v2.1 §15.2) ; la fonction SQL interne garde son nom — la renommer passe par une migration, sans bénéfice public | Libre |
| Migrations appliquées hors bande | Le chargement direct par script casse le `db push` suivant si la migration n'est pas rejouable — 42701 sur `source_key` le 8 août, puis 42725 sur `events_catalog` le 9 : pendant un rejeu, deux surcharges coexistent et un `comment on function` au nom nu devient ambigu. Règles : idempotence (`if not exists`, `on conflict`, `create or replace`) **et** toute référence de fonction qualifiée par sa signature complète dès qu'elle évolue | Continu |
| Tableau des détections de la fiche plafonné en silence | `fire_event_detections` rend 500 lignes par défaut (2 000 au plus) ; la relecture annonce désormais son plafond, la fiche pas encore — un événement à 600 détections afficherait un tableau tronqué sans le dire | J7 |
| Événement de démonstration en production | Traité le 10 août : `DEMO-2607A1` et ses 7 détections `demo:%` supprimés selon la recette documentée par la fixture, entrée d'audit posée avant les suppressions (état avant + motif), dans la même transaction. Vérifié : zéro restant en base, `/archives` sans la démo (cache MISS), fiche en 404 | Traité |
| Le banc ne reprend pas où il s'est arrêté | Traité le 8 août : le troisième accident (mise en veille) l'a réclamé, comme prévu. `--reprendre` saute les jeux déjà sur disque et complète le CSV | Traité |
| Jetons du thème recopiés dans la carte OG | Satori (moteur d'`opengraph-image.tsx`) ne lit ni variables CSS ni feuilles de style : les jetons clairs y sont en dur, avec le commentaire qui l'assume. Une retouche de palette doit être répercutée à la main | Libre |
| Pseudo-événements industriels encore servis | Fos et Dunkerque restent visibles au catalogue jusqu'à leur archivage par le cycle de vie (7 jours sans observation). Contrôle au plus tard le 17 août — voir §2 | 17 août |

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
