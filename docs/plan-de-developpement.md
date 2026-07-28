# Plan de développement MapFeux

**Dernière mise à jour** : 28 juillet 2026

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

**Le produit fonctionne de bout en bout sur données réelles.** 931 détections
importées sur 90 jours d'historique du 06 et du 83, regroupées en 122
événements. Les fiches affichent de vrais feux, avec leurs communes, leurs
capteurs, leur chronologie et leur puissance radiative.

**Le critère de sortie de J2 est atteint.** Un recalcul complet du regroupement
redonne exactement la même empreinte : 122 événements, signature identique. Le
résultat est explicable parce qu'il est reproductible.

Le plus gros événement — 570 détections, 66 km², six jours près de Pontevès —
présente un profil temporel sans trou et des FRP jusqu'à 2197 MW : c'est un vrai
grand feu, pas un chaînage de l'algorithme.

### Portes de qualité — dernier passage

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 44 tests |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 17 fichiers |
| Worker | `mypy src` | ✅ strict, 12 fichiers |
| Worker | `pytest` | ✅ 83 tests |

---

## 2. Prochaine action

**Trancher la politique d'affichage de la longue traîne.** Sept événements
portent 77 % des observations, cent trois en portent 16 %. La carte les montre
sur le même plan : un visiteur y voit un semis dont plus de huit points sur dix
ne correspondent probablement à rien.

Ce n'est pas un réglage d'algorithme mais une décision de produit, et elle
précède l'ouverture : une carte illisible dessert autant qu'une carte fausse.
Le cahier interdit de masquer une observation, donc la réponse est une vue par
défaut hiérarchisée, avec une commande explicite pour tout afficher.

Deux autres chantiers sont mûrs : le regroupement reste lent — le coût est
dominé par les allers-retours réseau, pas par le calcul, ce qui appelle à
pousser la boucle côté serveur — et l'ingestion n'est ni planifiée ni branchée
sur le rafraîchissement des snapshots.

En parallèle, de votre côté :

- ouvrir les préalables de la [phase 0](strategie.md#3-phase-0--préalables-non-techniques),
  en particulier l'autorisation de cumul — c'est un point d'arrêt du projet ;
- trancher les [décisions ouvertes](strategie.md#8-décisions-ouvertes), dont
  l'ordonnancement et le préfixe d'identifiant public ;
- `pnpm db:push` pour les deux migrations en attente
  (`20260727130000_api_municipalities.sql`,
  `20260728100000_source_status_freshness.sql`) ;
- `pnpm db:types` pour générer les types du schéma `api`.

---

## 3. Jalons

Hypothèse de charge : développement principalement solo, à temps partiel, en
parallèle d'un service de sapeur-pompier professionnel. Les durées sont en
**semaines calendaires**, pas en jours-homme.

| Jalon | Contenu | Estimé | Reste | État |
|---|---|---:|---:|---|
| J1 | Fondations et fiche événement sur données figées | 8 sem. | **1 sem.** | 🟡 critère de sortie atteint |
| J2 | Ingestion FIRMS et regroupement réel | 6 sem. | **4 sem.** | 🟡 ingestion en service |
| J3 | Carte et territoires | 6 sem. | **2 sem.** | 🟡 pilote livré |
| J4 | Informations officielles automatisées | 6 sem. | 6 sem. | ⬜ |
| J5 | Administration, supervision, mode dégradé | 5 sem. | 5 sem. | ⬜ |
| J6 | Recette, charge, sécurité, ouverture | 5 sem. | 5 sem. | ⬜ |
| | | 36 sem. | **23 sem.** | |

Les fondations, la fiche événement, la couche territoriale du pilote et
l'ingestion FIRMS étant livrées, il reste **environ 23 semaines** au lieu de 36.

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

## 5. J2 — Ingestion FIRMS et regroupement ⬜

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

### Reste ⬜

- ⬜ Planification toutes les dix minutes
- ⬜ Déplacer les fichiers bruts vers Storage — ils sont aujourd'hui sur le
  disque local, sans rétention
- ✅ Algorithme de rattachement déterministe, paramètres versionnés (§17.2) —
  26 tests sur les fonctions pures
- ✅ Reproductibilité vérifiée sur 90 jours réels : recalcul complet, empreinte
  identique
- ✅ Score de fiabilité interne et seuils publics versionnés (§17.3)
- ✅ Génération idempotente des entrées de chronologie (FR-058)
- ✅ Import d'historique par tranches, corpus de calibration constitué
- ✅ Banc de calibration : huit jeux de paramètres rejoués sur le corpus complet
- ⬜ Calibration fine sur plusieurs saisons — une seule est chargée

#### Ce que le balayage a montré

| jeu | évts | 1 det | ≥2 capt | + gros | diag. km |
|---|---:|---:|---:|---:|---:|
| référence (2500 m, 500 m/h, 24 h, 0,35) | 122 | 53 % | 7 % | 570 | 15,1 |
| rayon 1500 m | 145 | 50 % | 12 % | 171 | 7,6 |
| rayon 4000 m | 114 | 56 % | 4 % | 691 | 15,8 |
| croissance 250 m/h | 123 | 53 % | 7 % | 570 | 15,1 |
| croissance 1000 m/h | 122 | 53 % | 7 % | 338 | 15,1 |
| fenêtre 12 h | 154 | 50 % | 10 % | 300 | 11,6 |
| seuil 0,20 | 116 | 56 % | 5 % | 662 | 15,1 |
| seuil 0,50 | 152 | 51 % | 10 % | 319 | 10,5 |

**La proportion d'événements à une seule détection ne bouge pas** : entre 50 %
et 56 % quel que soit le réglage. Aucun paramètre ne la déplace, parce qu'elle
tient à la donnée et non à l'algorithme — la moitié des détections sont vues
une fois, par un seul capteur, et jamais revues.

**La croissance du rayon est quasi inerte.** De 250 à 1000 m/h, le nombre
d'événements ne varie pas. Le paramètre peut être figé et retiré de la surface
de calibration.

**Le résultat n'est pas monotone dans les paramètres.** Une croissance de
1000 m/h — plus permissive — produit un plus gros événement *plus petit* que
500 m/h. Le rattachement séquentiel glouton ne garantit pas que « plus lâche »
donne « plus fusionné » : l'intuition n'est pas un guide sûr, ce qui est
précisément la raison d'être du banc.

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

La carte affiche aujourd'hui les 122 sur le même plan. Un visiteur y voit un
semis dont plus de huit points sur dix ne correspondent probablement à rien. Ce
n'est pas une question d'algorithme mais de **politique d'affichage** :
- ⬜ Vue par défaut mettant au premier plan les événements étayés, sans masquer
  les autres — le cahier interdit de dissimuler une observation (§17.7)
- ⬜ Commande explicite pour tout afficher, et libellé disant ce qui est filtré
- ⚠️ À trancher avant l'ouverture : une carte illisible dessert autant qu'une
  carte fausse.
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
- ⬜ Connecteurs par type de source : flux RSS préfectoraux, pages de
  communiqués, vigilance Météo-France, arrêtés d'accès aux massifs
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

## 10. Dettes et points de vigilance

| Sujet | Nature | Échéance |
|---|---|---|
| Préalables de phase 0 non engagés | Autorisation de cumul, cadre juridique — point d'arrêt | Immédiat |
| Décisions ouvertes non tranchées | Ordonnancement, calendrier, validation, préfixe | Avant J2 |
| CI jamais observée en vert | Premier déclenchement au commit initial | Immédiat |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | J1 |
| Pas de CSP | En-têtes partiels seulement | J6 |
| Aucun test de composant | Recherche et carte n'ont que le typage | J6 (Playwright) |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des jalons |
| Schémas `meteo`, `air`, `radar` vides | Tables reportées en v2 avec le panache | v2 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| Fichiers bruts FIRMS sur disque local | Ni Storage, ni rétention : ils s'accumulent | J2 |
| Regroupement encore lent | Le coût quadratique des agrégats est levé, mais il reste une requête de candidats par détection. À surveiller avant la montée en charge (§6.3) | J6 |
| Calibration limitée à une saison | L'API FIRMS NRT ne sert qu'une fenêtre glissante d'environ quatre mois. Juillet 2025 renvoie zéro ligne. Les saisons antérieures exigent une demande à l'archive FIRMS | Avant le jalon C |
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
