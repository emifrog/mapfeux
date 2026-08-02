# ADR-025 — Plateforme à deux visages : accueil de PREVIFEU dans le monorepo

- **Statut** : accepté
- **Date** : 2026-08-02
- **Amende** : cahier §3.3 (périmètre des produits voisins) ; complète ADR-008
  (séparation DFCI OPS) sans le modifier

## Contexte

MapFeux est défini comme un service d'information cartographique grand public,
indépendant de tout dispositif opérationnel (cahier §2). Un second produit est
spécifié par ailleurs : PREVIFEU, aide à la décision **réservée aux SDIS**,
qui anticipe le risque d'éclosion à J-1/J-3 (IFM/FWI sur champs AROME,
sécheresse des sols, historique d'éclosions) et prépare le pré-positionnement
des moyens.

Les deux produits partagent l'essentiel de leur substance technique : mêmes
sources (AROME, FIRMS, référentiels IGN), même pile géospatiale Python, mêmes
règles de provenance, de fraîcheur et d'historisation, même culture de recette
rejouable. Les développer dans deux dépôts reviendrait à dupliquer le worker,
les vocabulaires et la CI, puis à les faire diverger.

À l'inverse, les fusionner en **un seul produit** est exclu : un score de
risque localisé est une donnée sensible (exploitable à des fins de malveillance),
et la crédibilité publique de MapFeux repose précisément sur son indépendance
vis-à-vis de tout dispositif opérationnel. La frontière n'est pas technique,
elle est de positionnement et de sécurité.

Enfin, PREVIFEU ne démarre pas immédiatement : le développement de MapFeux
(J4 à J6) reste prioritaire. Cet ADR fige l'architecture d'accueil **avant**
que des décisions locales ne la rendent coûteuse, et identifie la donnée
périssable à capturer dès maintenant.

## Décision

**Une plateforme, un socle, deux visages.**

1. **Un seul monorepo.** PREVIFEU sera une application du monorepo `mapfeux`,
   sous `apps/previfeu`, consommant les paquets existants (`domain`,
   `contracts` étendu ou paquet frère, `config`) et le worker
   `services/geo-worker` enrichi de providers (`arome`, `swi`) et de pipelines
   (`fwi`) dédiés.

2. **Deux projets Supabase, sans exception.** Le projet MapFeux ne contient
   aucun score prédictif ; le projet PREVIFEU porte ses propres schémas, ses
   propres rôles et sa propre surface exposée. L'étanchéité se joue au niveau
   des projets et des identités, pas au niveau du code. Aucune base commune,
   aucun flux PREVIFEU → MapFeux, jamais.

3. **Le worker est un code, deux déploiements.** Le même code de
   `services/geo-worker` s'exécute en deux instances, chacune pointant vers son
   projet Supabase, avec sa propre file de tâches PostgreSQL et son propre
   planificateur (conforme à ADR-016, y compris sa contrainte d'instance de
   planification unique — elle s'applique **par déploiement**).

4. **Les extraits AROME sont conservés dès leur première ingestion.** Lorsque
   l'ingestion AROME entrera en service pour le panache (cahier §18), les
   champs utiles au calcul FWI (température 2 m, humidité relative, vent 10 m,
   précipitations) seront archivés en stockage froid après usage, au lieu
   d'être purgés. Ce corpus est la matière première de la calibration
   PREVIFEU ; il est périssable, son archivage est quasi gratuit, il commence
   avec le panache sans attendre PREVIFEU.

5. **Le flux d'événements vers PREVIFEU est un export batch contrôlé.**
   L'historique d'éclosions de PREVIFEU se construit depuis les événements
   MapFeux par export unidirectionnel (MapFeux → PREVIFEU), au même titre que
   depuis la BDIFF et Prométhée. C'est le symétrique du principe déjà acté
   pour DFCI OPS (ADR-008) : les produits opérationnels consomment MapFeux,
   jamais l'inverse.

## Conséquences

**Favorables**

- Le socle (ingestion, vocabulaires, provenance, CI, recette rejouable) est
  investi une fois et sert deux produits ; toute amélioration du worker
  profite aux deux visages.
- L'archivage AROME transforme une purge en actif : chaque jour d'exploitation
  MapFeux construit l'historique de calibration PREVIFEU.
- La séparation par projets Supabase rend la frontière public/opérationnel
  auditable de l'extérieur : il suffit de constater qu'aucune clé, aucun rôle
  et aucune table ne sont partagés.
- La décision est datée et opposable dans toute discussion de partenariat :
  l'architecture « plateforme » précède la négociation, elle n'est pas
  fabriquée pour elle.

**Défavorables**

- La CI du monorepo s'alourdit d'une application et de pipelines
  supplémentaires ; les temps de build sont à surveiller (Turborepo limite le
  coût aux paquets affectés).
- Deux projets Supabase signifient deux jeux de migrations, de secrets et de
  sauvegardes à opérer.
- Le stockage froid AROME introduit un coût récurrent (faible : quelques
  champs sur deux départements, puis emprise nationale) et une politique de
  rétention à écrire (à rattacher à ADR-010).
- Étendre `services/geo-worker` pour deux consommateurs impose une discipline
  de compatibilité : les pipelines MapFeux ne doivent jamais dépendre d'un
  module PREVIFEU.

## Condition de réexamen

Cette décision est réexaminée si l'un de ces cas survient :

- une exigence SSI d'un SDIS impose l'auto-hébergement de PREVIFEU (le
  monorepo demeure, le déploiement diverge) ;
- la charge de la CI ou la cadence des versions rend le monorepo pénalisant en
  pratique ;
- un partenariat industriel impose une séparation de propriété intellectuelle
  entre le socle et l'un des visages — auquel cas l'extraction du worker en
  dépôt propre (« orionis-geodata ») redevient l'option de référence.

La ligne rouge, elle, n'est pas réexaminable par simple ADR : toute proposition
faisant apparaître un score prédictif dans le visage public constitue une
révision du positionnement du cahier (§2) et suit le circuit de révision du
cahier, pas celui des ADR.
