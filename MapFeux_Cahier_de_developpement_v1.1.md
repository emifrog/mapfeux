# PROJET MapFeux

## Cahier complet de développement

**Plateforme nationale publique de suivi des détections thermiques, des feux potentiels et des fumées**  
Version 1.1 — 27 juillet 2026  
Statut : document de référence consolidé pour conception, développement et recette  
Nom de code : Projet MapFeux — marque définitive à valider  
Territoire pilote : Alpes-Maritimes (06)  
Déploiement cible : France métropolitaine, puis extension progressive aux territoires ultramarins

> **Positionnement essentiel**  
> Le Projet MapFeux est un service d'information cartographique grand public, indépendant de tout dispositif opérationnel. Il ne constitue ni un système d'alerte, ni une source de confirmation terrain, ni un outil de commandement. Les observations satellitaires, traitements algorithmiques et modèles affichés peuvent être retardés, incomplets ou incertains. Les consignes et publications des autorités restent prioritaires.

---

# Sommaire

1. Résumé exécutif  
2. Vision, objectifs et principes directeurs  
3. Périmètre du produit et découpage en phases  
4. Utilisateurs, besoins et parcours  
5. Exigences fonctionnelles du MVP  
6. Exigences non fonctionnelles  
7. Architecture de l'information et routes  
8. Principes UX, cartographie et accessibilité  
9. Sources de données et règles d'utilisation  
10. Architecture technique cible  
11. Organisation du monorepo  
12. Architecture Supabase et PostGIS  
13. Modèle de données détaillé  
14. Sécurité, rôles et politiques RLS  
15. API publique et API d'administration  
16. Pipelines d'ingestion et d'orchestration  
17. Détection, dédoublonnage et regroupement des événements  
18. Modèle simplifié de panache de fumée  
19. Qualité de l'air et radar  
20. Administration et supervision éditoriale  
21. Performance cartographique et stratégie de cache  
22. Sécurité applicative, confidentialité et conformité  
23. Observabilité et exploitation  
24. Stratégie de tests et recette  
25. Environnements, CI/CD et déploiement  
26. Roadmap de réalisation  
27. Backlog initial par epic  
28. Critères d'acceptation et Definition of Done  
29. Risques, limites et plans de réduction  
30. Préparation des phases 2 et 3  
31. Annexes techniques

---

# 1. Résumé exécutif

Le Projet MapFeux doit fournir une carte nationale compréhensible par le grand public, permettant de consulter les détections thermiques satellitaires récentes, de les regrouper en événements cohérents, d'estimer un panache de fumée indicatif, d'identifier les communes potentiellement concernées et de consulter les données météorologiques, de qualité de l'air et de précipitations associées.

Le produit est conçu dès le premier jour comme une plateforme multi-territoires. Aucun fork par département ne doit être créé. Les départements, régions, communes et territoires frontaliers sont des configurations et des géométries administratives gérées dans la base.

La version 1.1 place la **fiche événement** au centre de l'expérience. Chaque événement dispose d'une URL permanente, d'une synthèse immédiatement disponible, d'une chronologie textuelle, d'un historique des changements et d'une distinction stricte entre observation satellitaire, traitement algorithmique, estimation de modèle, information officielle et correction éditoriale. Une détection satellite ne peut jamais devenir une confirmation officielle par simple transition automatique.

Le MVP public ne comporte pas de compte utilisateur public, de signalement citoyen, de notification push, de données DFCI, de SITAC ou de données opérationnelles. Seuls les administrateurs disposent d'un compte. La liaison éventuelle à DFCI OPS est reportée à une phase 3 et devra reposer sur une passerelle filtrée, unidirectionnelle par défaut et juridiquement séparée.

L'architecture retenue repose sur :

- Next.js, TypeScript, Tailwind CSS, shadcn/ui et MapLibre GL JS pour l'application web et PWA ;
- Supabase pour PostgreSQL, PostGIS, Auth, Storage, fonctions SQL, politiques RLS et administration des données ;
- un service Python conteneurisé séparé pour les traitements GRIB/NetCDF, les imports, les calculs géospatiaux et le panache ;
- Redis et une file de tâches pour les traitements asynchrones ;
- un CDN et des caches HTTP pour les données cartographiques publiques ;
- des données officielles ou institutionnelles provenant notamment de NASA FIRMS, Météo-France, Copernicus CAMS et IGN.

Le lancement recommandé commence par le département des Alpes-Maritimes, sans limiter l'architecture au 06. Le Var sert de second territoire de validation, puis la couverture est étendue à toute la France métropolitaine. Le nom « Projet MapFeux » reste un nom de code tant que la marque définitive, les domaines et les antériorités ne sont pas validés.

# 2. Vision, objectifs et principes directeurs

## 2.1 Vision produit

Rendre les informations disponibles sur les détections thermiques et les fumées plus lisibles, territorialisées et transparentes, sans créer de confusion avec les informations opérationnelles ou les alertes officielles.

## 2.2 Objectifs du MVP

- Afficher une vue nationale de la situation récente.
- Permettre la sélection immédiate d'un département ou d'une commune.
- Agréger les détections satellitaires issues de plusieurs capteurs.
- Réduire le bruit visuel en regroupant les détections probablement liées au même phénomène.
- Présenter clairement la date, l'heure, le capteur, la confiance et la fraîcheur de la donnée.
- Calculer une enveloppe indicative de fumée à partir du vent disponible.
- Croiser cette enveloppe avec les communes.
- Afficher les données de qualité de l'air et de précipitations utiles.
- Donner accès aux liens officiels du territoire concerné.
- Fonctionner correctement sur téléphone, tablette et ordinateur.
- Fournir un état visible des sources et des éventuelles pannes.

## 2.3 Objectifs non poursuivis dans le MVP

- Confirmer qu'un incendie est en cours.
- Déclarer qu'un feu est éteint.
- Produire une alerte de sécurité civile.
- Remplacer les communications des préfectures, SDIS, SIS ou communes.
- Modéliser précisément la dispersion atmosphérique en relief complexe.
- Fournir une position en temps réel des moyens, personnels ou opérations.
- Permettre des contributions citoyennes.
- Publier des données DFCI sensibles ou réservées.

## 2.4 Principes directeurs

### Transparence et provenance

Chaque information doit afficher sa source, son heure d'acquisition, son heure d'import, son degré d'incertitude et sa date de validité. Elle est classée dans une provenance explicite : `observation`, `algorithmic_inference`, `model_estimate`, `official_information`, `editorial_correction` ou `external_report`.

### Prudence sémantique

L'interface utilise les termes « détection thermique », « événement probable », « dernière observation » et « panache indicatif ». Elle évite « incendie confirmé », « feu actif », « feu fixé », « feu maîtrisé » et « feu éteint » sans source officielle attribuée et datée.

Trois dimensions ne doivent jamais être confondues :

- la fraîcheur technique de l'événement ;
- le niveau de vérification de son existence ;
- un éventuel statut opérationnel communiqué officiellement.

### Séparation des responsabilités

Supabase conserve la donnée structurée et applique les règles d'accès. Le service Python exécute les traitements lourds. Next.js présente les résultats et sert de couche d'API publique stabilisée.

### Multi-territoires natif

Toute fonctionnalité doit fonctionner avec un `territory_id`, un code INSEE ou une emprise géographique. Aucun code métier ne doit contenir de condition spécifique au département 06, sauf une configuration explicite et documentée.

### Dégradation maîtrisée

Une panne de CAMS ou du radar ne doit pas rendre la carte des détections indisponible. Chaque source est indépendante et l'interface annonce précisément les couches indisponibles. Toute page événement doit pouvoir afficher le dernier état connu, son horodatage exact et l'âge de la donnée, sans écran de chargement indéfini.

# 3. Périmètre du produit et découpage en phases

## 3.1 Phase 1 — MVP public national

Inclus :

- carte nationale ;
- sélecteur de territoire ;
- recherche de commune ;
- géolocalisation locale et volontaire ;
- import NASA FIRMS ;
- regroupement en événements ;
- fiche événement permanente et partageable ;
- chronologie textuelle de l'événement ;
- statuts de vérification et provenance des informations ;
- panache indicatif simplifié ;
- communes potentiellement concernées ;
- vent et métadonnées de modèle ;
- qualité de l'air CAMS ;
- radar de précipitations ;
- liens officiels ;
- pages méthodologie, sources, statut et mentions ;
- PWA ;
- administration privée ;
- supervision des imports, corrections manuelles non destructives et publication d'informations officielles attribuées.

## 3.2 Phase 2 — Enrichissements publics

Préparés mais non bloquants pour le MVP :

- relief et topographie ;
- comparaison de plusieurs modèles météo ;
- données des AASQA régionales ;
- périmètres EFFIS et surfaces brûlées ;
- danger quotidien par massif ;
- accès aux massifs ;
- relecture cartographique et historique avancé ;
- notifications territoriales ;
- visualisation 3D ;
- carte probabiliste de dispersion ;
- scénarios multi-altitudes ;
- enrichissement éditorial par les autorités partenaires.

## 3.3 Phase 3 — Connexion éventuelle à DFCI OPS

La phase 3 n'est pas incluse dans le schéma public du MVP. Elle devra respecter les règles suivantes :

- bases et projets Supabase distincts ;
- domaines, politiques d'accès et journaux distincts ;
- aucune clé `service_role` partagée ;
- passerelle API dédiée et auditable ;
- liste blanche explicite des données transmissibles ;
- absence de flux automatique du système opérationnel vers le public, sauf validation métier ;
- authentification forte et contrôle d'organisation ;
- test de sécurité indépendant avant mise en service.

# 4. Utilisateurs, besoins et parcours

## 4.1 Personas

| Persona | Besoin principal | Risque à éviter |
|---|---|---|
| Habitant | Savoir si une détection ou de la fumée concerne sa commune | Interpréter la carte comme une alerte officielle |
| Touriste | Comprendre rapidement une situation locale | Ne pas connaître le nom du département ou de la commune |
| Journaliste | Accéder à des données sourcées et datées | Confondre une détection thermique avec un feu confirmé |
| Élu ou agent communal | Obtenir une vue territoriale synthétique | Reprendre une estimation comme information opérationnelle |
| Administrateur Projet MapFeux | Superviser les sources et corriger les erreurs visibles | Modifier ou supprimer la donnée brute sans traçabilité |
| Analyste technique | Vérifier les calculs et la fraîcheur des modèles | Ne pas pouvoir reproduire une sortie |

## 4.2 Parcours principal — Consulter son territoire

1. L'utilisateur ouvre la carte nationale.
2. Il accepte ou refuse la géolocalisation.
3. Il recherche une commune ou choisit un département.
4. La carte se centre sur le territoire.
5. Les événements récents sont affichés avec une légende temporelle.
6. L'utilisateur sélectionne un événement.
7. Une fiche présente le niveau de vérification, la dernière observation, les capteurs, le vent et le panache indicatif.
8. Une chronologie distingue les observations, calculs, corrections et informations officielles.
9. Les communes potentiellement concernées sont listées.
10. Les liens vers la préfecture et les informations officielles sont visibles.

## 4.3 Parcours national

1. L'utilisateur consulte la France entière.
2. Il voit un résumé par département, sans charger toutes les géométries communales.
3. Les départements comportant des détections récentes sont mis en évidence.
4. Un clic ouvre la vue départementale et charge les données détaillées dans l'emprise.

## 4.4 Parcours administrateur

1. Authentification par lien magique ou fournisseur configuré.
2. Accès au tableau de santé des sources.
3. Consultation des imports récents et erreurs.
4. Recherche d'un événement.
5. Actions possibles : marquer comme source thermique connue, masquer de la vue publique, fusionner, séparer, enrichir un lien officiel, publier une information officielle attribuée ou ajouter une correction éditoriale.
6. Chaque action crée une entrée d'audit avec auteur, date, motif et valeurs avant/après.
7. Les changements significatifs produisent une entrée de chronologie publique ou interne selon leur nature.

# 5. Exigences fonctionnelles du MVP

## 5.1 Carte nationale

**FR-001** — La page d'accueil affiche une carte de France métropolitaine avec la Corse.  
**FR-002** — La carte affiche un résumé des détections et événements des dernières 24 heures.  
**FR-003** — Les marqueurs sont regroupés visuellement selon le niveau de zoom.  
**FR-004** — L'utilisateur peut activer ou masquer les couches : événements, détections brutes, panaches, qualité de l'air, radar et limites administratives.  
**FR-005** — La date de dernière mise à jour de chaque couche est visible sans ouvrir une page secondaire.  
**FR-006** — Une légende explique les couleurs, symboles et plages temporelles.  
**FR-007** — Le système ne charge que les données nécessaires à l'emprise visible.

## 5.2 Sélecteur de territoire

**FR-010** — Le sélecteur permet de choisir une région, un département ou une collectivité configurée.  
**FR-011** — La recherche accepte le nom, le code départemental et les variantes usuelles.  
**FR-012** — Les départements sont regroupés par région.  
**FR-013** — L'URL est partageable et conserve le territoire sélectionné.  
**FR-014** — Les territoires non encore ouverts peuvent être configurés comme « à venir » sans code spécifique.

## 5.3 Recherche de commune et géolocalisation

**FR-020** — La recherche retourne les communes par nom et code postal indicatif, avec code INSEE comme identifiant de référence.  
**FR-021** — Les homonymes affichent le département.  
**FR-022** — La sélection centre la carte et ouvre une synthèse communale.  
**FR-023** — Le bouton « Autour de moi » utilise l'API de géolocalisation du navigateur uniquement après consentement.  
**FR-024** — La position n'est pas enregistrée par défaut.  
**FR-025** — Une fonction PostGIS résout la commune contenant le point transmis.  
**FR-026** — En cas de refus ou d'échec, la recherche manuelle reste pleinement fonctionnelle.

## 5.4 Détections thermiques

**FR-030** — Le système importe les capteurs VIIRS disponibles et MODIS.  
**FR-031** — Chaque détection conserve les attributs bruts utiles : latitude, longitude, date/heure UTC, capteur, satellite, confiance, FRP, jour/nuit, version et taille de pixel si disponible.  
**FR-032** — Les heures sont stockées en UTC et affichées dans le fuseau du territoire ou de l'utilisateur.  
**FR-033** — Les doublons d'import sont bloqués par une clé idempotente.  
**FR-034** — Les points plus anciens sont différenciés visuellement.  
**FR-035** — Le détail rappelle qu'un point correspond au centre approximatif d'un pixel satellite et non nécessairement au foyer exact.  
**FR-036** — Les sources thermiques connues peuvent être signalées sans supprimer la détection brute.

## 5.5 Événements regroupés

**FR-040** — Plusieurs détections proches dans l'espace et le temps peuvent être regroupées dans un événement.  
**FR-041** — L'événement possède un identifiant public non séquentiel et une URL permanente.  
**FR-042** — Le système conserve l'historique de ses détections membres et de ses représentations successives.  
**FR-043** — Les fusions et séparations manuelles sont auditables et réversibles.  
**FR-044** — La fraîcheur technique distingue au minimum : `new`, `recent`, `not_recent`, `archived` et `hidden`.  
**FR-045** — Le niveau de vérification distingue : `satellite_detection`, `probable_event`, `publicly_reported` et `officially_confirmed`.  
**FR-046** — Un statut opérationnel tel que fixé, maîtrisé, contrôlé ou éteint est nullable et ne peut être renseigné qu'avec une source officielle.  
**FR-047** — Aucun job automatique ne peut définir `officially_confirmed` ni un statut opérationnel officiel.  
**FR-048** — Un score de fiabilité interne est calculé, puis présenté au public sous une forme simple : faible, modéré ou élevé.  
**FR-049** — Le niveau de fiabilité ne qualifie ni la gravité, ni la surface, ni le statut opérationnel du feu.

## 5.6 Fiche événement

**FR-050** — Chaque événement dispose d'une page permanente `/evenements/[publicId]`.  
**FR-051** — La page fournit un contenu serveur minimal utilisable avant le chargement de la carte.  
**FR-052** — Le dernier état connu reste visible lorsque les flux temps réel ou une couche secondaire sont indisponibles.  
**FR-053** — Les observations, estimations, informations officielles et corrections sont visuellement différenciées.  
**FR-054** — Le partage d'une URL conserve l'événement et, lorsque demandé, l'instant de chronologie consulté.

La fiche doit afficher :

- identifiant public ;
- niveau de vérification et fraîcheur technique ;
- éventuel statut officiel avec organisme, source et date ;
- position représentative et communes proches ;
- première et dernière observation ;
- âge exact de la dernière donnée ;
- nombre de détections ;
- satellites/capteurs concernés ;
- FRP minimale, maximale et médiane si disponible ;
- niveau de fiabilité ;
- provenance de chaque bloc d'information ;
- chronologie récente ;
- panache indicatif et période de validité ;
- vent utilisé ;
- communes potentiellement concernées ;
- qualité de l'air disponible ;
- liens officiels du territoire ;
- avertissement méthodologique ;
- bouton de partage.

## 5.7 Chronologie et préparation de la relecture

**FR-055** — La fiche affiche une chronologie textuelle triée par date de survenue, indépendante de la date d'import.  
**FR-056** — Les types minimaux sont : nouvelle observation, changement de regroupement, nouveau calcul de panache, changement significatif du vent, information officielle, correction éditoriale et changement de statut.  
**FR-057** — Chaque entrée indique sa provenance, sa source, son heure de survenue, son heure d'enregistrement et son niveau de visibilité.  
**FR-058** — Les entrées générées automatiquement sont idempotentes et versionnées.  
**FR-059** — Le MVP conserve les versions nécessaires à une future relecture cartographique, sans imposer l'animation complète en phase 1.

La chronologie publique ne doit pas exposer les notes internes, les motifs sensibles de modération ou les identités techniques des opérateurs. Les suppressions sont logiques : une entrée retirée du public reste disponible dans l'audit interne.

## 5.8 Panache indicatif

**FR-060** — Un panache est calculé uniquement lorsque des données de vent suffisamment récentes sont disponibles.  
**FR-061** — La période de validité et le modèle météo sont affichés.  
**FR-062** — Le panache est présenté comme indicatif et non comme une concentration mesurée.  
**FR-063** — Si le vent varie fortement, l'incertitude augmente et l'interface l'indique.  
**FR-064** — Les géométries invalides ou les résultats dépassant les garde-fous sont rejetés.  
**FR-065** — Les paramètres de calcul et la version de l'algorithme sont conservés pour reproductibilité.  
**FR-066** — Un recalcul est déclenché lors d'un nouveau run météo ou d'une évolution significative de l'événement.

## 5.9 Communes potentiellement concernées

**FR-070** — Les communes sont obtenues par intersection PostGIS entre le panache et les géométries communales.  
**FR-071** — Le résultat indique une fenêtre temporelle estimée lorsque le modèle le permet.  
**FR-072** — La liste est triée par heure estimée d'arrivée puis par niveau d'exposition indicatif.  
**FR-073** — Le terme « potentiellement concernée » est systématique.  
**FR-074** — Une commune peut être consultée directement depuis la liste.

## 5.10 Qualité de l'air

**FR-080** — Le MVP affiche au minimum PM2,5 et PM10 issus de CAMS.  
**FR-081** — La résolution du modèle et l'heure de validité sont indiquées.  
**FR-082** — Les données ne sont pas présentées comme une mesure locale lorsqu'elles proviennent d'une grille de modèle.  
**FR-083** — Une couche raster ou tuilée est proposée sur la carte.  
**FR-084** — La fiche commune indique la valeur de la cellule correspondante et sa source.  
**FR-085** — Les AASQA régionales sont prévues en phase 2 via une interface fournisseur commune.

## 5.11 Radar de précipitations

**FR-090** — La carte peut afficher la dernière image radar disponible.  
**FR-091** — Une animation courte des dernières images peut être activée si les performances le permettent.  
**FR-092** — L'horodatage de chaque frame est visible.  
**FR-093** — Les frames anciennes sont supprimées selon une politique de rétention courte.  
**FR-094** — Une panne du radar ne bloque aucune autre couche.

## 5.12 Informations officielles

**FR-100** — Chaque territoire peut définir des liens vers la préfecture, le SDIS/SIS, l'accès aux massifs, la vigilance et les organismes de qualité de l'air.  
**FR-101** — Les liens sont administrables sans déploiement.  
**FR-102** — Les liens expirés ou redirigés sont vérifiés automatiquement.  
**FR-103** — Une bannière officielle peut être publiée par un administrateur habilité, avec date de début et de fin.  
**FR-104** — Les contenus officiels sont visuellement distincts des estimations automatiques.

## 5.13 État des données

**FR-110** — Une page `/statut` présente chaque source, le dernier import réussi, la dernière donnée disponible et les incidents.  
**FR-111** — Chaque couche de la carte dispose d'un indicateur de fraîcheur.  
**FR-112** — Les erreurs détaillées restent privées ; le public reçoit un message compréhensible.  
**FR-113** — Un incident peut être créé automatiquement après plusieurs échecs consécutifs.  
**FR-114** — Une couche indisponible affiche son dernier état publiable, son horodatage et un message explicite.  
**FR-115** — Un chargement dépassant le seuil défini bascule vers un état d'erreur ou de dernier état connu ; aucun spinner ne reste indéfini.  
**FR-116** — La page événement indique séparément la fraîcheur de FIRMS, du vent, du panache, de la qualité de l'air et du radar.

## 5.14 PWA

**FR-120** — L'application est installable sur les navigateurs compatibles.  
**FR-121** — Le shell, les pages méthodologiques et la dernière vue consultée sont mis en cache de façon limitée.  
**FR-122** — Les données temps réel ne sont jamais présentées comme fraîches lorsqu'elles proviennent du cache hors ligne.  
**FR-123** — Une bannière indique clairement le mode hors connexion.  
**FR-124** — Les notifications push ne font pas partie du MVP.

# 6. Exigences non fonctionnelles

## 6.1 Disponibilité et résilience

| Indicateur | Cible MVP |
|---|---|
| Disponibilité de l'application publique | 99,5 % mensuel hors maintenance annoncée |
| Disponibilité de l'administration | 99,0 % mensuel |
| Tolérance à une source externe indisponible | Oui, sans indisponibilité globale |
| Reprise après échec d'import | Automatique avec retries et file d'échec |
| Sauvegarde base | Quotidienne au minimum |
| RPO cible | 24 heures pour le contenu ; imports rejouables |
| RTO cible | 4 heures pour le service public |

## 6.2 Performance

- LCP cible inférieur à 2,5 secondes sur une connexion mobile correcte pour la page initiale, sans attendre toutes les couches.
- Réponse API publique mise en cache : p95 inférieur à 500 ms.
- Recherche de commune : p95 inférieur à 300 ms.
- Chargement des événements dans une emprise départementale : p95 inférieur à 800 ms hors cache.
- Interaction cartographique fluide à 30 images par seconde sur un téléphone de milieu de gamme.
- Taille initiale JavaScript maîtrisée ; les bibliothèques de traitement géospatial lourd ne sont jamais embarquées côté client.

## 6.3 Scalabilité

Le système doit supporter sans changement architectural :

- tous les départements métropolitains ;
- plusieurs dizaines de milliers de détections par jour en période exceptionnelle ;
- plusieurs centaines de milliers de visites quotidiennes lors d'une crise médiatisée ;
- une forte concentration des accès sur un département ;
- le recalcul parallèle de plusieurs événements.

Les seuils de montée en charge doivent déclencher :

- passage des GeoJSON volumineux aux tuiles vectorielles ;
- partitionnement renforcé des tables temporelles ;
- augmentation horizontale des workers ;
- CDN pour les rasters, PMTiles et réponses publiques ;
- lecture depuis une réplique si nécessaire.

## 6.4 Maintenabilité

- TypeScript en mode strict.
- Python typé avec mypy ou pyright.
- Formatage automatique et lint bloquants.
- migrations SQL versionnées.
- contrats API documentés par OpenAPI.
- décisions d'architecture enregistrées sous forme d'ADR.
- aucune logique métier critique uniquement présente dans l'interface.
- algorithmes versionnés et reproductibles.

## 6.5 Accessibilité

- conformité visée au RGAA en vigueur pour les parcours principaux ;
- navigation clavier ;
- contrastes suffisants ;
- légendes non fondées uniquement sur la couleur ;
- alternatives textuelles à la carte ;
- respect de `prefers-reduced-motion` ;
- tailles tactiles adaptées ;
- lecture des dates et statuts par lecteur d'écran ;
- tableau accessible listant les événements visibles.

# 7. Architecture de l'information et routes

## 7.1 Routes publiques

| Route | Fonction |
|---|---|
| `/` | Accueil national et résumé |
| `/carte` | Carte nationale plein écran |
| `/territoire/[slug]` | Vue région, département ou collectivité |
| `/commune/[insee]` | Synthèse d'une commune |
| `/evenements/[publicId]` | Fiche d'un événement et chronologie |
| `/evenements/[publicId]?at=` | Partage d'un instant de chronologie |
| `/sources` | Sources, licences et attributions |
| `/methodologie` | Explication des détections et du panache |
| `/statut` | Santé des données |
| `/a-propos` | Présentation du projet |
| `/mentions-legales` | Mentions légales |
| `/confidentialite` | Politique de confidentialité |
| `/accessibilite` | Déclaration et contact accessibilité |

## 7.2 Routes privées

| Route | Fonction |
|---|---|
| `/admin` | Tableau de bord |
| `/admin/sources` | Santé et imports |
| `/admin/evenements` | Recherche et corrections |
| `/admin/territoires` | Configuration territoriale |
| `/admin/liens-officiels` | Gestion des liens |
| `/admin/messages` | Bannières et informations officielles |
| `/admin/utilisateurs` | Rôles administrateurs |
| `/admin/audit` | Journal des actions |

## 7.3 Structure de navigation mobile

- Carte
- Autour de moi
- Rechercher
- Couches
- Informations

La navigation secondaire et les pages légales restent dans un menu latéral.

# 8. Principes UX, cartographie et accessibilité

## 8.1 Hiérarchie de l'information

L'utilisateur doit comprendre en moins de cinq secondes :

1. le territoire affiché ;
2. la période couverte ;
3. le nombre d'événements récemment détectés ;
4. les couches actives ;
5. l'état de fraîcheur des données ;
6. le caractère non officiel et indicatif du service.

## 8.2 Système visuel recommandé

- Fond principal neutre et lisible.
- Rouge/orange réservé aux détections et phénomènes thermiques.
- Gris pour les données anciennes ou non revues.
- Bleu/violet pour qualité de l'air et météo.
- Hachures ou contour pointillé pour l'incertitude du panache.
- Symboles distincts pour détection brute et événement regroupé.

## 8.3 Carte

- MapLibre GL JS comme moteur.
- Fond IGN ou autre fond compatible, avec attribution obligatoire.
- Vue nationale simplifiée par agrégats départementaux.
- Vue locale avec points, événement, communes et panache.
- Contrôle de couches accessible.
- Barre temporelle optionnelle pour filtrer 6 h, 12 h, 24 h, 48 h et 7 jours.
- Les limites communales ne sont chargées qu'à un niveau de zoom pertinent.

## 8.4 Fiche latérale

Sur ordinateur, la sélection ouvre une fiche latérale sans masquer entièrement la carte. Sur mobile, une bottom sheet à trois états est utilisée : compacte, intermédiaire et plein écran.

## 8.5 Chronologie visuelle

La chronologie utilise une liste accessible avant toute visualisation animée. Les entrées officielles, les observations et les estimations possèdent des pictogrammes, libellés et formulations distincts. Le déplacement dans le temps ne doit jamais masquer l'horodatage réellement consulté.

## 8.6 Alternative textuelle

Une liste synchronisée avec l'emprise de la carte présente :

- nom ou identifiant de l'événement ;
- commune la plus proche ;
- dernière détection ;
- distance depuis l'utilisateur si autorisée ;
- niveau de fiabilité ;
- lien vers la fiche.

# 9. Sources de données et règles d'utilisation

## 9.1 NASA FIRMS

NASA FIRMS distribue des détections de feux actifs et anomalies thermiques provenant de MODIS et VIIRS en temps quasi réel. Les données mondiales sont généralement disponibles dans les trois heures suivant l'observation satellitaire. VIIRS fournit une résolution nominale de 375 m et MODIS une résolution nominale de 1 km. Une clé gratuite est nécessaire pour l'API et le quota standard indiqué par FIRMS est de 5 000 transactions par tranche de dix minutes. [S1][S2][S3]

Utilisation dans le MVP :

- source principale des détections thermiques ;
- import des jeux VIIRS S-NPP, NOAA-20, NOAA-21 et MODIS selon disponibilité ;
- conservation de la version NRT ;
- réconciliation possible avec les données standard ultérieures ;
- attribution NASA FIRMS visible dans l'application.

Règles :

- ne jamais déduire automatiquement qu'une détection correspond à un incendie confirmé ;
- conserver l'heure d'acquisition UTC ;
- préserver les attributs bruts ;
- afficher les limitations de couverture nuageuse, de passage satellite et de résolution.

## 9.2 Météo-France — AROME

Les données AROME sont utilisées pour extraire les composantes du vent et alimenter le panache indicatif. Les fichiers de modèle sont traités côté Python, pas dans Supabase Edge Functions. Le portail historique de données publiques est en cours de migration vers les nouveaux portails API et `meteo.data.gouv.fr`; l'intégration doit donc passer par un adaptateur afin de pouvoir changer d'endpoint sans modifier le métier. [S4][S5]

Données minimales :

- identifiant et date du run ;
- échéance ;
- composantes U/V du vent à 10 m ;
- vitesse et direction dérivées ;
- grille et projection ;
- éventuellement humidité, stabilité ou hauteur de couche limite pour une phase ultérieure.

## 9.3 Radar Météo-France

Les produits radar temps réel peuvent comporter des images individuelles à une résolution de 1 km toutes les cinq minutes selon le produit. Le pipeline doit conserver les métadonnées du produit, sa projection et son horodatage, puis produire une représentation web mise en cache. [S6]

## 9.4 Copernicus CAMS

Le jeu CAMS European air quality forecasts fournit des analyses et prévisions quotidiennes pour l'Europe. Le produit européen est proposé à environ 0,1 degré, soit approximativement 10 km, à partir d'un ensemble de systèmes de prévision. Il convient à une tendance régionale, pas à une affirmation à l'échelle d'une rue. [S7]

Données MVP :

- PM2,5 ;
- PM10 ;
- date de run ;
- heure de validité ;
- unité ;
- grille et modèle d'ensemble.

## 9.5 IGN et Géoplateforme

L'API de téléchargement de la Géoplateforme permet de découvrir et télécharger les produits administratifs, dont ADMIN EXPRESS COG. Elle est paginée et indique une limite d'usage de dix requêtes par seconde depuis une même adresse IP. Les géométries doivent être importées en processus contrôlé, versionnées et simplifiées pour le web. [S8]

Produits :

- limites régions, départements et communes ;
- codes officiels géographiques ;
- centres géographiques calculés ;
- emprises et géométries simplifiées ;
- relief réservé à la phase 2.

## 9.6 Sources territoriales

Les liens vers préfectures, SIS, accès aux massifs et AASQA sont des contenus configurés. Le MVP ne doit pas dépendre d'un scraping fragile de pages web pour fonctionner. Les données locales automatisées sont intégrées uniquement lorsqu'une API ou un flux stable existe et que les conditions de réutilisation sont documentées.

## 9.7 Registre des sources

Chaque fournisseur dispose d'un enregistrement comprenant :

- nom ;
- type ;
- URL de documentation ;
- licence ;
- attribution requise ;
- propriétaire du connecteur ;
- fréquence attendue ;
- seuil de retard ;
- politique de rétention ;
- statut actif/inactif ;
- contact technique ;
- date de dernière vérification contractuelle.

# 10. Architecture technique cible

## 10.1 Vue d'ensemble

```text
Utilisateurs web / PWA
          |
          v
Next.js + CDN + cache HTTP
          |
          +----------------------+
          |                      |
          v                      v
API publique/BFF            Supabase Auth Admin
          |                      |
          v                      v
Supabase PostgreSQL + PostGIS + Storage
          ^
          |
Service Python d'ingestion et de calcul
          |
          +--> Redis / file de tâches
          +--> Stockage fichiers GRIB, NetCDF, radar et sorties
          +--> NASA FIRMS
          +--> Météo-France
          +--> Copernicus CAMS
          +--> IGN / Géoplateforme
```

## 10.2 Composants

### Application Next.js

Responsabilités :

- rendu serveur des pages ;
- PWA ;
- interface cartographique ;
- recherche et navigation ;
- API publique stabilisée ;
- contrôle du cache ;
- administration ;
- validation des entrées ;
- génération des métadonnées SEO et partage.

### Supabase

Responsabilités :

- source de vérité relationnelle ;
- géométries PostGIS ;
- authentification administrateur ;
- Storage ;
- RLS et permissions ;
- fonctions SQL géospatiales ;
- audit ;
- tâches SQL légères ;
- événements temps réel limités à l'administration.

Supabase prend en charge PostGIS pour les requêtes géographiques, `pg_cron` pour les tâches récurrentes et Vault pour stocker des secrets chiffrés. Les tables exposées doivent être protégées par RLS et les objets accessibles par la Data API doivent cumuler grants et politiques RLS. [S9][S10][S11][S12]

### Service Python

Responsabilités :

- téléchargement et validation des sources ;
- lecture GRIB2/NetCDF/BUFR/GeoTIFF ;
- transformation de projections ;
- extraction des vents ;
- calcul de panaches ;
- regroupement d'événements ;
- intersection avec les communes ;
- production de rasters et tuiles ;
- archivage des fichiers bruts ;
- reprise et relecture des imports.

Technologies recommandées :

- Python 3.13 ou version stable validée au démarrage ;
- FastAPI ;
- Pydantic ;
- SQLAlchemy ou psycopg ;
- GeoPandas ;
- Shapely ;
- xarray ;
- rasterio ;
- GDAL ;
- ecCodes ;
- Celery avec Redis ;
- structlog ;
- OpenTelemetry.

### Redis

- file de tâches ;
- verrouillage distribué ;
- anti-duplication temporaire ;
- cache de calculs ;
- limitation de débit interne.

## 10.3 Décisions d'architecture

| ADR | Décision | Justification |
|---|---|---|
| ADR-001 | Supabase/PostGIS comme source de vérité | Géospatial, RLS, Auth et administration intégrés |
| ADR-002 | Worker Python séparé | Les formats météo et calculs lourds ne conviennent pas aux Edge Functions |
| ADR-003 | Aucun compte public au MVP | Réduit les données personnelles et la complexité |
| ADR-004 | Donnée brute immuable | Audit, reproductibilité et correction non destructive |
| ADR-005 | API publique versionnée | Évite le couplage direct du front au schéma interne |
| ADR-006 | Multi-territoires natif | Empêche la duplication par département |
| ADR-007 | Aucune confirmation automatique d'incendie | Limite le risque de désinformation |
| ADR-008 | DFCI OPS séparé | Sécurité et cloisonnement opérationnel |

# 11. Organisation du monorepo

```text
feux-de-france/
├── apps/
│   └── web/                       # Next.js public + administration
├── services/
│   └── geo-worker/                # FastAPI, Celery, imports et calculs
├── packages/
│   ├── ui/                        # composants partagés
│   ├── config/                    # eslint, typescript, tailwind
│   ├── contracts/                 # schémas Zod/OpenAPI partagés
│   ├── map-style/                 # styles, légendes, expressions MapLibre
│   └── domain/                    # types métier sans dépendance UI
├── supabase/
│   ├── migrations/
│   ├── seed/
│   ├── tests/
│   └── config.toml
├── data/
│   ├── fixtures/                  # jeux de tests non sensibles
│   └── schemas/                   # schémas fournisseurs
├── infra/
│   ├── docker/
│   ├── compose/
│   ├── terraform/                 # optionnel
│   └── monitoring/
├── docs/
│   ├── adr/
│   ├── api/
│   ├── runbooks/
│   └── algorithms/
├── scripts/
├── .github/workflows/
├── pnpm-workspace.yaml
├── turbo.json
└── README.md
```

## 11.1 Règles de dépendance

- `apps/web` peut dépendre de `packages/*` mais jamais de code Python.
- `services/geo-worker` consomme les contrats JSON/OpenAPI exportés.
- Les migrations Supabase sont l'unique moyen de modifier le schéma de production.
- Les types TypeScript de base sont générés depuis Supabase puis enrichis par le domaine.
- Les transformations fournisseur restent isolées dans `providers/`.

# 12. Architecture Supabase et PostGIS

## 12.1 Schémas PostgreSQL

| Schéma | Contenu | Exposition Data API |
|---|---|---|
| `app` | territoires, contenus, configurations | Non directe |
| `geo` | communes, géométries, index spatiaux | Non directe |
| `fire` | détections et événements | Non directe |
| `meteo` | runs, vents et sorties | Non directe |
| `air` | CAMS et qualité de l'air | Non directe |
| `radar` | métadonnées radar | Non directe |
| `ingest` | imports, fichiers et erreurs | Non |
| `admin` | profils et habilitations | Non |
| `audit` | journaux immuables | Non |
| `api` | vues et fonctions publiques stables | Oui, lecture contrôlée |

Le schéma exposé par Supabase doit être limité au strict nécessaire. Les tables brutes ne sont jamais accessibles directement aux rôles `anon` ou `authenticated`.

## 12.2 Extensions

- `postgis` ;
- `pg_cron` pour housekeeping léger ;
- `pg_net` uniquement si un appel HTTP planifié depuis la base est réellement nécessaire ;
- `vault` pour secrets internes ;
- `pg_stat_statements` pour analyse de requêtes ;
- `uuid-ossp` ou fonctions UUID natives selon version ;
- `pg_trgm` pour recherche tolérante des communes.

## 12.3 Types géographiques

- Stockage principal en `geometry` EPSG:4326 pour échanges web.
- Colonnes `geography` ou conversions ciblées pour les distances métriques.
- Index GiST sur toutes les colonnes spatiales interrogées.
- Géométries communales valides et multipolygones.
- Versions simplifiées par niveaux de zoom ou PMTiles statiques.

## 12.4 Partitionnement et rétention

- `fire.detections` partitionnée mensuellement par `acquired_at` lorsque la volumétrie le justifie.
- `ingest.import_runs` conservée 24 mois, puis agrégée.
- fichiers bruts récents conservés au minimum 30 jours ; rétention prolongée selon coût et obligations de reproductibilité.
- frames radar conservées de 6 à 24 heures dans le stockage chaud.
- statistiques agrégées conservées sans limite définie au MVP.

# 13. Modèle de données détaillé

## 13.1 `app.territories`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Identifiant interne |
| `parent_id` | uuid FK nullable | Région ou territoire parent |
| `type` | enum | country, region, department, collectivity, custom |
| `code` | text | Code officiel ou interne |
| `slug` | text unique | URL publique |
| `name` | text | Nom officiel |
| `short_name` | text nullable | Libellé court |
| `timezone` | text | Fuseau IANA |
| `geometry` | geometry(MultiPolygon,4326) | Emprise |
| `center` | geometry(Point,4326) | Centre par défaut |
| `default_zoom` | numeric | Zoom cartographique |
| `status` | enum | draft, pilot, active, disabled |
| `settings` | jsonb | Options contrôlées |
| `created_at` | timestamptz | Création |
| `updated_at` | timestamptz | Modification |

Index : `slug`, `code`, GiST sur `geometry`, index sur `parent_id` et `status`.

## 13.2 `geo.municipalities`

| Colonne | Type | Description |
|---|---|---|
| `insee_code` | text PK | Code INSEE |
| `department_code` | text | Département |
| `name` | text | Nom officiel |
| `normalized_name` | text | Recherche |
| `postal_codes` | text[] | Aide à la recherche |
| `geometry` | geometry(MultiPolygon,4326) | Limite |
| `centroid` | geometry(Point,4326) | Centre |
| `area_km2` | numeric | Surface |
| `source_version` | text | Version IGN/COG |
| `valid_from` | date | Début de validité |
| `valid_to` | date nullable | Fin de validité |

## 13.3 `ingest.data_sources`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Source |
| `key` | text unique | firms, arome, cams, radar, ign |
| `name` | text | Nom public |
| `provider` | text | Organisme |
| `expected_interval` | interval | Fréquence attendue |
| `stale_after` | interval | Seuil de retard |
| `status` | enum | active, paused, degraded, disabled |
| `documentation_url` | text | Documentation |
| `license_name` | text | Licence |
| `attribution` | text | Attribution |
| `settings` | jsonb | Configuration non secrète |

## 13.4 `ingest.import_runs`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Import |
| `source_id` | uuid FK | Source |
| `job_name` | text | Tâche |
| `started_at` | timestamptz | Début |
| `finished_at` | timestamptz nullable | Fin |
| `status` | enum | running, success, partial, failed, skipped |
| `source_data_at` | timestamptz nullable | Date des données |
| `records_read` | integer | Entrées lues |
| `records_inserted` | integer | Insertion |
| `records_updated` | integer | Mise à jour |
| `records_rejected` | integer | Rejet |
| `artifact_path` | text nullable | Fichier brut |
| `checksum` | text nullable | Intégrité |
| `error_code` | text nullable | Code stable |
| `error_summary` | text nullable | Résumé public interne |
| `metrics` | jsonb | Durées et mesures |

## 13.5 `fire.detections`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Détection |
| `provider_key` | text unique | Clé idempotente hashée |
| `source_id` | uuid FK | FIRMS |
| `sensor` | text | VIIRS/MODIS |
| `satellite` | text | S-NPP, NOAA-20, etc. |
| `product_version` | text | Version |
| `acquired_at` | timestamptz | Observation UTC |
| `imported_at` | timestamptz | Import |
| `location` | geometry(Point,4326) | Centre de pixel |
| `latitude` | double precision | Valeur brute |
| `longitude` | double precision | Valeur brute |
| `confidence_raw` | text | Valeur fournisseur |
| `confidence_score` | numeric nullable | Normalisation interne |
| `frp_mw` | numeric nullable | Fire Radiative Power |
| `brightness` | numeric nullable | Température de brillance |
| `day_night` | char(1) nullable | D/N |
| `scan_km` | numeric nullable | Taille pixel |
| `track_km` | numeric nullable | Taille pixel |
| `thermal_type` | text nullable | Type fournisseur |
| `raw_payload` | jsonb | Donnée brute |
| `known_source_id` | uuid nullable | Source thermique connue |
| `is_public` | boolean | Visibilité dérivée |

## 13.6 `fire.events`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Interne |
| `public_id` | text unique | Identifiant partageable, préfixe de marque configurable |
| `freshness_status` | enum | new, recent, not_recent, archived, hidden |
| `verification_status` | enum | satellite_detection, probable_event, publicly_reported, officially_confirmed |
| `official_control_status` | enum nullable | active, contained, controlled, extinguished ou vocabulaire configuré |
| `official_status_source_id` | uuid nullable | Source justifiant le statut officiel |
| `official_status_at` | timestamptz nullable | Date de l'information officielle |
| `first_detected_at` | timestamptz | Première observation |
| `last_detected_at` | timestamptz | Dernière observation |
| `representative_point` | geometry(Point,4326) | Position |
| `extent` | geometry(MultiPolygon,4326) nullable | Enveloppe des pixels |
| `detection_count` | integer | Compteur |
| `sensor_count` | integer | Nombre de capteurs |
| `confidence_level` | enum | low, medium, high |
| `confidence_score` | numeric | Interne 0-1 |
| `frp_max_mw` | numeric nullable | Maximum |
| `frp_median_mw` | numeric nullable | Médiane |
| `nearest_municipality_code` | text nullable | Commune proche |
| `algorithm_version` | text | Regroupement |
| `manual_state` | jsonb | Corrections séparées |
| `last_public_snapshot_at` | timestamptz nullable | Dernier snapshot publiable |
| `created_at` | timestamptz | Création |
| `updated_at` | timestamptz | Modification |

Contraintes :

- `officially_confirmed` exige une source attribuée ;
- `official_control_status` exige `official_status_source_id` et `official_status_at` ;
- les jobs automatiques n'ont pas le droit de renseigner les champs officiels ;
- les statuts officiels ne doivent pas écraser la fraîcheur satellitaire.

## 13.7 `fire.event_detections`

- `event_id` uuid FK ;
- `detection_id` uuid FK unique ;
- `attached_at` timestamptz ;
- `method` enum auto/manual ;
- `score` numeric ;
- `algorithm_version` text ;
- PK composite.

## 13.8 `fire.event_history`

Journal technique append-only de l'état complet ou différentiel de l'événement :

- `id` uuid PK ;
- `event_id` uuid FK ;
- `version_no` integer ;
- `recorded_at` timestamptz ;
- `effective_at` timestamptz ;
- `change_type` text ;
- `provenance` enum ;
- `actor_type` enum job/admin/system ;
- `actor_id` uuid nullable ;
- `source_id` uuid nullable ;
- `algorithm_version` text nullable ;
- `before_state` jsonb nullable ;
- `after_state` jsonb ;
- `reason` text nullable ;
- `is_publicly_replayable` boolean.

Le journal permet de reconstruire l'état logique d'un événement, d'expliquer une correction et de préparer une relecture temporelle.

## 13.9 `fire.event_timeline_entries`

Table dédiée à la narration temporelle publique et interne :

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Identifiant |
| `event_id` | uuid FK | Événement |
| `entry_type` | enum | detection, grouping, smoke_forecast, wind_change, official_update, editorial_correction, status_change |
| `provenance` | enum | Nature de l'information |
| `occurred_at` | timestamptz | Heure de survenue |
| `recorded_at` | timestamptz | Heure d'enregistrement |
| `title` | text | Libellé public |
| `summary` | text nullable | Résumé |
| `source_id` | uuid nullable | Source attribuée |
| `related_entity_type` | text nullable | detection, forecast, official_message… |
| `related_entity_id` | uuid nullable | Ressource liée |
| `visibility` | enum | public, internal, suppressed |
| `deduplication_key` | text unique nullable | Idempotence |
| `metadata` | jsonb | Données structurées |

## 13.10 `fire.event_aliases`

Conserve les identifiants fusionnés, séparés ou renommés et permet une redirection permanente vers l'événement canonique.

## 13.11 `fire.known_thermal_sources`

Stocke les volcans, torchères, sites industriels et autres sources récurrentes identifiées. Une correspondance marque la détection mais ne l'efface pas.

## 13.12 `meteo.model_runs`

- fournisseur ;
- modèle ;
- run time UTC ;
- domaine ;
- résolution ;
- projection ;
- échéances disponibles ;
- état d'import ;
- fichier source ;
- checksum ;
- métadonnées.

## 13.13 `meteo.wind_samples`

Table dérivée pour les points utilisés par les événements :

- modèle/run ;
- point ;
- altitude ou niveau ;
- valid_at ;
- U ;
- V ;
- vitesse ;
- direction météorologique ;
- méthode d'interpolation ;
- distance à la cellule.

La grille complète reste dans le stockage objet et n'est pas nécessairement dupliquée dans PostgreSQL.

## 13.14 `meteo.smoke_forecasts`

| Colonne | Type | Description |
|---|---|---|
| `id` | uuid PK | Prévision |
| `event_id` | uuid FK | Événement |
| `model_run_id` | uuid FK | Run météo |
| `algorithm_version` | text | Version |
| `generated_at` | timestamptz | Calcul |
| `valid_from` | timestamptz | Début |
| `valid_to` | timestamptz | Fin |
| `geometry` | geometry(MultiPolygon,4326) | Enveloppe globale |
| `centerline` | geometry(LineString,4326) | Axe indicatif |
| `confidence_level` | enum | low, medium, high |
| `parameters` | jsonb | Paramètres reproductibles |
| `quality_flags` | text[] | Alertes |
| `is_current` | boolean | Prévision publiée |

## 13.15 `meteo.smoke_steps`

Une ligne par pas temporel : temps, centre, polygone, vitesse, direction, largeur, distance et flags.

## 13.16 `meteo.affected_municipalities`

- forecast_id ;
- insee_code ;
- first_intersection_at ;
- last_intersection_at ;
- overlap_area_km2 ;
- overlap_ratio ;
- exposure_rank ;
- confidence_level.

## 13.17 `air.model_runs` et `air.grid_assets`

Métadonnées CAMS, fichiers bruts, polluant, unité, échéance, emprise, résolution, chemin de tuile ou COG et checksum.

## 13.18 `radar.frames`

- produit ;
- acquired_at ;
- imported_at ;
- projection ;
- emprise ;
- chemin du fichier brut ;
- chemin web ;
- état ;
- checksum ;
- expiration.

## 13.19 `app.official_links`

- territoire ;
- catégorie ;
- titre ;
- URL ;
- organisme ;
- ordre ;
- actif ;
- date de dernière vérification ;
- code HTTP observé ;
- notes internes.

## 13.20 `app.official_messages`

Bannières programmables avec territoire, niveau, titre, contenu, URL source, dates, état de validation et auteur.

## 13.21 `admin.profiles`

Profil lié à `auth.users`, rôle, statut, territoires autorisés, MFA exigée ou non et date de dernière activité.

## 13.22 `audit.entries`

Journal immuable : acteur, action, ressource, identifiant, valeurs avant/après, motif, IP hachée si nécessaire, user-agent réduit et timestamp.

# 14. Sécurité, rôles et politiques RLS

## 14.1 Rôles applicatifs

| Rôle | Droits |
|---|---|
| `anon` | Lecture des vues/fonctions publiques uniquement |
| `authenticated` | Aucun droit métier par défaut |
| `viewer_admin` | Consultation administration |
| `content_admin` | Liens et messages officiels |
| `data_admin` | Corrections d'événements et sources |
| `super_admin` | Gestion des rôles et configuration globale |
| `service_role` | Workers et tâches serveur, jamais côté client |

## 14.2 Principes RLS

- RLS activée sur toute table située dans un schéma exposé.
- Aucun `SELECT *` public sur les tables internes.
- Les vues publiques excluent `raw_payload`, erreurs internes et notes privées.
- Les écritures administratives utilisent des fonctions SQL contrôlées ou des endpoints serveur.
- Le rôle est lu depuis `app_metadata`, modifiable uniquement par un serveur privilégié.
- Les politiques territoriales limitent les administrateurs locaux à leurs territoires.
- Les fonctions `security definer` fixent explicitement le `search_path` et valident tous les paramètres.

## 14.3 Secrets

- Clés fournisseurs dans l'environnement du worker ou dans un gestionnaire de secrets.
- Vault peut être utilisé pour les secrets nécessaires aux fonctions PostgreSQL planifiées. [S11]
- `service_role` uniquement dans des environnements serveur.
- Rotation documentée.
- Aucun secret dans les logs, fichiers bruts, erreurs publiques ou bundle JavaScript.

## 14.4 Authentification administrateur

- authentification sans mot de passe ou SSO ;
- MFA obligatoire pour `super_admin` et recommandée pour les autres ;
- sessions courtes pour actions sensibles ;
- révocation immédiate ;
- invitations limitées aux domaines autorisés si applicable ;
- journal des connexions et élévations de rôle.

# 15. API publique et API d'administration

## 15.1 Principes

- Préfixe `/api/v1`.
- Réponses JSON GeoJSON quand pertinent.
- Validation Zod côté Next.js et Pydantic côté Python.
- Pagination par curseur, jamais par offset sur les tables volumineuses.
- Dates ISO 8601 UTC.
- Identifiants publics opaques.
- En-têtes `Cache-Control`, `ETag` et `Last-Modified`.
- Erreurs stables avec `code`, `message`, `requestId`.
- OpenAPI publié pour les endpoints non internes.

## 15.2 Endpoints publics

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/status` | Santé synthétique |
| GET | `/api/v1/sources` | Fraîcheur des sources |
| GET | `/api/v1/territories` | Liste et hiérarchie |
| GET | `/api/v1/territories/{slug}` | Détail territoire |
| GET | `/api/v1/municipalities/search?q=` | Recherche |
| GET | `/api/v1/municipalities/{insee}` | Synthèse commune |
| POST | `/api/v1/location/resolve` | Commune contenant un point |
| GET | `/api/v1/fires` | Événements par bbox/période |
| GET | `/api/v1/fires/{publicId}` | Fiche événement |
| GET | `/api/v1/fires/{publicId}/detections` | Détections membres |
| GET | `/api/v1/fires/{publicId}/timeline` | Chronologie publique |
| GET | `/api/v1/fires/{publicId}/state?at=` | État historique disponible, phase 2 ou mode préparatoire |
| GET | `/api/v1/fires/{publicId}/smoke` | Panache courant |
| GET | `/api/v1/fires/{publicId}/municipalities` | Communes concernées |
| GET | `/api/v1/air-quality` | Couche ou valeurs |
| GET | `/api/v1/radar/latest` | Frame actuelle |
| GET | `/api/v1/radar/timeline` | Frames disponibles |
| GET | `/api/v1/official-links` | Liens par territoire |

## 15.3 Exemple de réponse événement

```json
{
  "data": {
    "id": "PFF-8K4P2M",
    "freshnessStatus": "recent",
    "verificationStatus": "probable_event",
    "officialControlStatus": null,
    "firstDetectedAt": "2026-07-27T12:04:00Z",
    "lastDetectedAt": "2026-07-27T14:18:00Z",
    "location": { "type": "Point", "coordinates": [7.12, 43.75] },
    "nearestMunicipality": { "insee": "06088", "name": "Nice" },
    "detectionCount": 5,
    "sensors": ["VIIRS_NOAA20", "VIIRS_SNPP"],
    "confidence": "medium",
    "frpMw": { "median": 6.2, "max": 11.8 },
    "provenance": {
      "event": "algorithmic_inference",
      "detections": "observation"
    },
    "timeline": {
      "latestEntryAt": "2026-07-27T15:02:00Z",
      "entryCount": 8
    },
    "smoke": {
      "available": true,
      "validFrom": "2026-07-27T15:00:00Z",
      "validTo": "2026-07-27T21:00:00Z",
      "confidence": "low",
      "provenance": "model_estimate"
    }
  },
  "meta": {
    "generatedAt": "2026-07-27T15:06:22Z",
    "lastKnownSnapshotAt": "2026-07-27T15:05:30Z",
    "sources": {
      "firms": { "status": "fresh", "dataAt": "2026-07-27T14:18:00Z" },
      "weather": { "status": "fresh", "dataAt": "2026-07-27T15:00:00Z" }
    },
    "disclaimer": "Événement déduit de détections satellitaires, non équivalent à une confirmation officielle."
  }
}
```

Le préfixe d'identifiant public reste configurable tant que la marque définitive n'est pas choisie.

## 15.4 Filtres de `/fires`

- `bbox=minLon,minLat,maxLon,maxLat` obligatoire au-delà d'un seuil national ;
- `since` ;
- `until` ;
- `status` ;
- `confidence` ;
- `sensor` ;
- `territory` ;
- `include=smokeSummary` ;
- `limit` plafonné.

## 15.5 Endpoints administratifs

- fusionner deux événements ;
- séparer des détections ;
- masquer/restaurer ;
- associer une source thermique connue ;
- relancer un calcul ;
- gérer territoires et liens ;
- créer une information officielle attribuée ;
- ajouter ou corriger une entrée de chronologie ;
- modifier un statut officiel avec source obligatoire ;
- consulter un import ;
- rejouer un import ;
- acquitter un incident.

Toutes les mutations exigent un motif et créent une entrée d'audit.

# 16. Pipelines d'ingestion et d'orchestration

## 16.1 Principes communs

Chaque pipeline suit les étapes :

1. acquérir un verrou distribué ;
2. créer un `import_run` ;
3. vérifier si une nouvelle version est disponible ;
4. télécharger dans un fichier temporaire ;
5. vérifier taille, type, schéma et checksum ;
6. copier le fichier brut dans Storage ;
7. parser dans une zone de staging ;
8. valider les unités, dates et géométries ;
9. insérer/upsert de façon idempotente ;
10. déclencher les traitements dérivés ;
11. publier les métriques ;
12. clôturer l'import ;
13. libérer le verrou.

## 16.2 Politique de retry

- erreurs réseau : 5 essais avec backoff exponentiel et jitter ;
- erreur 429 : respect du `Retry-After` ;
- erreur de schéma : pas de boucle infinie, bascule en incident ;
- fichier incomplet : nouvelle tentative puis quarantaine ;
- erreur métier isolée : rejet de la ligne avec comptage ;
- erreur globale : transaction annulée.

## 16.3 FIRMS

Fréquence de polling recommandée : toutes les dix minutes, sans prétendre réduire la latence intrinsèque du satellite.

Processus :

- emprise France métropolitaine avec tampon frontalier ;
- découpage spatial si nécessaire pour maîtriser le quota ;
- récupération des capteurs configurés ;
- normalisation des champs ;
- création de la clé idempotente ;
- insertion ;
- marquage des sources thermiques connues ;
- rattachement aux événements ;
- déclenchement de recalcul si nouvel événement significatif.

## 16.4 AROME

Le worker interroge périodiquement le catalogue et importe uniquement un nouveau run complet ou suffisamment disponible.

- stockage du GRIB2 brut ;
- index des paramètres et échéances ;
- extraction à la demande autour des événements ;
- interpolation bilinéaire ou voisin le plus proche selon validation ;
- normalisation des directions ;
- garde-fous sur valeurs aberrantes ;
- recalcul des panaches concernés.

## 16.5 CAMS

- import à chaque nouveau run ;
- stockage NetCDF/GRIB ;
- extraction PM2,5 et PM10 ;
- reprojection EPSG:3857 pour tuiles si nécessaire ;
- génération de COG ou tuiles raster ;
- publication atomique de la nouvelle version ;
- conservation de la version précédente jusqu'à validation.

## 16.6 Radar

- polling aligné sur la fréquence du produit ;
- récupération de la frame ;
- conversion contrôlée ;
- génération d'une image web géoréférencée ;
- ajout à la timeline ;
- expiration automatique des anciennes frames.

## 16.7 IGN

- import manuel contrôlé ou job peu fréquent ;
- staging complet ;
- validation des codes ;
- correction `ST_MakeValid` si nécessaire ;
- comparaison avec la version précédente ;
- publication transactionnelle ;
- génération des géométries simplifiées et index de recherche.

## 16.8 Calendrier indicatif

| Tâche | Fréquence | Exécutant |
|---|---|---|
| FIRMS polling | 10 min | Celery Beat |
| Recherche nouveau run AROME | 30 min | Celery Beat |
| Recherche nouveau run CAMS | 60 min | Celery Beat |
| Radar | 5 min ou fréquence fournisseur | Celery Beat |
| Regroupement événements | après import FIRMS + rattrapage horaire | Worker |
| Recalcul panaches | événementiel + après run météo | Worker |
| Vérification liens officiels | quotidien | Worker léger |
| Purge radar | horaire | Supabase Cron ou worker |
| Agrégation métriques | quotidien | SQL/worker |
| Sauvegarde applicative complémentaire | quotidien | Infrastructure |

# 17. Détection, dédoublonnage et regroupement des événements

## 17.1 Dédoublonnage

La clé fournisseur est un hash stable de : fournisseur, produit, satellite, capteur, date/heure d'acquisition, latitude, longitude et version pertinente. L'upsert ne modifie que les champs enrichis autorisés et conserve le payload initial.

## 17.2 Rattachement automatique

Algorithme MVP déterministe :

1. sélectionner les événements non archivés dont la dernière détection est suffisamment récente ;
2. calculer la distance entre la nouvelle détection et l'emprise/centre de chaque événement ;
3. appliquer une fenêtre spatiale dépendant du capteur et du délai ;
4. calculer un score combinant distance, temps, continuité et capteurs ;
5. rattacher à l'événement ayant le meilleur score au-dessus d'un seuil ;
6. sinon créer un nouvel événement ;
7. recalculer les agrégats ;
8. détecter les événements candidats à une fusion, sans fusion irréversible silencieuse.

Paramètres initiaux à valider sur données historiques :

- distance de base : 2 à 3 km ;
- extension temporelle : +0,5 km par heure, plafonnée ;
- fenêtre de rattachement : 18 à 24 heures ;
- seuil de fusion : centres proches et enveloppes compatibles ;
- seuil de séparation automatique : non inclus au MVP, séparation manuelle.

## 17.3 Score de fiabilité

Composantes possibles :

- confiance fournisseur ;
- répétition sur plusieurs passages ;
- présence de plusieurs capteurs ;
- FRP cohérente ;
- distance à une source thermique connue ;
- persistance temporelle ;
- cohérence spatiale.

Le score interne 0-1 n'est pas affiché directement. Les seuils publics sont versionnés et expliqués.

## 17.4 Dimensions de statut

### Fraîcheur technique

- `new` : événement créé récemment ;
- `recent` : observation dans la fenêtre récente ;
- `not_recent` : aucune nouvelle observation, sans conclusion sur l'extinction ;
- `archived` : hors fenêtre d'affichage courant ;
- `hidden` : exclu de la carte publique avec motif administratif.

### Niveau de vérification

- `satellite_detection` : une ou plusieurs anomalies thermiques, sans regroupement suffisamment robuste ;
- `probable_event` : regroupement algorithmique cohérent ;
- `publicly_reported` : événement mentionné par une source externe identifiable, non nécessairement officielle ;
- `officially_confirmed` : information publiée par une autorité ou un organisme habilité et attribuée dans la base.

### Statut officiel éventuel

Les termes `active`, `contained`, `controlled` ou `extinguished` ne sont renseignés que si le vocabulaire et la source officielle le permettent. Ils peuvent coexister avec une fraîcheur satellitaire différente. Une nouvelle détection ultérieure ne modifie pas silencieusement un statut officiel : elle génère une alerte de cohérence pour revue.

## 17.5 Règles de transition

- les jobs automatiques modifient uniquement la fraîcheur, le regroupement et la fiabilité ;
- le passage à `publicly_reported` peut être effectué par un administrateur avec source ;
- le passage à `officially_confirmed` exige une source officielle, un horodatage et un auteur ;
- toute régression ou contradiction crée une entrée d'audit ;
- les transitions interdites sont bloquées en base et dans l'API.

## 17.6 Génération de la chronologie

Une entrée est créée lors de :

- la première détection ;
- l'arrivée d'un nouveau capteur ou d'un groupe significatif de détections ;
- la fusion ou séparation d'événements ;
- la publication d'un nouveau panache significativement différent ;
- une variation de vent dépassant les seuils configurés ;
- l'ajout d'une information officielle ;
- une correction éditoriale publique ;
- un changement de niveau de vérification ou de statut officiel.

Les événements techniques répétitifs sont agrégés pour ne pas saturer la chronologie. Les clés de déduplication et versions d'algorithme rendent la génération rejouable.

## 17.7 Corrections

Les corrections sont des surcouches :

- un événement masqué reste conservé ;
- une fusion conserve les identifiants historiques et une redirection ;
- une séparation conserve les liens aux détections ;
- une source connue est une classification, pas une suppression ;
- une correction éditoriale ne modifie jamais le payload brut ;
- tout changement est réversible et audité ;
- une correction publique produit une entrée de chronologie portant la provenance `editorial_correction`.

# 18. Modèle simplifié de panache de fumée

## 18.1 Positionnement

Le MVP ne vise pas un modèle atmosphérique réglementaire. Il produit une enveloppe géographique indicative, utile à la compréhension générale de la direction probable de transport. Le relief, la convection, les brises locales, l'injection verticale et la chimie atmosphérique ne sont pas intégralement modélisés.

## 18.2 Entrées

- point représentatif de l'événement ;
- date/heure de dernière détection ;
- FRP agrégée si disponible ;
- vent AROME par pas de temps ;
- horizon de 6 heures par défaut, configurable jusqu'à 12 heures ;
- pas de 15 minutes ;
- coefficients d'advection et d'élargissement ;
- garde-fous de distance et de vitesse.

## 18.3 Algorithme MVP

Pour chaque pas temporel :

1. interpoler U/V au point courant et à l'échéance ;
2. calculer la vitesse et la direction aval ;
3. avancer le centre selon `distance = vitesse × durée × coefficient_advection` ;
4. calculer une largeur latérale croissante ;
5. produire une ellipse ou un secteur autour du segment ;
6. accumuler les polygones ;
7. simplifier et valider la géométrie ;
8. calculer une enveloppe globale et une ligne centrale ;
9. intersecter chaque pas avec les communes.

Forme indicative :

```text
largeur(distance) = largeur_initiale + distance × tan(angle_dispersion / 2)
```

Les coefficients sont des paramètres versionnés et doivent être calibrés sur des cas connus, sans être présentés comme une loi physique universelle.

## 18.4 Incertitude

Le niveau de confiance diminue lorsque :

- le modèle météo est ancien ;
- la détection est ancienne ;
- le vent est faible ou change fréquemment de direction ;
- le point se situe dans un relief complexe ;
- l'événement ne comporte qu'une détection faible ;
- l'interpolation est éloignée d'une cellule valide.

## 18.5 Garde-fous

- vitesse négative ou aberrante rejetée ;
- distance maximale par horizon ;
- surface maximale ;
- géométrie `ST_IsValid` obligatoire ;
- résultat vide si les entrées sont insuffisantes ;
- pas de panache publié avec un modèle expiré ;
- journal de calcul complet ;
- possibilité de désactivation globale immédiate.

## 18.6 Versionnement

Chaque prévision conserve :

- version de l'algorithme ;
- commit Git du worker ;
- run météo ;
- paramètres ;
- détections sources ;
- date de calcul ;
- qualité et flags ;
- checksum des entrées principales.

# 19. Qualité de l'air et radar

## 19.1 Stratégie raster

Les grilles CAMS et images radar ne doivent pas être envoyées en JSON brut au navigateur. Elles sont converties en :

- Cloud Optimized GeoTIFF pour archivage et traitement ;
- tuiles raster web ou service de tuiles ;
- métadonnées JSON légères ;
- palette et légende versionnées.

## 19.2 Consultation ponctuelle

La fiche commune peut obtenir une valeur par échantillonnage serveur du raster correspondant. La réponse indique :

- valeur ;
- unité ;
- polluant ;
- heure de validité ;
- résolution ;
- méthode d'échantillonnage ;
- source ;
- avertissement « donnée modélisée ».

## 19.3 Animation radar

- maximum 12 à 24 frames côté client ;
- préchargement progressif ;
- animation désactivable ;
- respect de la réduction des animations ;
- bouton lecture/pause et heure courante ;
- expiration des URLs de cache maîtrisée.

# 20. Administration et supervision éditoriale

## 20.1 Tableau de bord

Widgets :

- statut des sources ;
- imports échoués ;
- retard maximal ;
- événements récents ;
- événements à faible fiabilité très consultés ;
- liens officiels en erreur ;
- stockage et files de tâches ;
- incidents ouverts.

## 20.2 Gestion des événements

Fonctions :

- recherche par identifiant, date, commune et bbox ;
- vue des détections membres ;
- comparaison avant/après fusion ;
- séparation par sélection ;
- masquage motivé ;
- association à une source thermique connue ;
- note interne ;
- recalcul du panache ;
- aperçu public avant publication ;
- consultation et édition contrôlée de la chronologie ;
- workflow de statut officiel avec source obligatoire ;
- visualisation des contradictions entre observation et information officielle.

## 20.3 Gestion territoriale

- activer/désactiver un territoire ;
- définir le centre et le zoom ;
- choisir les liens et organismes ;
- définir le fuseau ;
- personnaliser les avertissements locaux ;
- configurer un tampon frontalier ;
- ajouter Monaco ou zones transfrontalières comme territoires personnalisés.

## 20.4 Publication de messages

Une information officielle doit comporter : organisme, titre, contenu, URL source, territoire ou événement, date de publication, période de validité, niveau, validateur et statut. L'interface ne doit pas permettre de faire passer une note du Projet MapFeux pour un message d'autorité.

La provenance `official_information` n'est disponible qu'aux rôles habilités. Le contenu reste attribué à son organisme d'origine et ne peut pas être réécrit de manière à modifier son sens.

# 21. Performance cartographique et stratégie de cache

## 21.1 Données statiques

- limites administratives simplifiées en PMTiles ou tuiles vectorielles statiques ;
- styles et sprites versionnés ;
- cache CDN long avec hash de contenu ;
- mise à jour atomique lors d'une nouvelle version IGN.

## 21.2 Données dynamiques

- événements retournés par bbox et période ;
- clustering MapLibre côté client pour volumes modérés ;
- agrégats serveur par département à l'échelle nationale ;
- panaches simplifiés selon le zoom ;
- `ETag` fondé sur la dernière mise à jour pertinente ;
- cache court de 30 secondes à 5 minutes selon endpoint.

## 21.3 Stratégie de zoom

| Zoom | Données |
|---|---|
| 4-6 | Agrégats départementaux, pas de communes |
| 7-9 | Événements regroupés et départements |
| 10-12 | Événements, panaches, communes concernées |
| 13+ | Détections brutes et détails locaux |

## 21.4 Limites de requêtes

- bbox maximale ;
- nombre maximal d'événements ;
- simplification automatique ;
- timeout serveur ;
- annulation des requêtes lors du déplacement de carte ;
- rate limiting sur endpoints coûteux et administration.

## 21.5 Snapshots publics et mode dégradé

Le système maintient un snapshot public léger par événement actif. Il contient les champs nécessaires au rendu serveur de la fiche, sans dépendre des couches cartographiques lourdes.

Règles :

- publication atomique après validation des données ;
- conservation du dernier snapshot valide lorsqu'un recalcul échoue ;
- horodatage `generated_at`, `data_at` et âge calculé côté interface ;
- bannière explicite lorsque le snapshot est ancien ou qu'une source est indisponible ;
- aucun retour silencieux vers une donnée en cache présentée comme actuelle ;
- timeout de chargement des couches interactives et bascule vers un message actionnable.

# 22. Sécurité applicative, confidentialité et conformité

## 22.1 Données personnelles

Le MVP collecte le minimum :

- comptes administrateurs ;
- journaux techniques ;
- géolocalisation uniquement en mémoire côté utilisateur, sauf action explicite nécessitant une requête ponctuelle ;
- aucune création de compte public ;
- aucune liste de favoris ou notification.

La CNIL recommande d'intégrer la protection de la vie privée dès la conception et de limiter les permissions, notamment la géolocalisation. [S13][S14]

## 22.2 Géolocalisation

- permission demandée uniquement après action ;
- finalité expliquée ;
- précision réduite lorsque suffisante ;
- coordonnées non écrites dans les logs applicatifs ;
- résolution de commune effectuée puis coordonnées supprimées ;
- bouton pour effacer le point affiché.

## 22.3 Analytics

Préférence pour une solution sans cookies ou strictement nécessaire. Si des traceurs soumis à consentement sont ajoutés, le refus doit être aussi simple que l'acceptation. [S15]

## 22.4 Sécurité web

- CSP restrictive ;
- HTTPS et HSTS ;
- protection CSRF sur mutations ;
- validation stricte ;
- limitation de débit ;
- headers de sécurité ;
- dépendances scannées ;
- secrets isolés ;
- prévention SSRF dans les vérificateurs d'URL ;
- uploads administratifs limités et analysés ;
- protection contre injection SQL via requêtes paramétrées ;
- revue des fonctions `security definer`.

## 22.5 Formulations obligatoires

À proximité de la carte :

> Les points affichés sont des détections thermiques satellitaires. Ils peuvent correspondre à un incendie, mais aussi à une autre source de chaleur. Un feu récent peut ne pas encore être détecté. Consultez les informations officielles des autorités.

Sur le panache :

> Projection indicative calculée à partir des données de vent disponibles. Elle ne tient pas complètement compte du relief, des brises locales, de la convection et de la hauteur réelle des fumées.

# 23. Observabilité et exploitation

## 23.1 Logs

Format JSON structuré avec :

- timestamp UTC ;
- service ;
- environnement ;
- niveau ;
- request/job ID ;
- source ;
- import ID ;
- durée ;
- résultat ;
- code d'erreur stable.

Aucune clé, payload sensible ou coordonnée utilisateur ne doit être journalisé.

## 23.2 Métriques

- disponibilité web/API ;
- latence p50/p95/p99 ;
- taux d'erreur ;
- files en attente ;
- durée des jobs ;
- dernier succès par source ;
- retard de donnée ;
- nombre de détections importées/rejetées ;
- panaches calculés/échoués ;
- taille base et stockage ;
- cache hit ratio ;
- âge du dernier snapshot public par événement ;
- nombre d'événements sans provenance complète ;
- transitions de statut officiel rejetées.

Supabase expose des métriques compatibles avec des collecteurs de type Prometheus selon son offre et sa configuration. [S16]

## 23.3 Alertes

- application publique indisponible ;
- source en retard ;
- plusieurs imports échoués ;
- quota FIRMS proche de la limite ;
- file de tâches bloquée ;
- absence de nouveau run météo au-delà du seuil ;
- erreurs 5xx supérieures au seuil ;
- stockage proche de la limite ;
- échec de sauvegarde.

## 23.4 Runbooks

Documents obligatoires :

- FIRMS indisponible ;
- modèle météo incomplet ;
- panache aberrant ;
- fausse détection médiatisée ;
- compromission d'un compte admin ;
- rollback d'une migration ;
- saturation du trafic ;
- purge d'une clé fournisseur ;
- restauration Supabase ;
- désactivation d'urgence d'une couche ;
- chronologie incohérente ou dupliquée ;
- statut officiel sans source valide ;
- page bloquée sur un chargement ou snapshot trop ancien.

# 24. Stratégie de tests et recette

## 24.1 Tests unitaires

- normalisation FIRMS ;
- génération des clés idempotentes ;
- calcul U/V vers vitesse/direction ;
- score de rattachement ;
- transitions de statuts et contraintes de source ;
- génération et déduplication des entrées de chronologie ;
- cycle de vie ;
- simplification de géométries ;
- calcul des fenêtres temporelles ;
- validation des paramètres ;
- formatage des dates et fuseaux.

## 24.2 Tests de base de données

- migrations depuis une base vide ;
- rollback ou stratégie de correction ;
- contraintes et unicité ;
- RLS pour chaque rôle ;
- accès interdit aux tables brutes ;
- performance des index ;
- fonctions PostGIS ;
- audit append-only.

## 24.3 Tests géospatiaux

Jeux de référence :

- commune avec enclave ;
- Corse et multipolygones ;
- frontière maritime ;
- point exactement sur une limite ;
- géométrie panache traversant plusieurs départements ;
- passage du méridien non pertinent mais test de robustesse ;
- géométrie invalide ;
- événement proche de Monaco/Italie.

## 24.4 Tests de contrats fournisseurs

- fixtures anonymisées ou publiques ;
- détection de changement de colonnes ;
- unité inattendue ;
- fichier vide ;
- compression incorrecte ;
- timeout et 429 ;
- run partiel ;
- données dans le futur ou très anciennes.

## 24.5 Tests E2E Playwright

- ouvrir la carte ;
- sélectionner le 06 ;
- rechercher Nice ;
- ouvrir un événement ;
- activer le panache ;
- consulter les communes ;
- refuser la géolocalisation ;
- utiliser le clavier ;
- passer hors ligne ;
- afficher la page statut ;
- administrateur masque puis restaure un événement.

## 24.6 Tests de performance

- vue nationale pendant un pic ;
- bbox dense ;
- 10 000 points ;
- calcul simultané de 100 panaches ;
- import FIRMS volumineux ;
- cache froid et chaud ;
- montée horizontale des workers.

## 24.7 Tests de sécurité

- accès anon aux schémas internes ;
- élévation de rôle ;
- IDOR ;
- injection ;
- SSRF ;
- CSRF ;
- XSS dans messages officiels ;
- fuite de `service_role` ;
- politiques Storage ;
- dépendances vulnérables.

## 24.8 Recette métier

La recette doit être réalisée sur plusieurs situations historiques connues :

- événement isolé ;
- grand feu avec multiples détections ;
- faux positif industriel ;
- zone montagneuse ;
- zone littorale ;
- vent faible ;
- changement de direction ;
- source externe indisponible.

# 25. Environnements, CI/CD et déploiement

## 25.1 Environnements

| Environnement | Usage |
|---|---|
| Local | Supabase CLI, services Docker, fixtures |
| Development | Intégration continue, données limitées |
| Staging | Copie fonctionnelle, tests et recette |
| Production | Données réelles et accès public |

Aucune donnée de production sensible ne doit être copiée sans procédure. Les données FIRMS étant publiques, un échantillon peut être utilisé, mais les comptes admin et journaux doivent être anonymisés.

## 25.2 CI

À chaque pull request :

- installation verrouillée ;
- lint ;
- typecheck ;
- tests unitaires ;
- tests Python ;
- tests migrations Supabase ;
- vérification RLS ;
- build Next.js ;
- build images Docker ;
- scan sécurité ;
- aperçu de déploiement.

## 25.3 CD

- déploiement staging automatique après merge ;
- migrations appliquées avant code compatible selon stratégie expand/contract ;
- validation manuelle production ;
- déploiement progressif du worker ;
- smoke tests ;
- rollback applicatif rapide ;
- migrations destructives interdites dans la même release que leur retrait applicatif.

## 25.4 Hébergement recommandé

- Next.js sur Vercel ou plateforme équivalente avec CDN ;
- Supabase managé dans une région européenne ;
- worker Python, Redis et services de tuiles sur VPS/conteneurs en Europe ;
- Storage Supabase ou objet compatible S3 selon volume ;
- DNS et protection DDoS via un fournisseur CDN.

## 25.5 Sauvegardes

- sauvegardes Supabase selon plan ;
- export régulier des migrations et configurations ;
- copie des fichiers critiques ;
- test de restauration trimestriel ;
- procédure de reconstruction complète depuis code, migrations et archives.

# 26. Roadmap de réalisation

## 26.1 Hypothèses

Estimation pour une petite équipe :

- 1 développeur full-stack principal ;
- 1 développeur/ingénieur Python géospatial à temps significatif ;
- UX/UI et recette métier ponctuelles ;
- 17 à 21 semaines pour un MVP national robuste incluant fiche événement, chronologie textuelle et mode dégradé.

Pour un développement principalement solo, prévoir plutôt 30 à 42 semaines selon disponibilité et expertise géospatiale.

## 26.2 Lots

| Lot | Durée indicative | Livrable |
|---|---:|---|
| 0. Cadrage et identité | 1 semaine | ADR, maquettes basses, conventions |
| 1. Fondations monorepo/Supabase | 2 semaines | CI, Auth admin, schémas initiaux |
| 2. Territoires et carte | 2 semaines | France, départements, communes, recherche |
| 3. FIRMS | 2 semaines | Import, détections, carte |
| 4. Événements | 2 à 3 semaines | Regroupement, statuts, fiches, chronologie, admin |
| 5. AROME et panache | 3 à 4 semaines | Worker météo, calcul, communes |
| 6. CAMS et radar | 2 à 3 semaines | Couches et métadonnées |
| 7. PWA, accessibilité et contenus | 2 semaines | Parcours public finalisé |
| 8. Supervision, sécurité et recette | 2 à 3 semaines | Monitoring, tests, lancement pilote |

## 26.3 Jalons

### Jalon A — Carte territoriale

France, départements, communes et recherche sans données temps réel.

### Jalon B — Détections FIRMS

Import et visualisation fiable sur le 06 et le 83.

### Jalon C — Événements

Regroupement, provenance, chronologie et administration validés sur des cas historiques.

### Jalon D — Panache indicatif

Calcul reproductible, avertissements et communes concernées.

### Jalon E — MVP pilote

CAMS, radar, statut, pages légales, PWA et supervision.

### Jalon F — Ouverture nationale

Tests de charge, revue sécurité, généralisation et communication.

# 27. Backlog initial par epic

## EPIC-01 — Fondations

- Initialiser pnpm/Turborepo.
- Créer Next.js et design system.
- Configurer Supabase local.
- Créer le worker Python.
- Configurer Docker Compose.
- Mettre en place CI et qualité.
- Écrire ADR-001 à ADR-008.

## EPIC-02 — Territoires

- Importer régions et départements.
- Importer communes.
- Normaliser noms et recherche trigramme.
- Créer sélecteur.
- Créer page territoire.
- Créer résolution point-vers-commune.
- Générer PMTiles administratives.

## EPIC-03 — FIRMS

- Obtenir et sécuriser la clé.
- Implémenter client avec quota.
- Stocker fichiers bruts.
- Parser capteurs.
- Idempotence.
- Affichage des détections.
- Légende et avertissements.
- Page source et statut.

## EPIC-04 — Événements

- Modèle événement.
- Algorithme de rattachement.
- Score de fiabilité.
- Fraîcheur, vérification et statut officiel séparés.
- Provenance des informations.
- Fiche événement rendue côté serveur.
- Chronologie textuelle.
- Fusion/séparation admin.
- Historique, snapshots et audit.

## EPIC-05 — Météo

- Connecteur catalogue AROME.
- Téléchargement GRIB2.
- Extraction U/V.
- Stockage des runs.
- API vent ponctuel.
- Gestion de fraîcheur.

## EPIC-06 — Panache

- Version 1 de l'algorithme.
- Tests géospatiaux.
- Géométries par pas.
- Intersection communes.
- Score d'incertitude.
- Rendu MapLibre.
- Documentation méthodologique.

## EPIC-07 — CAMS

- Client ADS/STAC ou API officielle.
- Import PM2,5/PM10.
- Tuiles raster.
- Valeur par commune.
- Légendes.

## EPIC-08 — Radar

- Connecteur Météo-France.
- Conversion produit.
- Timeline.
- Animation.
- Rétention et cache.

## EPIC-09 — Administration

- Auth et MFA.
- Dashboard santé.
- Gestion territoires/liens.
- Corrections événements.
- Workflow d'information officielle attribuée.
- Gestion de la chronologie.
- Contrôle des transitions de statut.
- Audit.

## EPIC-10 — Qualité et lancement

- Accessibilité.
- PWA.
- Tests E2E.
- Tests de charge.
- Pentest ciblé.
- Runbooks.
- Tests du mode dégradé et des snapshots.
- Mentions et confidentialité.
- Pilote 06/83.

# 28. Critères d'acceptation et Definition of Done

## 28.1 Critères de lancement MVP

- Les départements et communes métropolitaines sont consultables.
- Les imports FIRMS fonctionnent 7 jours consécutifs sans intervention manuelle critique.
- Aucun doublon significatif n'est créé lors du rejeu d'un import.
- Le regroupement est validé sur un corpus historique.
- Chaque événement affiche des sources, provenances et heures exactes.
- Une détection satellitaire n'est jamais présentée comme une confirmation officielle.
- Aucun statut officiel ne peut être enregistré sans source et date.
- La fiche événement fournit une chronologie textuelle accessible.
- Le panache est désactivé lorsque les données météo sont insuffisantes.
- Les communes concernées sont reproductibles pour une même version d'entrée.
- CAMS et radar peuvent tomber en panne sans affecter la carte FIRMS.
- Une indisponibilité FIRMS ou météo laisse visible le dernier snapshot avec son âge exact.
- Aucun écran principal ne reste en chargement indéfini.
- La page statut reflète les retards.
- Les tables internes ne sont pas accessibles au rôle anonyme.
- Aucun secret n'est présent dans le bundle ou les logs.
- Les parcours principaux sont utilisables au clavier et sur mobile.
- Les pages méthodologie, sources, confidentialité et mentions sont publiées.
- Une procédure de retrait d'urgence d'une couche est testée.
- La sauvegarde et la restauration ont été vérifiées.

## 28.2 Definition of Done d'une user story

- critères fonctionnels validés ;
- tests unitaires pertinents ;
- tests d'intégration si base ou fournisseur ;
- accessibilité vérifiée ;
- logs et métriques ajoutés ;
- documentation mise à jour ;
- migration réversible ou procédure de correction ;
- revue de sécurité ;
- traduction des erreurs en message utilisateur ;
- aucune régression E2E ;
- validation métier pour toute formulation publique ;
- provenance et impact chronologique évalués pour toute donnée exposée.

# 29. Risques, limites et plans de réduction

| Risque | Impact | Probabilité | Réduction |
|---|---|---:|---|
| Détection interprétée comme confirmation | Élevé | Élevée | Statuts séparés, provenance, terminologie, avertissements, liens officiels |
| Terme « opérationnel » ou statut ambigu | Élevé | Moyenne | Vocabulaire contrôlé et attribution obligatoire |
| Perte de l'historique lors d'une correction | Élevé | Moyenne | Journal append-only, snapshots et tests de reconstruction |
| Latence satellite | Élevé | Certaine | Afficher acquisition et expliquer les passages |
| Faux positifs | Moyen/élevé | Moyenne | Sources connues, score, corrections auditables |
| Changement API Météo-France | Moyen | Élevée | Adaptateur fournisseur et tests de contrat |
| Quota FIRMS | Moyen | Moyenne | Découpage, cache, contrôle des transactions |
| Relief du 06 | Élevé pour panache | Élevée | Incertitude forte, limitation MVP, phase 2 |
| Volumétrie lors d'une crise | Élevé | Moyenne | CDN, bbox, agrégats, tests de charge |
| Indisponibilité d'une source | Moyen | Élevée | Pipelines indépendants, snapshots, timeout et dégradation explicite |
| Coût rasters/stockage | Moyen | Moyenne | Rétention, COG, tuiles et archivage |
| Action admin erronée | Moyen | Moyenne | Aperçu, audit, réversibilité, rôles |
| Fuite d'une clé | Élevé | Faible/moyenne | Vault, rotation, scans, serveur uniquement |
| Couplage futur avec DFCI OPS | Très élevé | À venir | Projets séparés et passerelle filtrée |

# 30. Préparation des phases 2 et 3

## 30.1 Préparation phase 2

Le MVP doit prévoir des interfaces fournisseur génériques :

```text
AirQualityProvider
WeatherProvider
RadarProvider
AdministrativeBoundaryProvider
OfficialInformationProvider
```

Les tables acceptent plusieurs modèles et plusieurs sources pour une même échéance. Les algorithmes enregistrent leur version. Les géométries de relief ne sont pas nécessaires au MVP mais le service Python doit pouvoir intégrer un MNT ultérieurement.

La relecture phase 2 s'appuie sur les éléments déjà présents en phase 1 : `event_history`, `event_timeline_entries`, versions de panaches, runs météo et snapshots. L'API doit accepter à terme un paramètre `at` sans modifier le contrat de la fiche courante. Les règles de rétention doivent conserver les états significatifs même lorsque les données raster intermédiaires sont purgées.

## 30.2 Préparation phase 3

Aucune table `operations`, `resources`, `personnel` ou `sitac` n'est créée dans Projet MapFeux. Une future passerelle doit consommer une API publique ou partenaire explicite, jamais lire directement la base publique avec des privilèges élevés.

Flux potentiellement autorisés vers DFCI OPS :

- détections FIRMS ;
- panaches publics ;
- modèles météo ;
- qualité de l'air ;
- radar ;
- état des sources.

Flux vers Projet MapFeux : aucun par défaut. Une publication officielle éventuelle devra passer par un workflow humain et une API de contenu séparée.

# 31. Annexes techniques

## Annexe A — Exemple SQL simplifié

```sql
create extension if not exists postgis;
create extension if not exists pg_trgm;

create schema if not exists fire;
create schema if not exists api;

create table fire.detections (
  id uuid primary key default gen_random_uuid(),
  provider_key text not null unique,
  sensor text not null,
  satellite text not null,
  acquired_at timestamptz not null,
  imported_at timestamptz not null default now(),
  location geometry(Point, 4326) not null,
  confidence_score numeric,
  frp_mw numeric,
  raw_payload jsonb not null,
  is_public boolean not null default true
);

create index detections_acquired_at_idx
  on fire.detections (acquired_at desc);

create index detections_location_gix
  on fire.detections using gist (location);

revoke all on fire.detections from anon, authenticated;
```

## Annexe B — Fonction de recherche spatiale indicative

```sql
create or replace function api.resolve_municipality(lon double precision, lat double precision)
returns table (
  insee_code text,
  name text,
  department_code text
)
language sql
stable
security definer
set search_path = geo, pg_temp
as $$
  select m.insee_code, m.name, m.department_code
  from geo.municipalities m
  where st_covers(
    m.geometry,
    st_setsrid(st_makepoint(lon, lat), 4326)
  )
  limit 1;
$$;
```

La fonction réelle doit limiter les plages de coordonnées, contrôler les grants et être testée contre les frontières.

## Annexe C — Variables d'environnement

### Web

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` côté serveur uniquement
- `PUBLIC_APP_URL`
- `MAP_STYLE_URL`
- `SENTRY_DSN`
- `API_CACHE_SECRET`

### Worker

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET_RAW`
- `SUPABASE_STORAGE_BUCKET_DERIVED`
- `FIRMS_MAP_KEY`
- `METEOFRANCE_API_KEY` si requise
- `COPERNICUS_URL`
- `COPERNICUS_KEY` ou identifiants adaptés
- `REDIS_URL`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `SENTRY_DSN`

## Annexe D — Conventions de statut et provenance

### Fraîcheur source

- `fresh` : dans l'intervalle attendu ;
- `delayed` : seuil dépassé ;
- `stale` : donnée trop ancienne pour publication normale ;
- `unavailable` : source en échec ;
- `maintenance` : arrêt connu.

### Fraîcheur événement

- `new` : nouvel événement ;
- `recent` : observation récente ;
- `not_recent` : pas d'observation récente, sans conclusion opérationnelle ;
- `archived` : hors fenêtre courante ;
- `hidden` : masqué avec motif.

### Vérification événement

- `satellite_detection` : observation thermique seule ;
- `probable_event` : regroupement algorithmique cohérent ;
- `publicly_reported` : mention externe attribuée ;
- `officially_confirmed` : confirmation attribuée à une autorité.

### Statut officiel

- nullable par défaut ;
- valeurs configurées et traduites selon le vocabulaire officiel retenu ;
- source, date et administrateur obligatoires ;
- aucune transition automatique.

### Provenance

- `observation` : donnée instrumentale ou mesure ;
- `algorithmic_inference` : regroupement, classification ou score calculé ;
- `model_estimate` : prévision ou simulation ;
- `official_information` : publication attribuée à une autorité ;
- `editorial_correction` : correction ou contextualisation par l'équipe ;
- `external_report` : source publique externe non officielle.

### Fiabilité événement

- faible : une seule détection ou données fragiles ;
- modérée : répétition ou confiance correcte ;
- élevée : plusieurs détections cohérentes et/ou plusieurs capteurs.

Ces libellés ne qualifient ni la gravité, ni la surface, ni l'état opérationnel du feu.

## Annexe E — Codes d'erreur API

| Code | Sens |
|---|---|
| `INVALID_BBOX` | Emprise invalide |
| `BBOX_TOO_LARGE` | Vue trop large pour cet endpoint |
| `NOT_FOUND` | Ressource absente |
| `SOURCE_DELAYED` | Donnée disponible mais retardée |
| `SOURCE_UNAVAILABLE` | Source indisponible |
| `FORECAST_NOT_AVAILABLE` | Pas de panache publiable |
| `RATE_LIMITED` | Limite atteinte |
| `FORBIDDEN` | Droit insuffisant |
| `VALIDATION_ERROR` | Paramètres invalides |
| `INTERNAL_ERROR` | Erreur interne avec requestId |

## Annexe F — Registre minimal des ADR

- ADR-001 : choix Supabase/PostGIS ;
- ADR-002 : worker Python séparé ;
- ADR-003 : schémas internes non exposés ;
- ADR-004 : données brutes immuables ;
- ADR-005 : stratégie cartographique ;
- ADR-006 : algorithme de regroupement ;
- ADR-007 : modèle de panache MVP ;
- ADR-008 : séparation DFCI OPS ;
- ADR-009 : stratégie de cache ;
- ADR-010 : politique de rétention ;
- ADR-011 : dimensions de statut et transitions autorisées ;
- ADR-012 : provenance et chronologie ;
- ADR-013 : snapshots publics et mode dégradé.

## Annexe G — Checklist avant mise en production

- [ ] Domaine, DNS, TLS et redirections validés.
- [ ] Attributions des fonds et données visibles.
- [ ] Clés API de production distinctes.
- [ ] RLS testée avec `anon`, `authenticated` et admin.
- [ ] `service_role` absent du client.
- [ ] Sauvegarde et restauration testées.
- [ ] Page statut opérationnelle.
- [ ] Fiche événement rendue côté serveur avec dernier snapshot.
- [ ] Aucun chargement principal indéfini.
- [ ] Alertes configurées.
- [ ] Limites et avertissements validés métier.
- [ ] Statuts de vérification et provenance visibles.
- [ ] Statuts officiels impossibles sans source et date.
- [ ] Chronologie testée sur fusion, séparation et correction.
- [ ] Accessibilité des parcours principaux vérifiée.
- [ ] Test de charge réussi.
- [ ] Runbook fausse détection prêt.
- [ ] Désactivation d'urgence des panaches testée.
- [ ] Liens officiels 06 et 83 vérifiés.
- [ ] Politique de confidentialité publiée.
- [ ] Contact de signalement public disponible.

## Annexe H — Journal des évolutions 1.1

La version 1.1 consolide la version 1.0 sans remettre en cause son architecture générale.

Principales évolutions :

- utilisation de « Projet MapFeux » comme nom de code en attente de marque définitive ;
- reformulation du positionnement afin d'éviter toute apparence de service opérationnel officiel ;
- fiche événement permanente rendue côté serveur ;
- chronologie textuelle incluse dans le MVP ;
- séparation entre fraîcheur, niveau de vérification et statut officiel ;
- provenance obligatoire pour les informations exposées ;
- historique append-only et tables préparant la relecture temporelle ;
- snapshots publics et règles de mode dégradé ;
- API, tests, backlog, recette et ADR mis à jour.

## Annexe I — Références officielles

**[S1] NASA FIRMS — présentation et latence globale**  
https://firms.modaps.eosdis.nasa.gov/

**[S2] NASA FIRMS — API Area et quota de clé**  
https://firms.modaps.eosdis.nasa.gov/api/area/

**[S3] NASA FIRMS — description MODIS et attributs**  
https://firms.modaps.eosdis.nasa.gov/descriptions/FIRMS_MODIS_Firehotspots.html

**[S4] Météo-France — données du modèle AROME**  
https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=131&id_rubrique=51

**[S5] Météo-France — migration des données publiques**  
https://donneespubliques.meteofrance.fr/

**[S6] Météo-France — descriptif technique des données radar, version 18/03/2025**  
https://donneespubliques.meteofrance.fr/client/document/descriptiftechnique_radar_donneespubliques_v1-2_20250318_404.pdf

**[S7] Copernicus CAMS — prévisions européennes de qualité de l'air**  
https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts

**[S8] IGN/Géoplateforme — API de téléchargement**  
https://geoservices.ign.fr/telechargement-api

**[S9] Supabase — PostGIS**  
https://supabase.com/docs/guides/database/extensions/postgis

**[S10] Supabase — Cron et planification**  
https://supabase.com/docs/guides/cron

**[S11] Supabase — Vault**  
https://supabase.com/docs/guides/database/vault

**[S12] Supabase — sécurisation de la Data API et RLS**  
https://supabase.com/docs/guides/api/securing-your-api

**[S13] CNIL — guide RGPD pour les développeurs**  
https://www.cnil.fr/en/gdpr-developers-guide

**[S14] CNIL — recommandations applications et permissions**  
https://www.cnil.fr/en/mobile-applications-cnil-publishes-its-recommendations-better-privacy-protection

**[S15] CNIL — traceurs et consentement**  
https://www.cnil.fr/en/dark-patterns-cookie-banners-cnil-issues-formal-notice-website-publishers

**[S16] Supabase — Metrics API**  
https://supabase.com/docs/guides/telemetry/metrics/vendor-agnostic

---

# Validation du document

Ce cahier constitue la référence de développement de la version 1.1 du MVP. Toute modification affectant le périmètre, la séparation public/opérationnel, les sources de données, le modèle de panache ou l'exposition des schémas Supabase doit être consignée dans une décision d'architecture et validée avant implémentation.
