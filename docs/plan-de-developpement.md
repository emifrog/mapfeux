# Plan de développement MapFeux

**Dernière mise à jour** : 13 septembre 2026, soir — **l'accueil s'ouvre
sur la carte nationale vivante et trois chiffres réels**, la recherche est
sur la carte, la coque au-dessus de `/carte` passe de 172 à 96 px, les
contours et les marqueurs se lisent à l'échelle nationale, une lueur dit
ce qui a moins de vingt-quatre heures, **une carte au survol** dit d'un
marqueur ce que la liste en dit sans cliquer, et le zoom intermédiaire a
ses **grappes** et ses **noms de départements**. Comparaison faite au même
format contre ensemblepourlaforet.fr et GISFire : l'écart était d'abord sur
l'accueil. Le VPS attend sa souscription — le kit est prêt (`ops/vps/`),
la bascule est décrite en §2. Les Canadair sont écartés.

**Le même soir, un peu avant** — **le déclencheur est
passé au planificateur Windows**. Sept tâches aux cadences qu'Actions
déclarait sans les tenir, crons retirés, première passe par le déclencheur
lui-même à 16 h 43 ; S4U refusé sans élévation, donc session ouverte
requise — verrouillée suffit. Reste à remesurer sept jours de cadence.

**Plus tôt le même jour** — **le critère de J4 est
mesuré : non tenu, et non tenable sous le déclencheur Actions.** Sur sept
jours et toutes les sources, seul le cron quotidien tourne comme déclaré ;
tout le sous-quotidien est ramené à une passe toutes les trois à cinq
heures, FIRMS compris. Le contenu du jalon est entier et en service — la
mise en service du 11 a tenu, le connecteur `massifs` corrigé date bien ses
passes de l'instant de lecture depuis. Ce qui manque est la ligne que §8.1
avait prévue remplaçable, et c'est une décision d'exploitation à prendre.
Détail en [§2](#2-prochaine-action) et [stratégie §8.1](strategie.md).

**11 septembre 2026, nuit** — **les deux dernières
sources officielles sont en service**. `prefectures` et `massifs` passent
`active` après contrôle de leurs passes réelles — 169 au total, 163
complètes depuis fin août — et de la donnée servie ; le bandeau passe de
« 3/6 sources en service » à « 5/8 ». La bascule a révélé une **fausse
assurance** : `massifs` datait sa donnée du jour décrit, c'est-à-dire de
demain, et le bandeau annonçait « maj il y a moins d'une minute » en
permanence. Connecteur corrigé et deux garde-fous posés. J4 ne tient plus
qu'à la mesure de son critère des trente minutes.

**Plus tôt dans la soirée** — **`/carte` est
devenue une coque d'application, son fond suit le thème, et sa liste suit
la carte**. La page faisait 3,4 écrans de haut et donnait 47 % du premier
à la carte ; elle fait maintenant un écran, la carte le remplit, le reste
flotte dessus — à gauche ce qui se lit, à droite ce qui se manipule. Le
fond vectoriel est **dérivé en sombre** à partir de la feuille « gris » de
l'IGN, qui n'en
publie aucune : inversion de la clarté, bornée pour qu'un fond noir ne
fasse pas des marqueurs orange des trous de lumière. Deux défauts
antérieurs trouvés en vérifiant — le sprite de la Géoplateforme n'existe
qu'en simple densité, si bien qu'aucun motif de surface ne se dessinait
sur un écran moderne ; et le cadrage visait le centre de l'emprise quand
les neuf événements du jour étaient groupés à son bord ouest, hors de
vue. Enfin, les trois imperfections énoncées en livrant la coque sont
**soldées**, et tenaient à une seule cause : la carte chargeait toute sa
toile alors qu'elle n'en montre que la bande centrale. Elle charge
l'emprise visible, la liste la suit, et la page ne défile plus d'un pixel.
Le tout **mesuré sur le déploiement**, pas seulement en local. Le détail
en [§14](#refonte-visuelle-).

**Plus tôt le même jour** — **la carte a été reprise après comparaison**.
La [veille GISFire](strategie.md) v1.3 a servi de miroir : leur carte est meilleure que la nôtre, et l'écart tenait à la
finition, pas à la doctrine. Le lavis départemental cessait d'être un
agrégat pour devenir un cache — il s'efface en fondu là où les marqueurs
prennent le relais ; la carte occupe la hauteur de l'écran et les
commandes se posent dessus ; une **barre temporelle** (FR-005) borne
enfin ce qui est montré, sept jours par défaut, la frontière que §17.4
donne à l'archivage — 198 événements affichés sans le dire, 8 désormais,
annoncés. Le bandeau d'état dit la **prochaine donnée attendue**, tirée
de l'`expected_interval` du registre et non d'une prédiction orbitale
(43ᵉ migration, appliquée et rejouée). Trouvée en chemin : l'attribution
IGN de la carte était **vide** depuis un moment, la porte verte portant
sur le style raster de repli et non sur le vectoriel servi. Reste à J4 :
la mise en service de `prefectures` et `massifs`, et la mesure du critère
des trente minutes. Total restant ≈ 24 semaines.

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

### Portes de qualité — dernier passage (13 septembre, soir)

| Chaîne | Commande | Résultat |
|---|---|---|
| Web | `pnpm format:check` | ✅ |
| Web | `pnpm lint` | ✅ 5 paquets |
| Web | `pnpm typecheck` | ✅ 5 paquets, TypeScript strict |
| Web | `pnpm test` | ✅ 157 tests (54 domaine, 58 web, 37 map-style, 8 contrats) |
| Web | `pnpm build` | ✅ Next 16.2.12, Turbopack |
| Worker | `ruff check` / `ruff format --check` | ✅ 110 fichiers (79 worker + 31 scripts) |
| Worker | `mypy src` + `mypy scripts` | ✅ strict, 47 + 31 fichiers |
| Worker | `pytest` | ✅ 459 tests |
| Migrations | 44 migrations sur base vierge, en CI | ✅ CI verte sur les 43 du dernier push ; la 44ᵉ (`official_sources_in_service`) appliquée **et rejouée** en production — 2 lignes puis 0 —, et la 43ᵉ (`source_next_data`) vérifiée en service — nulle pour `ign_admin_express`, qui n'a jamais rapporté de donnée, exactement ce que la vue promet. **Contrôle du 28 août** : 20 objets matériels sondés, 20 présents ; le registre `supabase_migrations` n'existe pas — `db push` n'a jamais servi, la voie réelle est l'application directe idempotente, couverte par la CI base vierge |

⚠️ Aucune de ces portes ne voit la couleur ni la taille effectives d'un
élément. Les 86 classes CSS invalides du §14 les ont toutes passées.

---

## 2. Prochaine action

**Basculer le déclencheur sur le VPS — un geste de l'auteur, le kit est
prêt.**

Le planificateur Windows tient la cadence depuis 16 h 43 mais lie
l'ingestion à une session ouverte sur une machine de travail. Le kit VPS
(`ops/vps/`, Hostinger KVM 1, Ubuntu 24.04) est écrit et vérifié ; ce
qu'il reste ne peut pas être fait d'ici : provisionner, remplir `.env`
avec la chaîne `mapfeux_ingest`, lancer `install.sh` deux fois,
**désactiver** les tâches Windows, constater `environment: production`
dans `ingest.import_runs`. Le runbook est `ops/vps/README.md`. Ensuite :
sept jours de cadence mesurée, le critère des trente minutes de J4 sur la
première publication réelle, et J5 — administration, supervision, mode
dégradé.

Les deux clés attendues sont posées et vivantes — `COPERNICUS_KEY` en
secret GitHub, la clé d'application radar dans l'environnement : au
contrôle du 11 septembre, `cams`, `radar`, `firms` et `vigilance` lisent
toutes « à jour ». `arome` lit « en retard » — donnée de 09 h UTC quand le
run de 12 h devrait être entré ; **cause non établie**, la cadence Actions
en est la première suspecte, à instruire avant d'accuser.

Restent aussi, hors critères : le coup d'œil réel sur les couches air et
radar depuis un navigateur qui composite (réserve de J9 — **toujours
ouvert** : le panneau d'aperçu de septembre affiche la page mais ne
composite pas la toile MapLibre ; ce qui a pu être vérifié à l'écran l'a
été par l'arbre d'accessibilité et les mesures du DOM), et les décisions
ouvertes — formulation du panache (§22.5), ADR du vent historique, §8.5 —
plus l'**ordonnancement (§8.1)**, que le bandeau d'état rend maintenant
lisible du public.

Décisions toujours ouvertes, sans changement : formulation du panache
(§22.5), ADR du vent historique, validation humaine des informations
officielles (§8.3), réponse à la première erreur publique (§8.5).

La spécification de J8 est **vérifiée contre le PDF v2.1** (67 pages, fourni
le 10 août) : les §13.12-16, §16.4 et §18 y sont identiques au v1.1, à une
addition près — l'indicateur d'archivage froid des extraits FWI au §13.12 —
intégrée à la migration avant son commit (`fwi_archived`, posé par le
registre). Le §16.4 v2.1 **entérine** au passage le dépôt des champs FWI en
stockage froid (PR-1), la pratique en service depuis le 5 août. Seul écart
restant, antérieur à J8 : le GRIB2 brut n'est pas conservé (ADR-025, motivé
dans `providers/arome.py`).

Restent aussi à J7, sans bloquer J8 : slug éditorial (FR-042), relecture v2
(FR-082), page « Autour de moi », plafond parlant du tableau des détections.

✅ **Contrôle du 17 août : concluant, sur les trois volets** (vérifié le 18).
Fos `MPF-V7NPXN72` et Dunkerque `MPF-GCWYFMCW` sont `archived` — le cycle de
vie a basculé les pseudo-événements au septième jour sans observation ; 802
détections classées à l'ingestion sur les 10 404 importées depuis le 10 ;
**zéro événement né près d'une source active**. « Les nouveaux ne naissent
plus » est un fait mesuré, plus une promesse.

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
| J7 | Expérience FeuScope complète : catalogue, archives, relecture, partage | 4 — gate G4 Alpha | 10 sem. | **1 sem.** | 🟡 critère de sortie atteint |
| J8 | Météo et panache : vent, panache indicatif, communes concernées | 5 — gate G5 | 6 sem. | **2 sem.** | 🟡 critère G5 atteint |
| J9 | CAMS, radar et périmètres versionnés | 6 — gate G6 | 8 sem. | **1 sem.** | 🟡 critère G6 atteint, sources en service |
| J10 | Sources statiques et réconciliation NRT/standard | 7 | 2 sem. | **0 sem.** | 🟡 critère de sortie atteint |
| J4 | Informations officielles automatisées | 8 (partiel) + ajout stratégie §4 | 6 sem. | **1 sem.** | 🟡 tout construit ; mise en service et mesure du critère |
| J5 | Administration, supervision, mode dégradé | 8 — gate G7 | 5 sem. | 5 sem. | ⬜ |
| J6 | Durcissement, recette, pilote et ouverture | 9-11 — gates G8-G10 | 9 sem. | 9 sem. | ⬜ |
| | | | 66 sem. | **≈ 24 sem.** | |

Il reste **environ 24 semaines** — nettement sous la fourchette 40-50 de la
D-0. Le recalage du 6 août avait ajouté 30 semaines au total d'alors (21) :
c'est le prix, connu et accepté, du périmètre intégral ; le 25 août en a
rendu dix-sept — J7 neuf, J8 quatre, J9 quatre — les dix semaines du
jalon FeuScope s'étant faites en dix-sept jours calendaires, la saison creuse
d'août aidant. L'option C (renfort ou partenariat,
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
- ✅ **Slug éditorial facultatif** (25 août, FR-042 et FR-060) — colonne
  `fire.events.editorial_slug`, **posée par un humain, jamais générée** : un
  slug porte des mots, et les mots suivent le §2.4. Contrainte de format
  (kebab, 80 max, segments réservés `relecture` et `opengraph-image` exclus
  — le routeur fait primer le statique), `api.fire_event` recréée (le type
  de retour change : drop puis create, signature qualifiée) et snapshot
  enrichi — **vérifié ligne à ligne contre l'original**, ce qui a évité un
  `delete` inventé et une colonne inexistante que plpgsql n'aurait révélée
  qu'en production. Route `[publicId]/[slug]` : même fiche, mauvais slug
  redirigé en **307** — un slug éditorial se corrige, un 308 le graverait ;
  l'URL nue reste servie quoi qu'il arrive, la canonique départage.
  Exercé : `ponteves-juillet-2026` posé sur `MPF-5JP8XS99` (lieu et date,
  aucun mot qui affirme), audité, quatre trajets HTTP vérifiés
- ✅ **Relecture v2 : curseur et lecture automatique** (25 août, FR-080 et
  FR-082) — composant client posé **au-dessus des mêmes URL `?at=`** : les
  liens restent le parcours sans JavaScript et l'alternative textuelle
  (FR-083), rien n'existe que l'adresse ne porte. Le pas est celui des
  passages (la donnée n'existe qu'à ces instants, FR-084), la vitesse par
  défaut s'adapte au nombre de passages, la lecture replanifie un pas à la
  fois **après** chaque navigation — le rythme absorbe l'aller-retour
  serveur — et `prefers-reduced-motion` éteint la lecture automatique
  (`useSyncExternalStore`). Observé sur Pontevès : 0 → 30 en six secondes,
  l'URL suivant chaque pas
- ✅ URL d'instant `?at=` (FR-085) : exercée depuis la v1, et rejouée par la
  lecture automatique — chaque pas est une adresse
- ✅ États générés à la demande (FR-086) : tenu depuis la v1, aucune table de
  frames — la performance ne l'a pas exigé
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
- ✅ **Page « Autour de moi »** (25 août, FR-020 à FR-024) — `/autour-de-moi`
  donne une adresse au bouton de J3 et énonce le contrat **avant** le geste :
  les garanties sont le contenu de la page, pas des mentions après coup.
  Sans JavaScript, la page reste entière et renvoie vers la recherche par
  nom ; lien posé au pied de page. Le clic géolocalisé réel reste à exercer
  (le 🟢 de J3 tient)
- ✅ Préfixe d'identifiant public **figé : `MPF-`**, le 10 août
  ([ADR-021](adr/021-prefixe-didentifiant-public.md)). La fenêtre « avant la
  première URL durable » s'était refermée avec le catalogue ; la décision
  ratifie l'état servi plutôt que de payer un renommage cosmétique. FR-067
  peut graver les URL dans les partages sociaux.

**Critère de sortie** (G4) : ✅ **atteint le 25 août** — page événement,
chronologie et relecture exercées sur les cas du corpus (Pontevès en tête,
570 détections, 57 passages), et l'URL `?at=` porte l'instant logique à elle
seule : la lecture automatique elle-même ne navigue que par adresses.

---

## 8. J8 — Météo et panache ⬜

Phase 5 du cahier v2.1, gate G5. La réserve de la stratégie v1.0 — un vent à
10 m est physiquement fragile en relief — devient une contrainte d'affichage
et d'exploitation, pas un retrait de périmètre
([stratégie §4](strategie.md#4-périmètre-du-mvp)).

- ✅ Archivage froid AROME (PR-1) en service depuis le 5 août — voir le
  chantier transverse, y compris la fuite des 8-9 août colmatée le 10. Le
  corpus du panache s'accumule, **continu et sans trou** ; l'archive porte
  bien `u10`/`v10`, le vent dont le §18 a besoin. Le colmatage a été
  **éprouvé par une semaine autonome** (11-17 août, 14 runs au registre) et
  par le 15 août en particulier, au journal des passes : l'ancien cron meurt
  à 10 h 10 sur le 404 connu, le correctif est poussé à 10 h 12, la passe
  manuelle de 10 h 18 **replie sur le run de 03 h** — le 06 h n'est pas
  encore publié, la mi-journée est sauvée par le mécanisme construit pour
  ça — et le cron neuf capte le 06 h à 11 h 01
- ✅ **Les cinq tables météo, en production** (10 août) — migration
  `20260810150000` : `model_runs`, `wind_samples`, `smoke_forecasts`,
  `smoke_steps`, `affected_municipalities` (§13.12-16, vérifiés contre le
  PDF v2.1 — identiques au v1.1, plus l'indicateur `fwi_archived` du §13.12,
  intégré). `st_isvalid` en **contrainte** (§18.5), une seule
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
- ✅ **Extraction du vent aux points des événements** (18 août, §13.13 et
  §16.4) — `pipelines/wind_samples.py` : extrait relu du froid avec
  **empreinte vérifiée** contre le registre (`download_object`), interpolation
  bilinéaire ou plus proche voisin, direction météorologique normalisée
  (`270 − atan2`, testée aux quatre cardinales), garde-fous sur composantes
  aberrantes **et** sur la distance à la cellule — le voisin le plus proche
  se rabattrait en silence sur un nœud de bord. Écriture idempotente
  (clé d'upsert, migration `20260818100000`, appliquée et rejouée en
  production ; rejeu réel : 7 lignes avant, 7 après). Exercé sur
  `MPF-8FHDJQ1G` (Saurat, Ariège) contre le run du 17/08 06 h : 7
  échantillons, vent faible et tournant de vallée (1 à 2,7 m/s, 220-320°) —
  le cas même que le §18.4 fera peser sur la confiance. **Validation §16.4
  mesurée** : bilinéaire vs voisin, Δvitesse ≤ 0,32 m/s, Δdirection 22° par
  vent faible mais 2,5° au pas le plus venté — la bilinéaire est retenue,
  13 tests dont la grille à latitudes décroissantes
- ✅ **Ingestion des runs pour le calcul, complète** (25 août, §16.4) —
  `pipelines/arome_coverage.py` : échéances d'une fenêtre, tranches qui les
  portent, manquantes récupérées au dépôt (sondées par HEAD, extraites,
  déposées au froid, journalisées `arome:panache:<tranche>`, registre
  enrichi par fusion), lecture **cousue** multi-fichiers avec empreintes
  vérifiées et empreinte composite au versionnement. Le run se choisit sur
  la **grille du fournisseur** (`runs_reaching`, généralisation de la
  mécanique du colmatage) : pour un feu de la nuit, le run de minuit, pas
  celui de la veille. Exercé sur `MPF-5SV8SEFF` : run 03 h du jour créé au
  registre, deux tranches récupérées (24 Mo archivés — le corpus y gagne),
  19 pas **à travers la couture** 06 h→07 h, confiance `high`, garde-fou de
  distance tiré en réel à 57,7 km. Le registre porte 22 runs dont un à
  13 échéances en 2 fichiers. 14 tests
- ✅ **Le panache se calcule** (18 août, §18.3) —
  `pipelines/smoke_forecast.py` : advection pas à pas (15 min) avec le vent
  relu **au point courant** — bilinéaire en espace, linéaire en temps entre
  les échéances —, géométrie en projection azimutale équidistante centrée
  sur l'événement (les mètres y sont des mètres), élargissement en cône.
  Garde-fous §18.5 en code comme en contraintes : distance et surface
  maximales (troncature dite, jamais silencieuse), aberrations en erreur
  franche, **résultat vide si les entrées manquent**, horizon partiellement
  couvert → prévision tronquée et drapeautée. Incertitude §18.4 par facteurs
  mesurés (modèle ancien, vent faible, direction instable, cellule éloignée,
  observation ancienne) ; `relief_non_evalue` et `coefficients_non_calibres`
  sont des **drapeaux permanents** de la v1. Exercé sur `MPF-8FHDJQ1G`
  (Saurat) : 11 pas, vent de vallée faible et tournant (232°→353°),
  confiance `low` par trois facteurs, enveloppe 12,42 km², **7 communes
  ariégeoises** rangées par heure d'arrivée puis exposition (FR-072,
  Arignac 45 % de sa surface), **rejeu identique** — le critère G5 « mêmes
  entrées, même sortie » est tenu. 14 tests sur vent synthétique.
  `is_current` est faux partout : rien ne se publie avant §22.5
- ⬜ Incertitude affichée et croissante ; modèle, run, échéance, résolution et
  période de validité visibles (FR-101 à FR-103)
- ✅ Versionnement complet (§18.6) : `plume-v1`, commit du worker, run météo
  (id, horodatage, chemin, empreinte), paramètres, détections sources,
  empreinte des entrées — tout vit dans `parameters`, vérifié en base
- ✅ **Désactivation immédiate, sans déploiement** (25 août, FR-106 et
  FR-155) — registre générique `app.feature_switches` (migration
  `20260825120000`, appliquée et rejouée) : l'absence de ligne vaut actif,
  l'interrupteur est un frein ; portée globale ou par territoire, résolution
  par `app.is_feature_enabled` — **source unique** pour le calcul
  d'aujourd'hui, l'affichage et l'API de demain, le mode dégradé de J5
  ensuite. Motif obligatoire, chaque bascule au journal d'audit avant
  application, même transaction ; geste d'exploitation :
  `scripts/toggle-feature.py`. Le calcul consulte l'interrupteur **avant
  tout travail** — couper coupe le téléchargement et l'écriture. Exercé en
  production : coupure globale → refus motivé ; coupure du seul Var → le
  Nord calcule, le Var non ; quatre bascules au journal
- 🟡 Communes potentiellement concernées (FR-110 à FR-114) : intersection
  géospatiale par pas ✅ — fenêtre temporelle réelle (première et dernière
  intersection), surface et part de recouvrement, rang FR-072 ; le libellé
  « potentiellement concernée » obligatoire viendra avec l'affichage, qui
  attend §22.5
- ⬜ Formulation publique obligatoire du panache (§22.5), validée métier avant
  toute mise en ligne
- ⬜ Calibration sur cas connus du corpus — Gironde 2022 — avant publication.
  ⚠️ L'archive de vent ne commence qu'au 5 août 2026 : calibrer sur 2022
  exigera une source historique (ERA5 ou réanalyse AROME), à choisir par ADR

**Critère de sortie** (G5) : ✅ **atteint le 25 août**, par exécution :
panache reproductible — le rejeu de Saurat est identique, communes comprises
— et désactivable en une action, exercé en production dans les deux portées.
Le jalon ne se ferme pas pour autant : l'affichage de l'incertitude, la
formulation §22.5 validée métier et la calibration (source de vent
historique, ADR à venir) restent dus avant toute publication.

---

## 9. J9 — CAMS, radar et périmètres ⬜

Phase 6 du cahier v2.1, gate G6. Les schémas `air` et `radar`, vides depuis
l'origine, se remplissent ici.

- ✅ **Les schémas `air` et `radar` ont leurs tables** (25 août, §13.17-18) —
  migration `20260825170000`, appliquée et rejouée : `air.model_runs` (même
  vocabulaire d'état que le registre météo, **publication atomique** par
  bascule `is_current` — l'ancien run et ses fichiers survivent, §16.5),
  `air.grid_assets` (brut, COG ou tuile par polluant et échéance — le JSON
  brut vers le navigateur n'a pas de forme ici, §19.1), `radar.frames`
  (état, expiration §16.6). RLS partout, grants ingest
- ✅ **Connecteur CAMS, exercé contre l'ADS réel** (25 août, §16.5, FR-120)
  — API Processes, jeu `cams-europe-air-quality-forecasts` (celui que le
  registre pointe depuis l'origine), modèle `ensemble` niveau sol, PM2,5 et
  PM10, emprise nationale, échéances 0-24 h ; un NetCDF par polluant déposé
  dans `raw` (dézippé du transport), registre par fusion, publication
  **seulement si le run est complet**. Sans `COPERNICUS_KEY`, le script
  explique le provisionnement et sort sans toucher au journal. Premier
  import réel le jour même, jeton posé par l'auteur : 2 × 1,68 Mo en
  43,7 s, run **publié** (première bascule `is_current`), contenu vérifié
  par relecture avec empreinte — `pm10_conc`, 25 échéances × grille 105×160
  à 0,1°, 0,8-39,9 µg/m³ médiane 7,8, un fond d'été plausible. Une leçon au
  passage : le lien de résultat ADS est **pré-signé** — y joindre les
  en-têtes d'authentification invalide la signature, 400 mesuré puis
  consigné dans le code. 11 tests. `cams-import.yml` planifie l'import
  quotidien à 08 h 45 UTC ; ⚠️ le cron attend le secret GitHub
  `COPERNICUS_KEY` — action d'exploitation, et la source ne se dira « en
  service » qu'après ses premières passes planifiées (phrase d'attente,
  dette §15)
- ✅ **Stratégie raster (§19.1), en service** (25 août soir) —
  `pipelines/cams_rasters.py` : le NetCDF relu de `raw` avec empreinte
  vérifiée devient, **par échéance**, un COG EPSG:4326 aux valeurs intactes
  et une archive PMTiles de tuiles PNG (z0-6 — au-delà, la grille de 0,1°
  n'a plus d'information, MapLibre sur-zoome). Palette **versionnée**
  `aq-atmo-v1` (seuils ATMO, borne supérieure incluse ; la carte et la
  fiche classent par le même chemin, testé `digitize` contre `band_for`) ;
  légende dans l'alias JSON `cams-{polluant}.json` — les métadonnées
  légères du §19.1, le front la lira au lieu de recopier des seuils.
  Publication ordonnée : objets à empreinte (cache éternel), registre
  `air.grid_assets` (une ligne par échéance), **alias en dernier** — un
  échec à mi-chemin laisse la version précédente entière (§16.5). Deux
  pièges du produit réel couverts par les 27 tests : longitudes 0-360
  **enroulées au méridien**, bords de grille à déduire des centres float32.
  Exercé sur le run réel : 100 objets, 3,99 Mo, 30 s ; rejeu à registre
  inchangé. Le cron quotidien enchaîne la dérivation après l'import
  (`requirements-raster.txt`, roues PyPI)
- ✅ **Échantillonnage ponctuel serveur (§19.2), sur la fiche commune**
  (25 août soir) — `api.air_grid_assets()` (migration `20260825230000`,
  appliquée, rejouée, exercée sous `anon` : 50 actifs) désigne les COG du
  run le plus récent qui en possède ; le serveur web relit le COG public
  par son URL à empreinte (cache définitif, **empreinte vérifiée à la
  lecture**) et échantillonne la **cellule la plus proche** — jamais de
  rabattement de bord (le piège du §16.4), jamais de grille vers le
  navigateur. Les huit champs du §19.2 affichés : valeur en chasse fixe,
  unité, polluant, heure de validité, résolution, méthode, source,
  `MODELLED_VALUE_NOTICE` — posé en J1, servi aujourd'hui. Au-delà de douze
  heures d'écart, la section dit « aucune valeur récente » — phrase
  conditionnée à la donnée, pas au calendrier. Exercé sur Le
  Plan-de-la-Tour : PM10 12,1 et PM2,5 6,1 µg/m³ à 18 h UTC, **recoupés
  contre le NetCDF source à la même cellule** (12,12 / 6,14), console
  vide. 10 tests purs, dont le `-0` du bord nord
- ✅ **Couche raster air sur la carte** (25 août soir, FR-121) — commutable
  et **éteinte par défaut** : la carte parle d'abord des détections (§8.1).
  La couche lit l'alias, choisit l'échéance la plus proche de maintenant
  (péremption à douze heures — une carte de la veille présentée comme
  actuelle serait un mensonge coloré) et se glisse **sous** les lavis et
  les événements, rééchantillonnage au plus proche voisin. La légende est
  **lue de l'alias** — bornes, couleurs et version de la palette qui a
  réellement coloré les tuiles, jamais une copie — avec unité, grille,
  heure de validité, modèle, run et nature modélisée. Un piège MapLibre au
  dossier : `isStyleLoaded()` répond faux transitoirement après `load`, et
  un `once('load')` posé alors ne tire plus jamais — remplacé par un
  drapeau posé dans le gestionnaire. Exercé sur serveur local (carte
  pilotée par sa poignée de dev — le panneau sans compositing ne tire
  jamais `requestAnimationFrame`) : couche sous les six couches mapfeux,
  tuiles chargées sans erreur, bascule PM2,5/PM10, extinction propre.
  ⚠️ Le rendu n'a pas encore été **regardé** dans un navigateur qui
  composite — la leçon des 86 classes CSS vaut ici : un coup d'œil réel
  reste dû au prochain passage sur le déploiement
- ✅ **Connecteur radar : frames, conversion contrôlée, timeline, expiration**
  (25 août nuit, §16.6, FR-123) — API DPRadar (arbre de liens OGC, **sans
  historique** : chaque production manquée est perdue, le cron colle aux
  cinq minutes du produit, et une passe qui trouve la frame déjà servie
  sort sans rien retélécharger). Mosaïque lame d'eau 500 m en HDF5 ODIM
  (h5py — le driver HDF5 manque aux roues rasterio), brut archivé avant
  analyse, conversion **contrôlée** : grandeur `ACRR` exigée, dimensions
  vérifiées, et la convention de grille — origine au coin bas-gauche, y
  vers le nord — **prouvée sur chaque fichier** en reprojetant son propre
  coin. Image web Mercator au plus proche voisin (emprise sur le pourtour
  échantillonné : les bords stéréographiques bombent, les coins seuls
  rogneraient), palette versionnée `radar-lame-v1` — six bandes d'intensité
  mm/h, découpage éditorial **assumé comme tel** dans la légende.
  `radar.frames` avec expiration à deux heures ; timeline en alias JSON
  d'au plus 24 frames (§19.3), réécrit en dernier. Exercé sur l'orage réel
  du 25 au soir : frame 18:25, PNG 1533×1352 de 33 ko, rejeu « déjà
  servie », et la cellule maximale du brut (97 mm/h, bande extrême)
  **recoupée au pixel près** dans le PNG publié. 19 tests sur ODIM
  synthétique au projdef réel ; clé par application, jamais celle de la
  vigilance (testé). ⚠️ le cron toutes les cinq minutes attend le secret
  GitHub `METEOFRANCE_RADAR_API_KEY`
- ✅ **Animation radar sur la carte** (26 août matin, §19.3, FR-123 à
  FR-124) — panneau « Radar de précipitations » sur /carte, éteint par
  défaut : timeline lue de l'alias, frame la plus récente d'abord avec son
  heure d'acquisition (FR-123), lecture/pause à 600 ms par pas, pas-à-pas
  toujours disponible, préchargement progressif des frames. La sélection
  filtre l'expiration **contre l'horloge du lecteur** : l'alias de 08 h 06
  listait encore la frame de 06 h 15 expirée à 08 h 15 — le cas, constaté
  en production le matin même, est testé. `prefers-reduced-motion` fait
  disparaître la lecture automatique (le pas-à-pas n'est pas une
  animation), mécanique `useSyncExternalStore` comme la relecture. Couche
  = source image MapLibre sous les lavis et les événements, fondu raster
  coupé — 300 ms de fondu fabriqueraient des fantômes de pluie. Exercé sur
  la vraie carte : bascule 08:00↔07:20 en lecture, pause tenue, la frame
  expirée écartée en direct (2 servies sur 3 listées)
- ✅ **FR-125 exercée — G6 se solde** (26 août matin) : CAMS et radar
  coupés par interception réseau sur /carte — messages d'absence dans les
  deux panneaux, les cinq couches de détections intactes, console vide ;
  et côté fiche commune, quatre tests serveur (PostgREST en erreur,
  Storage injoignable, COG en 500, empreinte déviante) prouvent que la
  panne rend une liste vide, jamais une exception. Les chaînes d'ingestion
  sont séparées par construction (workflows distincts)
- ✅ Panne de CAMS ou du radar sans effet sur la carte des détections
  (FR-125) — exercée le 26 août, voir le dossier de G6 ci-dessous
- ✅ **`fire.event_perimeters` : la machinerie des périmètres versionnés**
  (25 août, §13.23, FR-090 à FR-096) — migration `20260825190000` : six
  natures, confiance à quatre valeurs (`not_applicable` — un périmètre
  officiel n'est pas « confiance élevée », il est hors échelle), surface
  **recalculée** sur l'ellipsoïde avec méthode consignée et surface annoncée
  conservée à côté, chaîne `supersedes`, masquage sans destruction, GiST.
  EFFIS au registre des sources (`disabled` comme ses aînés). Conversion
  GeoJSON réparée par `make_valid`, le non-surfacique refusé — 7 tests.
  **Exercé sur pièces** : les deux cartographies EFFIS réelles du complexe
  de Pontevès importées sur `MPF-5JP8XS99` — 967 ha (1ᵉʳ août) puis la
  révision à 498 ha (4 août) qui la remplace, version conservée ; surfaces
  recalculées recoupant les annoncées à 0,4 ha près, centres à 3-6 km du
  point représentatif. L'exercice a attrapé un défaut réel : deux versions
  partageaient un chemin d'archive et le second dépôt écrasait le brut de la
  première (FR-096) — le chemin porte désormais la date de publication
  source. Import KML/Shape : à l'adaptateur suivant, le GeoJSON couvre EFFIS
- ✅ **L'affichage des périmètres — fiche, carte, relecture** (25 août,
  FR-091 à FR-094) — `api.fire_event_perimeters` sert toutes les versions
  publiques avec source, méthode et version courante ; un périmètre masqué
  rend la précédente courante — la fiche ne reste pas nue sur une erreur
  retirée. Sur la carte, **FR-093 est porté par la structure** :
  `line-dasharray` n'étant pas pilotable par donnée, l'officiel a sa couche
  au trait plein d'autorité et tout le reste passe par la couche tiretée —
  il n'existe pas de chemin de code qui dessinerait un périmètre
  satellitaire en contour opérationnel. La fiche détaille la version
  courante (surface **avec sa méthode**, source et publication, résolution,
  confiance à quatre valeurs, `PERIMETER_DISCLAIMER`) et garde les
  précédentes visibles. **FR-094** : la publication d'un périmètre est un
  instant de relecture à part entière — vérifié sur Pontevès aux trois
  époques : absence dite au 23/07, 967 ha au 02/08, la révision à 497 ha au
  05/08, curseur et liens compris. Au passage : clés React dédoublonnées du
  tableau des détections, défaut préexistant révélé par les 500 lignes de
  Pontevès

**Critère de sortie** (G6) : ✅ **atteint le 26 août**, par exécution — les
périmètres EFFIS réels de Pontevès portent source, nature, dates, méthode
et confiance, leur remplacement conserve la version précédente (25 août) ;
et couper CAMS puis le radar, exercé par interception, ne touche ni la
carte ni les fiches : messages d'absence, détections intactes, console
vide. Reste à J9, hors critère : le coup d'œil réel sur les couches depuis
un navigateur qui composite (réserve déjà consignée).

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
- ✅ **Réconciliation trimestrielle NRT/standard, en service** (26 août,
  §16.3, FR-032) — `pipelines/reconciliation.py` : la passe lit la
  **disponibilité FIRMS** (les bornes standard avancent, FIRMS rogne le
  NRT en face — constaté contigu au jour près), croise avec la base par
  satellite — ce qui est écarté est **dit avec son motif** — et relit le
  standard par fenêtres de cinq jours sur l'API Area (les produits `_SP`
  s'y servent comme le NRT, colonne `type` comprise). Le rapprochement
  passe par la **clé naturelle** (satellite, horodatage, coordonnées à
  cinq décimales) : `provider_key` inclut la version brute (« 2.0NRT » ≠
  « 2 », testé) et ne bouge jamais — la prémisse « même clé » du plan
  était fausse, corrigée ici. Liste blanche du §17.1 enfin écrite :
  `thermal_type`, `standard_payload` (la ligne standard complète, à côté
  du brut immuable), `reconciled_at` — le verrou d'idempotence. **Pas
  d'insertion des lignes sans correspondance (v1, motivé au module)** : le
  standard est national quand la base de mai-juillet est pilote 06/83.
  Exercé en production : 3 060 lignes de mai (N20), **4 enrichies sur 7
  candidates** — les 3 autres n'existent pas au standard, le retraitement
  écarte des fausses alarmes — 3 056 non-appariées comptées ; **rejeu à
  zéro changement**. Et la ligne `type=2` reçue du standard était déjà
  classée par le masque de proximité : la vérité terrain FIRMS confirme
  le registre spatial. Cron trimestriel (`reconcile-firms.yml`),
  `records_updated` câblé pour la première fois. 10 tests
- ⚠️ N21 sans corpus retraité (dette du §15) : la réconciliation est
  bornée par la disponibilité FIRMS et **se détectera elle-même** le jour
  où un produit `VIIRS_NOAA21_SP` paraîtra — d'ici là, l'exclusion est
  imprimée à chaque passe.

**Critère de sortie** : ✅ **atteint le 26 août**, par exécution — la carte
ne montre plus la moitié non-végétation sans le dire depuis le masque du
10 août, et rejouer la réconciliation sur la fenêtre déjà traitée n'a rien
changé : 0 enrichie, 4 déjà réconciliées.

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
- ✅ **Politique de republication tranchée et gravée** (26 août) —
  [ADR-026](adr/026-republication-automatique-liste-blanche.md), stratégie
  §8.3 : **liste blanche automatique**, republication attribuée et jamais
  réécrite, sans valideur humain ; masquage sans destruction ; la voie
  éditoriale `official_messages` garde son second valideur. La ligne « ADR
  à rédiger sur la politique de republication » se solde du même geste
- ✅ **Capture préfectorale en liste blanche, 06 et 83** (26 août, §9.2,
  FR-141 à FR-143) — les sites préfectoraux nouvelle génération n'ont
  **plus de RSS** (sondé sur les deux pilotes) : le connecteur lit la page
  « Actualités » elle-même — cartes DSFR, seules les datées sont des
  publications, tout lien hors du domaine de l'autorité est rejeté et
  compté. Liste blanche en base (`app.official_feeds`, administrable),
  citations dans `official_feed_items` : titre verbatim, URL, date au
  jour — aucune heure inventée. Exercé en production : 10 publications par
  préfecture — dont « Mesures d'interdictions » (83) et « Risque feux de
  forêt » (06), la matière même du jalon — brut archivé avant analyse,
  **rejeu à zéro nouvelle et vingt revues**. `ImportCounters` expose
  désormais `run_id` : cette chaîne est la première à estampiller ses
  lignes. Cron au quart d'heure ; ⚠️ source `disabled` jusqu'à ses
  premières passes planifiées — même doctrine que CAMS et radar
- ✅ **Accès aux massifs forestiers, capté et affiché** (28 août, FR-140,
  ADR-026) — le site interservices des préfectures
  (risque-prevention-incendie.fr) publie un niveau par massif et par jour,
  la prévision du lendemain vers 18 h. La capture croise le JSON
  quotidien, le référentiel GeoJSON du site et **les libellés officiels au
  vocabulaire propre à chaque département** (tableau indexé dans le Var
  dont la queue compose le niveau 5 exceptionnel, clés nommées dans le
  06), republiés verbatim. Deux pièges de terrain couverts et testés : le
  06 vit sous `/6/`, et son référentiel est nu quand le JSON quotidien
  préfixe. Exercé en réel : 9 massifs du Var et 7 du 06 avec leurs
  libellés, rejeu inerte, page territoire du Var affichant le verbatim
  préfectoral et le renvoi à la carte officielle qui fait foi. Cron aux
  trois heures ; ⚠️ source `disabled` jusqu'aux passes planifiées. Autres
  départements : à l'ouverture de leurs territoires, jamais en masse
- ✅ **Rapprochement géographique, en service** (26 août soir) — un
  **appariement de structure, jamais une lecture** (§2.4) : noms entiers du
  référentiel communal détectés dans les titres (frontière de mot, sans
  accents ni tirets — « Toulon » ne se trouve pas dans « toulonnais »),
  croisés avec la commune la plus proche de l'événement dans une fenêtre
  de −7/+14 jours autour de son activité. Exercé sur pièces : deux
  citations réelles portent leurs communes (Sainte-Maxime, Hyères), et le
  garde-fou temporel a démontré les deux sens — l'événement d'Hyères de
  juin existe, la citation ZMEL date de février, hors fenêtre, écartée.
  ⚠️ Limite assumée et testée : un nom court articulé (« Le Val ») peut
  sur-apparier une expression courante — borné par le département et la
  fenêtre, et la fiche dit que la publication peut concerner un autre sujet
- ✅ **Affichage des citations** (26 août soir, FR-104) — la page
  territoire d'un département porte ses publications préfectorales (titres
  verbatim, attribués, datés, note disant la capture automatique — vérifié
  sur le Var, dix citations réelles) ; la fiche événement montre celles
  qui mentionnent sa commune, sous un intitulé qui **est** le critère de
  rapprochement, avec l'avertissement qu'une publication peut concerner un
  autre sujet. Une fiche sans rapprochement reste entière (vérifié sur
  Pontevès). Rien de tout cela n'est une estimation de MapFeux, et rien
  n'y ressemble
- ✅ **Gestion des contradictions observation / statut officiel** (26 août
  nuit, FR-145, §17.4-17.5) — une détection postérieure à un statut ne le
  modifie jamais en silence : **alerte de cohérence** au journal d'audit
  (fonction `security definer` — le rôle d'ingestion, sans accès au
  journal par doctrine, reçoit la capacité étroite de signaler ; dédup
  interne, une alerte par statut) câblée dans la chaîne des dix minutes,
  et **bandeau de divergence** sur la fiche : les deux faits datés côte à
  côte, aucun n'écrase l'autre. Seul « éteint » diverge d'une observation
  postérieure — « circonscrit » et « maîtrisé » annoncent par définition
  une activité qui continue, les signaler apprendrait à ignorer l'alerte.
  La définition vit deux fois, alignée et dite telle (prédicat du domaine,
  fonction SQL). **Exercée en transaction annulée** — le seul moyen
  honnête sans fabriquer un statut officiel public : statut synthétique
  posé, 1 divergence signalée à la bonne forme, dédup à 0 au second appel,
  annulation, zéro trace. Production réelle : 0 divergence — exact,
  aucun statut officiel n'existe encore

- ✅ **Les deux sources officielles sont en service** (11 septembre, nuit,
  FR-110 et FR-150). Le geste était réservé aux « premières passes
  planifiées » ; il est posé après contrôle des passes réellement
  enregistrées — `massifs` 69 passes dont 68 complètes depuis le 28 août,
  `prefectures` 100 dont 95 complètes depuis le 27 — et de la donnée
  servie : 256 niveaux dans `app.massif_access_levels`, 23 publications
  dans `app.official_feed_items`. Les cinq passes partielles de
  `prefectures` sont des sites préfectoraux injoignables
  (`RemoteProtocolError` sur le 06 et le 83) : l'amont, pas le connecteur,
  et le mode partiel est fait pour ça. Migration idempotente **appliquée
  et rejouée** (2 lignes puis 0). Le bandeau passe de « 3/6 sources en
  service » à « 5/8 », `/statut` les dit « À jour », et la page du Var
  porte le niveau d'accès verbatim et quatre publications préfectorales
  liées à `var.gouv.fr`

**Critère de sortie** : une information préfectorale publiée est visible sur la
fiche de l'événement correspondant en moins de 30 minutes, attribuée et datée,
sans réécriture.

⚠️ **Mesuré le 13 septembre 2026 : non tenu, et non tenable sous le
déclencheur actuel.** Le cron de `prefectures` est déclaré toutes les quinze
minutes ; sur 114 passes enregistrées depuis le 27 août, l'écart médian
entre deux passes est de **209 minutes** (moyenne 212, p90 327, maximum 573),
et **un seul écart sur 113** tient sous les trente minutes. La latence
médiane d'une publication est donc d'une heure et demie avant même la
revalidation de la fiche (deux minutes), et ce n'est pas le travail de J4 qui
manque — tout le jalon est construit et en service. La mesure, étendue à
toutes les sources, est consignée en [stratégie §8.1](strategie.md#81-ordonnancement--tranché-le-28-juillet-2026)
: seul le cron quotidien tourne comme déclaré.

Deux constats de mesure, à connaître :

- **La préfecture publie un jour, pas une heure.** `published_on` est une
  date : une latence en minutes ne peut pas se lire dans la donnée
  elle-même, seulement se déduire de la cadence. Et `published_on` est
  **réécrite à chaque passe** — par construction (« sans réécriture » veut
  dire qu'on reflète la date que la préfecture affiche, y compris quand
  elle la change) ; `first_seen_at` est le seul ancrage de capture honnête.
  La seule publication parue depuis la naissance du connecteur, vue le
  1ᵉʳ septembre, porte aujourd'hui la date du 7 : la préfecture l'a mise à
  jour, et nous l'avons suivie
- **Il n'y a presque rien à mesurer.** Une publication nouvelle en dix-sept
  jours sur le Var, aucune sur les Alpes-Maritimes depuis le 8 juin ; 3
  publications sur 23 rapprochées d'une commune. Le critère se mesurera
  pour de bon le jour d'un feu, sur une préfecture qui publie — et ce
  jour-là, il tiendra ou non selon le déclencheur choisi.

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
  reste en colonne. La liste emprunte les symboles de la carte — disque plein
  pour un événement étayé, anneau creux pour une observation isolée — plutôt
  que d'inventer un second vocabulaire pour la même distinction. *(La légende
  était alors posée à côté de la carte pour ne pas tomber hors de vue ; la
  passe du 11 septembre l'a ramenée dessous, la carte occupant désormais la
  hauteur de l'écran et les clés de lecture essentielles étant montées dans la
  barre temporelle, au contact des points qu'elles décodent.)*
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

#### La carte reprise après comparaison — 11 septembre 2026

La [veille GISFire](strategie.md#veille-du-11-septembre-2026--gisfire-re-sondé--la-torchère-a-sa-page)
a servi de miroir : leur carte est meilleure que la nôtre, et l'essentiel
de l'écart n'était pas doctrinal mais de finition. Trois séances, toutes
**regardées dans un navigateur** avant d'être déclarées faites.

- ✅ **Le lavis départemental cesse d'écraser les marqueurs.** Il montait à
  50 % d'opacité et restait peint jusqu'au zoom 9, par-dessus les
  événements auxquels la stratégie de zoom (§21.3) lui demande de céder :
  au zoom 8, cadrage par défaut de `/carte`, les disques disparaissaient
  dans le saumon. Il s'efface en fondu — plein à z6 où il est le sujet,
  0,3 à z7 où les deux coexistent, nul à z8. Un agrégat qui masque le
  détail qu'il annonce ne renseigne plus, il cache
- ✅ **La carte prend la hauteur de l'écran**, et les commandes se posent
  dessus. Elle occupait un quart de page sous un mur de texte, avec une
  colonne de 320 px où trois paragraphes d'explication prenaient la place
  des commandes. Le partage est net : `layers-panel.tsx` porte ce qui se
  manipule — calques groupés par famille, l'observation **sans
  interrupteur** puisqu'elle est le sujet —, le dessous de carte ce qui se
  lit. Les mentions obligatoires n'ont pas bougé : FR-121 garde résolution,
  unité, heure, nature modélisée et l'avertissement, désormais lisibles
- ✅ **Barre temporelle** (FR-005) — fenêtres 12 h / 24 h / 48 h / 7 j /
  Tout, le compte de ce qui est montré, et la clé de lecture des couleurs
  au contact des points qu'elle décode (paliers exportés de la légende :
  une définition, deux présentations). Toute la mécanique existait —
  `fires_in_bbox` et la route acceptent `since`, et le catalogue
  `/evenements` filtre par période depuis le 9 août ; la carte, seule,
  ne le proposait pas. C'était de la mise en scène. **Le défaut vient du
  cahier** : §17.4 tient `archived` pour « hors fenêtre d'affichage
  courant » et le cycle de vie archive au septième jour ; la carte servait pourtant tout l'historique de l'emprise — 198
  événements en septembre, l'été varois entier. Elle en montre 8, ceux des
  sept derniers jours, et le dit ; « Tout » reste à un clic. Filtrer en
  l'annonçant n'est pas masquer (§17.7). Le rendu serveur applique la même
  fenêtre : carte et liste comptent enfin pareil
- ✅ **Le bandeau d'état annonce la prochaine donnée** — « prochaine vers
  21:16 », depuis `next_data_expected_at` posé dans `api.source_status`
  (migration `20260911150000`). C'est une **attente, pas une prédiction** :
  dernière donnée plus l'`expected_interval` du registre, celui qui
  qualifie déjà une source de `delayed` ; « vers » porte l'approximation,
  l'heure est absolue parce qu'une durée vieillit mal dans une page en
  cache, et une échéance dépassée n'est pas affichée

⚠️ **L'attribution de la carte était vide** — `maplibregl-attrib-empty`,
0 × 0 pixel, constaté le 11 septembre. Le style **vectoriel** de la
Géoplateforme ne déclare pas d'attribution sur ses sources ; le test de
`map-style` vérifiait bien qu'elle existe, mais sur le style **raster**,
qui n'est que le repli — une porte verte sur le chemin qu'on n'emprunte
pas, exactement le motif des 86 classes. Rétablie par `customAttribution`
et vérifiée à l'écran (« © IGN — Géoplateforme »), la barre temporelle
s'arrêtant au-dessus d'elle plutôt que de la recouvrir (§9.5). Une
obligation de licence ne tenait plus depuis un moment.

Deux défauts encore, attrapés en vérifiant plutôt qu'en supposant : en
375 px l'heure du bandeau se détachait de sa phrase pour flotter seule, et
le **build a échoué** sur `/_not-found` — une date invalide franchit
toutes les comparaisons puisque `NaN` les fait toutes échouer, si bien
qu'un `new Date(undefined)` devenait l'échéance retenue. Garde-fou posé
dans la fonction pure du domaine, avec son test.

#### La coque d'application et le fond sombre — 11 septembre 2026, soir

La comparaison reprise à froid, quelques heures après : sur les quatre
points travaillés plus tôt, GISFire et MapFeux se ressemblent. Sur les deux plus gros, non.
Mesuré en 1280 × 800 avant la séance : leur page fait un écran de haut,
la carte commence à y = 0 ; la nôtre faisait **3,4 écrans**, la carte
commençait à **426 px** et n'occupait que **47 %** de l'écran à
l'ouverture, coupée par le pli. Et notre coque sombre servait un fond de
carte **blanc**.

- ✅ **`/carte` est une coque d'application.** La carte prend l'écran
  moins l'en-tête et le bandeau, tout le reste flotte dessus : identité
  et liste à gauche, calques à droite, fenêtre temporelle en bas. Rien
  n'est retiré — l'avertissement §2.4 ouvre le premier carton, la liste
  textuelle §8.6 reste rendue par le serveur, l'attribution IGN reste
  permanente (§9.5) — tout a changé de place, rien de statut. La règle
  qui manquait est nommée : **à gauche ce qui se lit, à droite ce qui se
  manipule**
- ✅ **Les panneaux sont placés par une grille**, non par des décalages
  calés un à un. La première version les posait chacun sur son coin ; ils
  se chevauchaient dès que la barre temporelle passait à deux lignes, et
  le panneau de calques recouvrait la commande de zoom de MapLibre — une
  carte dont on ne peut plus cliquer le « + ». Contrôlé par mesure : zéro
  chevauchement entre les six boîtes, commandes de MapLibre comprises
- ✅ **Fond de carte sombre**, dérivé de la feuille « gris » de l'IGN.
  La Géoplateforme n'en publie aucune : sondées le 11 septembre,
  `standard`, `gris`, `attenue`, `classique`, `epure` et `accentue`
  répondent 200, `sombre`, `dark` et `nuit` répondent 404. La
  transformation **inverse la clarté** et ne touche à rien d'autre —
  géométrie, seuils de zoom, épaisseurs, tiretés restent ceux de l'IGN.
  Les 525 couleurs de la feuille sont des gris neutres, si bien que
  l'inversion préserve exactement les écarts de contraste voulus. Deux
  bornes plutôt qu'une inversion franche : le blanc devient `#121212` et
  non du noir, le noir devient un gris clair et non du blanc — un fond
  parfaitement noir ferait des marqueurs orange des trous de lumière
- ✅ **La bascule de thème est suivie en direct**, attribut de racine et
  préférence système. Les calques de MapFeux sont reposés à chaque
  `style.load` plutôt qu'au seul `load` : `setStyle` remplace le style
  entier. Vérifié sur quatre bascules — les cinq calques reviennent, la
  couche air retrouve sa position sous les événements, et le nombre de
  gestionnaires d'événements ne bouge pas

⚠️ **Deux défauts trouvés en vérifiant**, tous deux antérieurs à la
séance. Le **sprite** de la Géoplateforme n'existe qu'en simple densité —
`@2x.png` et `@2x.json` répondent 404 — alors que MapLibre le demande dès
qu'un écran a plus d'un pixel physique par pixel CSS : aucun motif de
surface ne se dessinait sur un écran moderne. Réécrit à la requête,
vérifié à densité 2 (sprite chargé, trente images). Et le **cadrage**
visait le centre de l'emprise pilote quand les neuf événements du jour
étaient groupés à son bord ouest, le plus occidental hors de l'écran : la
page s'ouvrait sur une carte sans anomalie pendant que sa liste en
annonçait neuf. Le centre suit désormais l'étendue des événements servis
— le milieu, pas la moyenne, pour qu'une grappe ne tire pas le cadrage à
elle. Le zoom, lui, ne bouge pas : l'ajuster aux données ferait remonter
le lavis qu'on venait de faire céder.

La colonne de lecture se replie, enfin, et la caméra en tient compte
(`padding`). Ce n'est pas un confort : elle couvre en permanence le tiers
ouest de la carte, et rien ne garantit que les marqueurs du jour soient
ailleurs. Ouverte par défaut — sans JavaScript elle reste là, et c'est le
seul chemin d'accès textuel de la page.

#### Les trois imperfections annoncées, soldées — 11 septembre 2026, nuit

Elles avaient été énoncées en livrant la coque. Elles tenaient en fait à
**une seule cause** : la carte chargeait et cadrait sur toute sa toile,
panneaux compris, alors qu'elle n'en montre que la bande centrale.

- ✅ **La liste suit la carte** (§8.6). Le mot « synchronisée » du cahier
  n'était pas honoré : la liste venait du serveur pour l'emprise initiale
  et n'en bougeait plus, pendant que la carte rechargeait à chaque
  déplacement. La barre annonçait 19 événements et le carton voisin 8 ;
  aucun ne mentait, ensemble ils étaient illisibles. La carte tient déjà
  la réponse — elle vient de la demander pour ses marqueurs — et la liste
  la lit. Aucune requête de plus. Le rendu serveur reste son premier
  état : c'est le seul qui existe sans JavaScript, et le paragraphe
  d'excuse a disparu avec le défaut
- ✅ **Plus un marqueur sous un panneau.** `getBounds()` rend l'emprise de
  toute la toile, y compris le tiers que la colonne recouvre : on chargeait
  donc des événements qu'on ne montrerait pas, et la liste désignait des
  marqueurs cachés derrière elle-même — dix sur dix-neuf au relevé. La
  carte charge désormais l'emprise **visible**, marges déduites. Ce qu'elle
  liste, elle le montre. Le premier cadrage, lui, ajuste l'étendue des
  événements servis dans cette même bande
- ✅ **La page ne défile plus** : 0 pixel, mesuré. C'est la répartition en
  colonne du gabarit qui la mesure — `main` cesse de grandir avec son
  contenu et prend ce qui reste entre l'en-tête et le pied de page. Aucune
  hauteur n'est écrite à la main ; la version précédente en réservait une
  pour l'en-tête, qu'il aurait fallu corriger à chaque retouche. Le pied de
  page **reste**, resserré : ses liens — mentions légales, confidentialité,
  accessibilité — doivent être atteignables depuis toutes les pages. La
  carte y perd 83 px et gagne de ne plus rien cacher sous le pli

⚠️ **Les quatre nombres écrits à la main ont été retirés.** Les retraits de
caméra recopiaient des largeurs CSS ; ils se sont trompés deux fois dans la
même soirée — la barre temporelle avait grandi, et elle passe à deux lignes
sur un écran étroit. Les panneaux se mesurent maintenant eux-mêmes
(`overlay-padding.ts`, pur et testé ; un observateur de taille dans la
coque), et c'est la **géométrie** qui dit s'ils recouvrent la carte : sous
640 px ils s'empilent dessous et leur retrait tombe à zéro sans qu'aucun
seuil ne soit écrit. Un nombre écrit à la main décrit une mise en page à un
instant ; les panneaux, eux, continuent de vivre.

#### Contrôle sur le déploiement — 11 septembre 2026, 21 h

Tout ce qui précède a été **regardé et mesuré sur
<https://mapfeux.vercel.app/carte>**, pas seulement en local. Le rendu
servi porte bien la construction du soir (`x-vercel-cache: HIT`, `age: 0`).

La preuve la plus nette est l'emprise que la carte demande en production :

```
bbox=5.1704,43.2847,6.2250,44.0338
```

1,055° de large. Au zoom 8, la toile entière couvre 2,81° ; la bande
visible fait 1024 − 360 − 280 = 384 px, soit **1,055°**. En latitude,
0,749° demandés pour 377 px visibles, soit **0,749°**. Au centième près :
la carte ne charge que ce qu'elle montre, et c'est une garantie de
construction — non un comptage de marqueurs qui pourrait tomber juste par
hasard un jour de faible activité.

| Contrôle | Attendu | Constaté en production |
|---|---|---|
| Défilement de la page | nul | **0 px** |
| Carte | plein bord sous la coque | y = 172, 513 × 1024 |
| Pied de page | présent, resserré | 685 → 768, les neuf liens |
| Liste / barre / carte | même compte | **9 / 9 / 9**, « dans l'emprise affichée » |
| Attribution IGN | permanente | « © IGN — Géoplateforme » |
| Sprite à densité 2 | pas de `@2x` | `PlanIgn-Gris.png` et `.json`, rien d'autre |
| Console | sans erreur | sans erreur |

Le fond sombre s'affiche — Marseille, Aix-en-Provence, PNR du Luberon, PNR
de Camargue, Grimaud, Golfe du Lion en gris clair sur presque noir. La
**bascule de thème a été actionnée sur le site servi** : la page passe au
sombre, les marqueurs survivent au remplacement du style — c'est le chemin
`style.load` qui repose les calques — et la liste se met à jour. En clair,
`rgb(246, 248, 250)` en fond de page et fond de carte clair. En 375 × 812 à
densité 2, la page défile normalement et la carte redevient un bloc de
485 px : la règle de coque ne mord bien qu'au-dessus de 640 px.

Un comportement à connaître, qui n'est pas un défaut : sur téléphone la
liste reste sur le lot du rendu serveur — « au chargement de la page » —
jusqu'au premier déplacement. Sans panneau flottant il n'y a pas de marge
posée, donc aucun mouvement de caméra pour déclencher un rechargement. La
phrase le dit, et bascule sur « dans l'emprise affichée » au premier geste.

#### Une fausse assurance, révélée par une mise en service — 11 septembre 2026

Mettre `massifs` en service a fait dire au bandeau de **toutes les pages** :

> 5/8 sources en service · **maj il y a moins d'une minute** · prochaine vers 22:50

En permanence, et toujours par la même source. Le niveau d'accès aux
massifs du lendemain paraît la veille au soir : le connecteur datait donc
la donnée du **jour décrit**, c'est-à-dire de demain. `dataAgeMs` ramène
tout écart négatif à zéro, zéro se formate en « moins d'une minute », et
la source la plus en avance gagnait le concours du « plus récent ». Le
service annonçait s'être mis à jour à l'instant, quoi qu'il arrive aux
huit autres — exactement la fausse assurance que le §5.13 interdit.

- ✅ **La cause** : `import-massifs.py` enregistre désormais l'instant où
  il **lit**, non le jour décrit. C'est la convention du projet — CAMS
  enregistre l'heure de son run, FIRMS celle de l'acquisition, jamais
  l'échéance décrite. L'heure de publication de la préfecture n'étant pas
  connue, le moment de la passe est le meilleur ancrage honnête ; la
  deviner serait l'inventer. Le jour décrit reste où il a un sens,
  `app.massif_access_levels.valide_le`
- ✅ **La ceinture** : `mostRecentPast` écarte du concours toute donnée
  horodatée en avance, symétrique d'`earliestUpcoming` qui écarte les
  échéances passées. Aucune source, présente ou à venir, ne peut plus
  faire dire au bandeau qu'il vient d'être à jour
- ✅ **L'aveu** : `formatDataRecency` dit « dans 4 h 28 min » là où
  l'ancienne formule disait « il y a moins d'une minute ». Une tolérance
  de deux minutes absorbe les écarts d'horloge sans les commenter

Vérifié après correction : le bandeau annonce « maj il y a 2 h 21 min » —
le radar, qui est effectivement la donnée la plus récente déjà là.

Les anciennes lignes d'`ingest.import_runs` gardent leur date de validité
et n'ont **pas** été réécrites : le `max()` de la vue les laisse derrière
dès la première passe postérieure à minuit, et corriger des
enregistrements historiques pour gagner quelques heures d'affichage —
déjà honnête depuis l'aveu — serait payer cher un bénéfice qui vient tout
seul.

#### L'accueil s'ouvre sur la carte — 13 septembre 2026, soir

Nouvelle comparaison, trois captures au même format — ensemblepourlaforet.fr,
GISFire, nous. Le plus gros écart n'était pas sur `/carte` mais sur
**l'accueil** : les deux références s'ouvrent sur une carte et trois grands
chiffres, le nôtre sur de la prose, et « ouvrir la carte » était un lien
texte. Sur la carte elle-même, quatre défauts de finition à l'échelle
nationale.

- ✅ **La carte nationale en tête de l'accueil**, vivante et non manipulable
  — un lien vers `/carte`, pas une carte. Les lavis départementaux des sept
  derniers jours se chargent d'eux-mêmes, au zoom pour lequel ils ont été
  dessinés (§21.3) : vérifié, 129 départements chargés, 94 avec agrégat.
  `interactive={false}` sur `BaseMap` : ni zoom, ni déplacement, ni
  commandes ; l'attribution IGN reste, elle est due quelle que soit la forme
  (§9.5), et le bouton « Ouvrir la carte » a été déplacé en haut à droite
  parce qu'il la recouvrait
- ✅ **Trois chiffres lus en base à l'instant du rendu** — 86 événements sur
  24 h, 76 départements et 646 événements sur 7 j, 6/8 sources à jour au
  moment du contrôle. Ils ne disent pas « combien de feux », que MapFeux ne
  sait pas, mais ce qu'un service d'observation peut affirmer sans mentir.
  Revalidation à cinq minutes, comme l'API. Mesuré : ils tiennent dans le
  premier écran d'un 1280 × 800 (bas à 791 px), après deux marges
  resserrées
- ✅ **La recherche sur la carte**, dans le carton d'identité — c'est là
  qu'on cherche, et c'est le seul geste qu'on vient faire ici hors regarder
- ✅ **La coque au-dessus de la carte passe de 172 à 96 px** : le bandeau de
  positionnement, dû sur toutes les pages (§1, §22.5), tient sur une ligne
  en corps réduit sur `/carte` seulement — même mécanique `:has()` que le
  pied de page
- ✅ **Lisibilité à l'échelle nationale** : contours départementaux de 0,6 à
  0,85 — la carte n'avait plus de squelette, seulement un trait de côte ;
  rayons des marqueurs relevés d'un cran (6/11/16, traîne 4,5) — à 5 px un
  événement étayé se confondait avec un anneau isolé ; et une **lueur** sous
  les événements de moins de vingt-quatre heures, disque flou dans la
  couleur d'âge, deux fois le rayon. L'orange reste le seul propos chaud de
  la carte (§8.1) : il n'est posé que là où quelque chose vient d'être
  observé, et un événement archivé n'a pas de lueur

- ✅ **Une carte au survol d'un marqueur** — commune, identifiant, statut,
  nombre d'observations, fiabilité, dernière observation et son âge, dans
  les **mêmes mots que la liste textuelle**, sans cliquer. Ancrée sur le
  marqueur et non sur le curseur, une seule fenêtre réutilisée, disparaît
  en quittant le point ; le clic ouvre toujours la fiche. L'âge se compte
  **au survol**, depuis maintenant — l'`ageHours` de la couche est figé à
  sa construction et ne sert qu'à la couleur. Contenu pur et testé
  (`hover-card.ts`, sept tests), tout ce qui vient des données passe par
  l'échappement HTML. Vérifié : « Les Mées · MPF-SZQH9K1Z — Pas de nouvelle
  observation · 1 détection · fiabilité faible — Dernière observation
  10/09/2026 14:14 (il y a 3 j 8 h) », et rien une fois le marqueur quitté

- ✅ **Le zoom intermédiaire (7–8), regardé avec les données du jour.** Au
  zoom 7, la carte n'était qu'un trait de côte, des contours sans nom et
  des marqueurs qui se recouvraient — trois événements de Fos dans dix
  pixels. Deux réponses. **Des grappes sous le zoom 9** (§21.3) : la source
  regroupe, une grappe porte son compte, prend la **couleur de son membre
  le plus récent** — une grappe qui contient une détection de la nuit doit
  le dire —, compte ses étayés, et s'ouvre au clic jusqu'au zoom où elle
  se défait ; jamais une fiche, une grappe n'en a pas. Au survol, la même
  carte que les marqueurs, dans le même vocabulaire : « 5 événements · dont
  aucun étayé · 5 observations isolées · le plus récent il y a 6 h 7 min ».
  Et **les noms de départements** en petites capitales du zoom 6 au zoom
  8,5, effacés devant tout marqueur, dans les glyphes que la Géoplateforme
  sert avec son style. Vérifié au zoom 7 : trois grappes (5, 3 en orange
  à moins de huit heures ; 2 en gris), treize marqueurs isolés, quatorze
  noms rendus ; un clic sur la grappe de cinq passe au zoom 8 et la défait
  en marqueurs. Aucun nombre nouveau écrit en double : la couleur des
  grappes sort de la même expression que celle des marqueurs, paramétrée
  sur la propriété

Ce qui n'a pas bougé, et c'est voulu : le titre de l'accueil — formulation
publique, validation métier avant toute retouche —, l'avertissement du §2.4
et son filet orange, aucune couleur chaude en décoration. Les deux
références tirent une part de leur effet d'un fond de feu ou de satellite ;
ce n'est pas notre axe, et ce n'est pas ce qui manquait.

#### La fiche, regardée avec le même œil — 15 septembre 2026

Mesuré sur MPF-VHR8YJ85, cinquante-sept observations à Condé-sur-l'Escaut,
à 1 024 px de large : une page de 4 609 px, la carte au pixel 3 635 — sous
un tableau de cinquante-sept lignes — et **vide** : la fiche ne lui passait
aucun événement, elle montrait un fond IGN au zoom 11 sans rien dessus. Les
deux références ouvrent un feu sur sa carte et son évolution.

- ✅ **La carte en tête, à côté du titre**, avec **l'empreinte des
  observations** : chaque observation membre est un point coloré par son
  âge, disque ou anneau selon sa confiance — le vocabulaire de `/carte` et
  de la relecture, pas un troisième. Cadrée sur l'empreinte (`fitBounds`,
  marges de 36 px), jamais au-delà du zoom 13 : un pixel isolé de 375 m ne
  devient pas une carte de quartier. La position, la commune et
  l'horodatage restent en texte à sa gauche et s'impriment sans elle
  (FR-051, FR-068). Vérifié : 57 points rendus, un seul identifiant, un
  seul point pour Vicq-sur-Mer au zoom 13
- ✅ **La puissance radiative par passage** — un graphique SVG rendu par le
  serveur, sans JavaScript. Les pixels d'un même satellite à moins de dix
  minutes font un passage ; sa puissance est la **somme** des pixels
  connus, un calcul dit comme tel (FR-053). L'échelle part de zéro et
  plafonne à un nombre rond ; un passage sans puissance est marqué au sol,
  pas omis ; sous deux passages connus, pas de graphique. Géométrie pure
  dans une boîte de mille sur cent étirée à la colonne, libellés en HTML
  pour ne pas rétrécir sur téléphone. Vérifié : six passages du 15/09
  02:54 (N20, 15 observations, 57,8 MW) au 06:34 (Aqua, 3 observations,
  138,8 MW), chacun lisible au survol. Seize tests (`passes.ts`,
  `frp-chart.ts`)
- ✅ **Le tableau se replie au-delà de douze lignes** : les douze plus
  récentes, puis un `<details>` natif qui dit combien il en garde — 45 sur
  Condé. Rien n'est masqué au sens du cahier : tout est dans la page,
  rendu par le serveur, et s'ouvre sans JavaScript. La page passe de 4 609
  à 3 153 px
- ✅ **Une carte à lot fixe ne redemande jamais l'API** — trouvé en
  vérifiant, thème clair : l'empreinte remplacée par les événements de
  l'emprise, en gris d'archive. Le rechargement « au changement de
  fenêtre » de `BaseMap` tenait son premier montage pour acquis ; le mode
  strict de développement rejoue les effets, et le garde-fou ne tenait
  qu'une fois. Il est maintenant réservé aux cartes qui suivent l'emprise
  (`reloadOnMove`) — la fiche, la relecture et l'accueil en sont
  protégés. Production non touchée par le symptôme (pas de mode strict),
  mais le code était faux

Le corps de la fiche tient désormais dans une colonne de lecture de
soixante-quinze caractères, comme la relecture ; seule la tête est large,
parce qu'elle porte une carte. Reste, vu en passant : la carte au survol
d'un point de l'empreinte propose « cliquer pour ouvrir la fiche » depuis
la fiche elle-même — le clic ne fait que recharger la page ; et
l'impression ne porte que les douze premières lignes du tableau et
l'annonce du pli, un `<details>` fermé ne s'ouvrant pas à l'impression.

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

### Déclencheur d'ingestion ✅

Tranché le 13 septembre 2026 après mesure ([stratégie §8.1](strategie.md)) :
le planificateur Windows remplace le cron GitHub Actions pour tout ce qui
est sous-quotidien et quotidien ; seule la réconciliation FIRMS
trimestrielle reste sur Actions.

- ✅ **Sept tâches** `\MapFeux\MapFeux-*` — Ingestion (10 min), Radar
  (5 min), Prefectures (15 min), Vigilance (:20), Massifs (:20 toutes les
  trois heures), Cams (10 h 45), AromeArchive (12 h 45) — déclarées une fois
  dans `ops/windows/tasks.psd1`, lues par l'enregistrement et par
  l'exécution : deux listes divergeraient à la première retouche
- ✅ **Sondé avant d'écrire** : S4U refusé sans élévation, interactif
  accepté et exécuté (résultat 0). Aucun mot de passe demandé ni stocké.
  Contrepartie assumée : session ouverte, verrouillée suffit
- ✅ **Console masquée** par `launch.vbs` — la leçon du 6 août : une tâche
  interactive garde une console sur le bureau, et un Ctrl-C y reste
  possible. Le VBS attend la fin et rend le vrai code de sortie
- ✅ **Première passe par le déclencheur lui-même** à 16 h 43, une minute
  après l'enregistrement, avant tout lancement manuel : FIRMS sur quatre
  satellites, AROME, radar, préfectures — succès, en base
- ✅ **Journaux** `logs/<tâche>.log`, bornés à 2 Mo sur deux générations,
  hors dépôt. Première lecture en mojibake (« mosa├»que ») : PowerShell 5.1
  relit la sortie native en page 850. Réglé aux deux bouts — python forcé
  en UTF-8, console lue en UTF-8 — et vérifié à la passe suivante
- ✅ **Les crons retirés des sept workflows**, note posée dans chacun ; le
  `workflow_dispatch` demeure en secours pour une panne du poste
- ✅ **Le kit VPS, le soir même** (`ops/vps/`) — le poste n'est qu'une
  étape. Minuteries systemd engendrées depuis un registre devenu **commun**
  aux deux déclencheurs, `ops/tasks.json`, en UTC comme les crons remplacés
  (`tasks.psd1` a disparu ; le côté Windows lit le JSON et convertit en
  local, réenregistré et exercé). `install.sh` rejouable, qui refuse
  d'écrire un secret et teste l'IPv6 pour dire s'il faut le pooler ;
  `env.template` sans secret ; `status.sh` ; runbook avec la bascule et le
  retour arrière. Vérifié ici : syntaxe, sept paires d'unités aux
  expressions attendues, scripts marqués exécutables dans git
- ⬜ **Basculer** — provisionner, `.env`, installer, désactiver Windows,
  constater `environment: production` en base (geste de l'auteur)
- ⬜ **Remesurer la cadence sur sept jours**, comme celle qui a condamné
  Actions — sur le VPS cette fois

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
| Décisions ouvertes restantes | Réponse à la première erreur publique (§8.5), qui couvre aussi le canal de republication (ADR-026). Validation humaine (§8.3) tranchée le 26 août — liste blanche automatique, [ADR-026](adr/026-republication-automatique-liste-blanche.md) ; préfixe (§8.4) tranché le 10 août ; ⚠️ l'ordonnancement (§8.1), « tranché » par un retour à plus tard, presse désormais : il étrangle radar et capture préfectorale | Réponse avant J6 ; §8.1 à réexaminer |
| Mesures faussées par le cache Vercel | `Cache-Control: no-cache` ne traverse pas le cache de bordure : on conclut sur un rendu vieux de plusieurs jours en croyant lire l'état courant. Lire `x-vercel-cache` et `age`, ou interroger la base. `/statut` répondait `STALE` le 6 août | Continu |
| Affichage des détections par commune | `/communes/[insee]` renvoie vers la carte faute de le porter. Le rattachement existe en base, la requête et le bloc restent à écrire | J3 |
| Phrases d'attente à relire à chaque mise en service | Une phrase écrite quand une brique manquait devient fausse le jour où elle arrive. Celle de `/commune` a survécu un jour à l'ingestion | Continu |
| Aucune purge de rétention | `raw` est annoncé à trente jours au registre, rien ne l'applique. Le job devra exclure `cold` **explicitement**, et non par omission (§29) | J5 |
| Rétention des rasters CAMS et radar | ~100 objets et 4 Mo par run CAMS quotidien (préfixe `cams/`), plus ~33 ko par frame radar (préfixe `radar/`) dans le compartiment public `tiles`, aucune purge d'objets. Les frames radar **expirent en base** (statut) mais leurs PNG restent ; garder la fenêtre servie suffit. À traiter avec la purge de `raw` | J5 |
| Cadence de **toutes** les sources sous-quotidiennes étranglée par GitHub Actions | Le cron `*/5` tourne à ~une passe par heure (mesuré les 25-26 août : 06:21, 07:22, 08:06) : la timeline porte 2-3 frames au lieu de 24, l'animation est courte, et les bornes de fraîcheur du registre sont calées sur cette réalité (1 h / 3 h) plutôt que sur les cinq minutes du produit — annoncer cinq minutes afficherait « En retard » en permanence, le signal exact et faux de la leçon vigilance. L'[ordonnancement propre](strategie.md#81-ordonnancement--revenir-à-celery-et-redis) (§8.1, décision ouverte) ramènera cadence et bornes aux cinq minutes. ⚠️ **La dette est sortie des journaux** le 11 septembre : le bandeau d'état annonçant désormais la prochaine donnée attendue, une passe manquée se lit **en page d'accueil**. Une source servie à une passe par heure contre un `expected_interval` d'une heure vit sur la frontière de `delayed` en permanence — le radar a été vu `stale` en cours de journée, `fresh` le soir même, et AROME lisait `delayed` à l'instant du contrôle (cause propre non établie, voir §2). Ce n'est pas un défaut d'affichage : le bandeau dit juste, et ce qu'il dit est le symptôme. **Mesuré le 13 septembre sur sept jours** : médiane réelle entre passes — firms 111 min (déclaré 10), radar 213 (5), vigilance 244 (60), prefectures 181 (15), arome 1 431 (180, soit une fois par jour) ; seul cams, quotidien, tient (1 436 pour 1 440). Tableau complet en stratégie §8.1. **Bloquait le critère de sortie de J4** — tranché le 13 septembre : planificateur Windows, sept tâches, crons Actions retirés (§14). Reste à remesurer sur sept jours | §8.1 — tranché, à remesurer |
| Portes vertes sur des chemins qu'on n'emprunte pas | L'attribution IGN de la carte était **vide** en production (constaté le 11 septembre, `maplibregl-attrib-empty`, 0 × 0 pixel) alors qu'un test la vérifiait : il portait sur le style **raster**, qui n'est que le repli, tandis que le style **vectoriel** servi ne déclare rien sur ses sources. Même motif que les 86 classes CSS du §14 — ce n'est pas l'absence de test qui coûte, c'est le test qui rassure ailleurs. À chaque assertion sur un artefact servi, se demander **quelle variante l'utilisateur reçoit** | Continu |
| Une source peut dater sa donnée en avance | `massifs` enregistrait `source_data_at` au **jour décrit** — le niveau du lendemain paraît la veille au soir — et non à l'instant de lecture. La fraîcheur en tirait un âge négatif, ramené à zéro puis formaté en « moins d'une minute » : le bandeau de toutes les pages a annoncé « maj il y a moins d'une minute » en permanence dès la mise en service (11 septembre). Connecteur corrigé, et deux garde-fous posés dans le domaine — `mostRecentPast` écarte du concours ce qui est horodaté en avance, `formatDataRecency` dit « dans 4 h 28 min » plutôt que de faire passer une avance pour une fraîcheur. **À vérifier à chaque nouveau connecteur** : `source_data_at` est l'instant de production, jamais l'échéance décrite | Continu |
| Types Supabase non générés | Requêtes typées à la main dans `lib/data/` | J1 |
| Pas de CSP | En-têtes partiels seulement | J6 |
| Aucun test de composant | Recherche et carte n'ont que le typage | J6 (Playwright) |
| ADR-001 à 013 non rédigés | Décisions actées, non documentées | Au fil des jalons |
| Schémas `air` et `radar` vides | Traité le 25 août : les trois tables sont en production (§13.17-18). Les schémas restent sans données tant que les connecteurs n'ont pas leurs clés — voir §2 | Traité |
| `app.official_messages` inutilisable par une ingestion | La table exige un `created_by` humain et un `validated_by` : la vigilance a donc ses propres tables. La [décision §8.3](strategie.md#83-validation-humaine-des-informations-officielles) reste ouverte pour les sources en texte libre | J4 |
| Pas de fichier de lock conda | Parité d'environnement non garantie | Avant le premier déploiement |
| Schémas `air` et `radar` déclarés au registre | Traité le 26 août : les deux sources sont `active` après leurs premières passes planifiées, `/statut` les dit « À jour ». Aucune phrase d'attente à retirer côté web — l'affichage « à venir » venait du statut au registre, et s'est résolu avec lui. Les intervalles radar (1 h / 3 h) sont calés sur la cadence Actions réelle, voir la dette dédiée | Traité |
| Regroupement encore lent | Chiffré le 9 août : **11,2 h de CPU saturé sans terminer un seul regroupement complet des quatorze saisons** (337 757 détections, recherche de candidats en mémoire). Les passes incrémentales de production restent rapides (orphelines seules), mais tout recalcul complet à l'échelle est impraticable — la structure de voisinage se paie par détection × événements. À traiter avant la montée en charge (§6.3) | J6 |
| Coût d'un jeu de calibration | Borné par le sous-corpus (16 544 détections) : 102 à 161 s par jeu (mesure du 6 août, `data/calibration/axes-sous-corpus.csv`). La calibration est close ; le banc reste prêt pour une v2 des règles | Traité |
| `cluster-detections.py` vise encore la production | Traité le 6 août : bascule `--calibration` posée, cible affichée avant d'agir. L'usage production reste légitime — reprise manuelle aux paramètres de référence | Traité |
| N21 sans corpus retraité | 30 180 lignes — 8,9 % du corpus — servies en NRT : FIRMS ne publie aucun produit standard NOAA21 (confirmé à l'API de disponibilité le 26 août). La réconciliation trimestrielle, bornée par cette disponibilité, **se détectera elle-même** le jour où le produit paraîtra ; d'ici là chaque passe imprime l'exclusion | Suit FIRMS |
| La borne de R4 suppose le corpus standard dense | Un satellite indisponible en milieu de période retraitée verrait ses lignes NRT de la panne écartées à tort. FIRMS ne publie pas de calendrier de couverture. La borne employée est consignée dans le compte rendu du corpus | J2 |
| Corpus dérivé versionné | Le Parquet pèse 6,8 Mo et se régénère depuis les zips. Chaque régénération dépose un nouveau blob dans l'historique. À arbitrer : le compte rendu JSON suffit à prouver la provenance | J6 |
| `api.fire_events` expose l'`id` interne | §15.1 demande des identifiants publics opaques. Non exploité par nos réponses, mais lisible via PostgREST | J6 |
| Coût d'un pic non chiffré | Conditionne un point d'arrêt — dernier préalable de phase 0 encore ouvert | Phase 0 |
| Réponse à la première erreur publique | Runbook éditorial absent | Avant J6 |
| MFA super_admin non appliquée | La contrainte en base exige `mfa_required` pour `super_admin`, mais l'enrôlement TOTP n'existe pas (§14.4). D'ici J5, ne pas employer de compte super_admin au quotidien — `grant-admin.py` l'affiche | J5 |
| `fires_in_bbox` sous son nom historique | L'API publique dit désormais `events` (cahier v2.1 §15.2) ; la fonction SQL interne garde son nom — la renommer passe par une migration, sans bénéfice public | Libre |
| Migrations appliquées hors bande | Le chargement direct par script casse le `db push` suivant si la migration n'est pas rejouable — 42701 sur `source_key` le 8 août, puis 42725 sur `events_catalog` le 9 : pendant un rejeu, deux surcharges coexistent et un `comment on function` au nom nu devient ambigu. Règles : idempotence (`if not exists`, `on conflict`, `create or replace`) **et** toute référence de fonction qualifiée par sa signature complète dès qu'elle évolue | Continu |
| Tableau des détections de la fiche plafonné en silence | Traité le 25 août : le plafond est nommé (`DETECTION_TABLE_LIMIT`) et annoncé — « Tableau partiel : les 500 observations les plus récentes, sur 570 » vérifié sur Pontevès, avec renvoi vers la relecture qui rejoue tout | Traité |
| Événement de démonstration en production | Traité le 10 août : `DEMO-2607A1` et ses 7 détections `demo:%` supprimés selon la recette documentée par la fixture, entrée d'audit posée avant les suppressions (état avant + motif), dans la même transaction. Vérifié : zéro restant en base, `/archives` sans la démo (cache MISS), fiche en 404 | Traité |
| Le banc ne reprend pas où il s'est arrêté | Traité le 8 août : le troisième accident (mise en veille) l'a réclamé, comme prévu. `--reprendre` saute les jeux déjà sur disque et complète le CSV | Traité |
| Jetons du thème recopiés dans la carte OG | Satori (moteur d'`opengraph-image.tsx`) ne lit ni variables CSS ni feuilles de style : les jetons clairs y sont en dur, avec le commentaire qui l'assume. Une retouche de palette doit être répercutée à la main | Libre |
| Pseudo-événements industriels encore servis | Traité : archivés par le cycle de vie au septième jour, contrôle du 18 août concluant (Fos et Dunkerque `archived`, zéro naissance près d'une source depuis le 10, 802 détections classées à l'ingestion) — voir §2 | Traité |

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
