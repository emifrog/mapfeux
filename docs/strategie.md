# MapFeux — Stratégie

**Version 1.3 — 11 septembre 2026** — re-sonde GISFire (§2) : le concurrent
est passé au monde entier, aux fiches indexées en quatre langues et à
l'abonnement payant ; les torchères de Fos et Grande-Synthe y sont
devenues des **pages titrées « Feu de »**, et le bilan départemental des
Bouches-du-Rhône n'est composé que d'elles. Version 1.2 : 25 août 2026 —
veille concurrentielle du §2, deux entrants examinés sur pièces (GISFire,
Climate Innov), thèse confirmée, frontière des moyens aériens rappelée.
Version 1.1 : 6 août 2026 — décision D-0 (option A) répercutée au §4,
autorisation de cumul obtenue (§3.1, point d'arrêt du §7 levé), calendrier
tranché (§8.2). Version 1.0 : 28 juillet 2026.

Ce document porte les décisions qui ne bougent pas d'une semaine sur l'autre :
positionnement, périmètre, préalables juridiques, modèle économique, conditions
d'arrêt. Il ne décrit **pas** l'avancement — c'est le rôle de
[plan-de-developpement.md](plan-de-developpement.md), qui porte seul le
découpage en jalons et l'état réel du code.

Le document de référence est le **cahier des charges v2.1** (5 août 2026, PDF
hors dépôt), qui remplace le
[cahier de développement v1.1](../MapFeux_Cahier_de_developpement_v1.1.md) —
conservé pour l'historique. Le présent document en organise la livraison. Les
écarts techniques assumés sont au [registre des ADR](adr/README.md).

---

## 1. Thèse produit

À relire avant chaque arbitrage de périmètre :

> MapFeux est la fiche événement de référence sur les feux en France : une page
> permanente, sourcée, horodatée et lisible même quand tout le reste tombe.

Ce que cela implique :

- l'objet central n'est pas la carte, c'est **l'événement** ;
- l'avantage compétitif n'est pas la fraîcheur brute, c'est **l'attribution et
  la permanence** ;
- l'avantage stratégique est d'exister **avant** le prochain grand feu, pas
  d'être construit pendant.

**Ce que MapFeux ne fera jamais** : confirmer un feu, déclarer une extinction,
publier une position de moyens, se substituer à une alerte officielle.

## 2. Différenciation

| Concurrent | Ce qu'il fait bien | Ce que MapFeux fait mieux |
|---|---|---|
| FeuScope | Relecture temporelle, mono-feu, très réactif | Rendu serveur, permanence des URL, couverture nationale préexistante |
| alertesfeux.fr | Agrégation des communiqués préfectoraux, évacuations, hébergements | Attribution formelle, horodatage, historique conservé |
| suivi-feu-medoc | Rendu spectaculaire, ADS-B, imagerie Meteosat | Rigueur sémantique, statuts séparés, pas de confusion avec l'officiel |
| feuxdeforet.fr, feux.net | Volume de pages, SEO | Traçabilité vérifiable, absence d'affirmation non sourcée |
| FIRMS, EFFIS | Données brutes de référence | Maille communale, langue française, lisibilité grand public |
| GISFire (gisfire.saro.app) | Le concurrent le plus complet, et il accélère : cinq produits FIRMS dont GOES, monde entier (26 666 feux actifs), fiches **rendues serveur** et indexées en quatre langues, pages départementales, rejeu de propagation, panache, ADS-B et largages, foudre, `/api/status` détaillé, abonnement Pro (alertes courriel/SMS, API) | Masque des sources statiques — **re-sondé le 11 septembre : Fos et Grande-Synthe sont devenues des pages « Feu de », 1 042 et 1 189 ha** —, identifiants opaques, statut officiel jamais posé par un automate, surfaces avec méthode, provenance attribuée plutôt que rapprochement de presse |
| Climate Innov (ensemblepourlaforet.fr) | Risque de départ de feu horaire, 3 km, 36 h, météo satellitaire (Spire), partenaire EDHEC | Pas un concurrent : le risque avant le feu, MapFeux l'observation pendant et après — leur propre avertissement renvoie ailleurs pour les feux en cours. SecuFire Action (Balbi, gratuit pour les SDIS) concurrence PREVIFEU, pas MapFeux |

### Veille du 25 août 2026 — deux entrants, examinés sur pièces

**GISFire** (SARO × Gistin, deux agences web/SIG — vitrine, pas institution)
est le concurrent frontal le plus abouti vu à ce jour, en ligne aujourd'hui :
cinq produits FIRMS dont GOES, regroupement en événements (~1 700 actifs,
Europe entière), fiches par incendie (courbe FRP, emprise, avant/après),
curseur temporel avec rejeu, panache calculé du vent prévu, suivi ADS-B des
Canadair et zones de largage, foudre sur 7 jours, `/api/status` par source
avec mode dégradé. Sa visite guidée est d'une honnêteté remarquable — « c'est
une détection, pas un constat de terrain », panache « estimation, pas
observation » qui pâlit quand le vent tourne : le ton juste existe ailleurs.

Mais le produit ne porte pas la machinerie derrière le ton, et c'est
démontrable sur ses propres données : sondé le 25 août, **GISFire servait
« Fos-sur-Mer, 45 pixels » et « Grande-Synthe, 106 pixels » comme feux
actifs** — les torchères que le masque MapFeux a mesurées et éteintes le
10 août. S'y ajoutent : identifiants internes séquentiels exposés, surfaces
en hectares sans méthode, « incendies signalés » = flux Google News au filtre
bruyant (aucune parole officielle), aucune méthodologie publiée, rien ne se
rend sans JavaScript. Sa visite dit « seule la préfecture fait foi » ; son
produit ne porte pas la préfecture. Une idée à retenir : `nextDataAt`,
l'heure du prochain passage satellite annoncée sur chaque événement.

**Climate Innov** (Nice, EDHEC Climate Institute, Spire) occupe le créneau
voisin, pas le nôtre : `ensemblepourlaforet.fr` prédit le **risque de départ
de feu** (horaire, 3 km, 36 h) et affiche « n'informe pas sur les feux en
cours » — le vide que MapFeux comble. Sa page commerciale revendique « 94 %
d'efficacité » sans métrique ni référentiel, l'exemple même de ce que §2.4
interdit. **SecuFire Action** (propagation Balbi, gratuit pour les acteurs
publics) est en revanche un concurrent direct de PREVIFEU, à suivre avant le
pilote 2028.

Trois conséquences. La thèse tient : le couloir « observation attribuée,
permanente, avec la parole officielle » reste vide — GISFire a la surface,
personne n'a la profondeur, et le jour où un média titrera sur un « feu » de
torchère d'après une carte concurrente, la différence deviendra une histoire
racontable. **J4 prend de la valeur** : l'information officielle attribuée
est la réponse structurelle que ni un fil de presse ni un disclaimer ne
remplacent. Enfin la frontière des moyens aériens est déjà tranchée par la
thèse — « jamais de position de moyens » : GISFire fait ce que MapFeux
s'interdit, et c'est un choix, pas un retard.

Entretien : re-sonder Fos chez GISFire et revisiter les deux acteurs avant
l'ouverture publique ; toute nouvelle fonction chez eux s'évalue contre la
thèse, pas contre la peur de manquer.

### Veille du 11 septembre 2026 — GISFire re-sondé : la torchère a sa page

Dix-sept jours après, l'entretien prescrit ci-dessus a été exécuté. Le
concurrent a beaucoup avancé, et **le défaut de fond s'est aggravé en
devenant durable**.

Ce qu'ils ont gagné : GOES ajouté (83 137 lignes/24 h, le plus gros
volume), passage de l'Europe au **monde entier** — 262 847 détections sur
24 h, 26 666 feux actifs ; des **fiches rendues serveur** et indexées,
`/feux/foyer/<lieu>-<lat>n<lon>e`, doublées de pages départementales
`/feux/<departement>`, le tout en **quatre langues** (652 URL au sitemap) ;
un `/api/status` par source avec `stalenessS` et drapeau `degraded` ; un
**abonnement Pro** (alertes courriel et SMS sur zones surveillées, API,
historique). Ils ont aussi commencé J4 à leur manière : presse et sources
officielles « rapprochées automatiquement », avec historique de qui a
annoncé quoi.

Ce qu'ils ont perdu en le gardant. Les torchères ne sont plus seulement
servies sur la carte : elles ont des **pages permanentes, titrées, en
quatre langues**.

- `/feux/foyer/fos-sur-mer-43.45n4.89e` — « **Feu de Fos-sur-Mer du
  10 août 2026** », 850 détections sur 29 jours, **1 042 ha d'emprise**.
- `/feux/foyer/grande-synthe-51.04n2.29e` — « **Feu de Grande-Synthe du
  11 août 2026** », 748 détections sur 30 jours, **1 189 ha**.
- Et surtout `/feux/bouches-du-rhone` : « **2 foyers détectés au cours des
  30 derniers jours, pour 1 426 hectares d'emprise cumulée** » — les deux
  foyers étant Fos (1 042 ha) et Martigues (384 ha, raffinerie de Lavéra).
  **Le bilan départemental d'un département méditerranéen est composé à
  100 % de sites industriels.**

Justice leur soit rendue : la nuance est dans le corps du texte — « le feu
**ou la source de chaleur** peut être plus ancien », « seules la préfecture
et le SDIS font foi », et une distinction fine entre orbites polaires (qui
mesurent une surface) et géostationnaires (trop grossières pour une
géométrie). Ils savent. Mais **le titre, l'URL, le H1 et l'agrégat
départemental disent « feu »** — et c'est le titre qui part dans Google,
dans un partage, dans une reprise de presse. La leçon est nette et vaut
pour nous : **un avertissement ne corrige pas une structure**. Là où nous
avons payé un registre spatial de 45 sources et une mesure (10 août), ils
ont payé une phrase.

Deuxième écart de doctrine, nouveau : leurs fiches affichent une
chronologie avec **statuts affirmés** — « Éteint … éteint le 9 septembre à
05:00 » sur la torchère de Fos, qui brûle en continu. Un automate y pose
un statut d'extinction ; chez nous, FR-047 l'interdit en base et dans le
domaine, et l'observation postérieure à un statut officiel déclenche une
alerte de cohérence sans jamais écraser (FR-145, livré le 26 août).

Trois conséquences pour nous, aucune en panique.

1. **La thèse ne bouge pas, elle se vérifie.** Le couloir « observation
   attribuée, permanente, avec la parole officielle » reste vide : ils ont
   pris la surface, l'échelle et maintenant le SEO — pas la profondeur.
   L'histoire racontable est désormais adossée à des URL publiques.
2. **J4 était le bon pari.** Ils rapprochent de la presse ; nous
   republions de l'autorité en liste blanche, verbatim et attribuée
   (ADR-026), plus les niveaux d'accès aux massifs. C'est la différence
   entre « on en a parlé » et « la préfecture a écrit ».
3. **Ce qui mérite d'être copié, et rien d'autre** : `stalenessS` et le
   drapeau `degraded` de leur `/api/status` (à verser au mode dégradé de
   J5, FR-115), et `nextDataAt` — l'heure du prochain passage satellite,
   déjà notée le 25 août. Les fiches indexées multilingues, l'abonnement
   payant et les moyens aériens ne s'évaluent pas ici : l'i18n est déjà
   cadrée (FR-166, français seul activé), le modèle économique est au §6,
   et la position des moyens reste interdite par la thèse.

Entretien : re-sonder avant l'ouverture publique, en vérifiant d'abord si
le bilan des Bouches-du-Rhône a changé de composition.

### Qui lira réellement MapFeux

Le grand public en situation de crise cherche à savoir **s'il doit partir**.
MapFeux refuse délibérément de répondre à cette question. L'audience réelle est
donc plus étroite que « le grand public » : journalistes, élus, agents
communaux, riverains informés, et toute personne cherchant après coup ce qui
s'est réellement passé.

Ce n'est pas une faiblesse, mais cela a deux conséquences qu'il faut assumer :
le succès ne se mesure pas au volume de visites, et l'API partenaire du §5
devient probablement la piste de financement principale plutôt qu'une option
parmi d'autres.

---

## 3. Phase 0 — Préalables non techniques

**Aucun jalon de développement ne s'achève tant que 3.1 et 3.2 ne sont pas
clos.** Durée : 3 à 4 semaines calendaires, menées en parallèle du travail
technique déjà engagé.

### 3.1 Position vis-à-vis du SDIS 06 et de l'employeur

**Autorisation de cumul accordée le 6 août 2026.** La demande écrite — avec la
note explicite : plateforme grand public, aucune donnée opérationnelle, aucune
donnée DFCI, aucun lien technique avec les systèmes du SDIS — a reçu une
réponse favorable de l'employeur. Le point d'arrêt correspondant du §7 est
levé.

Restent à traiter, sans bloquer les jalons :

- Point avec la hiérarchie sur la communication : que se passe-t-il si un
  journaliste cite MapFeux en présentant l'auteur comme sapeur-pompier du 06 ?
- Décider si le lien auteur/SDIS est mentionné publiquement ou dissocié. Les
  deux choix sont défendables, l'ambiguïté ne l'est pas.

### 3.2 Cadre juridique de l'édition

- Éditeur : Orionis Solutions SAS. Mentions légales complètes, directeur de
  publication nommé.
- Responsabilité civile professionnelle couvrant la diffusion d'information
  publique.
- Relecture par un juriste des formulations obligatoires et des pages
  méthodologie, statut et limites.
- Vérification d'antériorité de la marque MapFeux (INPI) et dépôt en classes 9,
  38 et 42. Réservation des domaines `mapfeux.fr` et `.com`.

### 3.3 Audit de licences

Pour chaque source, un tableau signé avant le jalon correspondant : licence,
attribution exacte à afficher, conditions de rediffusion via l'API publique,
limites de quota, contact.

- **NASA FIRMS** — attribution requise, quota 5 000 transactions / 10 min.
- **Météo-France AROME et radar** — Licence Ouverte Etalab, mention de la source
  obligatoire, migration de portail en cours.
- **Copernicus CAMS** — mention « informations du service Copernicus modifiées »
  à formuler exactement.
- **IGN ADMIN EXPRESS COG** — Licence Ouverte, 10 requêtes/s.
- **API Découpage administratif (Etalab)** — source effectivement utilisée pour
  les limites communales du pilote ; voir [ADR-017](adr/017-source-des-limites-communales.md).

### 3.4 Demander l'archive FIRMS

**À engager tôt : la livraison n'est pas immédiate.**

Constaté en exploitation : l'API Area de FIRMS ne sert que les jeux NRT, sur une
fenêtre glissante d'environ quatre mois. Une requête datée de juillet 2025
répond 200 avec zéro ligne — pas une erreur, simplement rien.

Or le critère de sortie du regroupement suppose une calibration sur plusieurs
saisons. Sans archive, elle se limite à la saison en cours, ce qui suffit à
vérifier la reproductibilité mais pas à régler les seuils contre des cas
variés : petit feu de broussailles, grand feu de forêt, torchère industrielle,
fausse détection.

L'archive s'obtient par une demande auprès de FIRMS, livrée en différé. Elle
conditionne le jalon des événements, donc l'un des points d'arrêt du §7.

### 3.5 Estimation du coût d'un pic

Déplacée en phase 0 : elle conditionne un point d'arrêt (§7), et un pic de
trafic peut survenir le lendemain de la première publication. Une demi-journée
suffit à obtenir un ordre de grandeur.

- hébergement et base en régime normal, puis pendant un épisode médiatisé ;
- CDN et bande passante sur une journée à forte affluence ;
- stockage des archives brutes et des rasters ;
- nom de domaine, marque, assurance, revue de sécurité externe.

---

## 4. Périmètre du MVP

**Décision D-0 — option A, confirmée le 5 août 2026 (cahier v2.1, §26.1) : le
périmètre v2.0 est livré intégralement à l'ouverture publique.** Ce choix
privilégie la complétude et la crédibilité du produit au lancement sur la
précocité du calendrier ; sa conséquence assumée est le report du démarrage de
PREVIFEU après le lancement, pilote SDIS visé saison feux 2028 (ADR-025).
L'option C — renfort ou partenariat — reste ouverte à tout moment et resserre
le calendrier sans changer le périmètre.

### Entre dans l'ouverture publique

- fiche événement permanente, rendue côté serveur, avec chronologie textuelle ;
- trois dimensions de statut séparées et provenance sur chaque bloc ;
- import FIRMS, dédoublonnage, regroupement en événements ;
- carte nationale et départementale, recherche de commune ;
- catalogue national des événements récents et archivés ;
- relecture temporelle partageable et version imprimable ;
- vent, panache indicatif et communes potentiellement concernées ;
- qualité de l'air CAMS et radar de précipitations ;
- périmètres sourcés, versionnés, multi-sources ;
- agrégation des informations officielles attribuées ;
- pages statut, méthodologie, sources, mentions ;
- PWA, snapshots publics et mode dégradé ;
- administration privée et audit.

### Réserves de la v1.0, converties en contraintes de conception

La version 1.0 de ce document sortait du MVP le panache, les communes
concernées, CAMS/radar et la relecture. La décision D-0 les réintègre ; les
raisons du report ne disparaissent pas pour autant — elles changent de forme :

- **Panache indicatif.** Physiquement fragile avec un vent à 10 m, très fragile
  dans le relief du 06. La réponse n'est plus le retrait mais les garde-fous du
  cahier §18 : incertitude affichée et croissante, confiance dégradée en
  relief, aucun panache sur modèle expiré, désactivation globale immédiate
  possible (FR-106). C'est la seule fonction qui pousse un utilisateur vers une
  décision : sa formulation publique passe par la validation métier avant toute
  mise en ligne.
- **Communes potentiellement concernées** — dépendent du panache et héritent de
  ses garde-fous ; le libellé « potentiellement concernée » est obligatoire
  (FR-111).
- **CAMS et radar** — chacun ajoute un pipeline à exploiter ; leur panne ne
  doit jamais toucher la carte des détections (FR-125), et ils restent
  affichés « à venir » tant que le connecteur n'existe pas.

### Ajouté au MVP

- **Ingestion automatisée des sources officielles** : flux RSS et pages de
  communiqués des préfectures, comptes officiels, vigilance Météo-France,
  arrêtés d'accès aux massifs. C'est ce que les gens cherchent réellement
  pendant une crise, et l'automatisation évite d'exiger un opérateur humain
  disponible en août — au moment précis où l'auteur est en intervention.

---

## 5. Modèle économique et pérennité

Section absente du cahier v1.1. Le chiffrage relève de la phase 0 (§3.4) ; le
choix du modèle doit être arrêté avant le jalon des informations officielles.

### Pistes, à arbitrer

1. **Autofinancement Orionis** — simple, mais plafonne la capacité à tenir un
   pic.
2. **Subvention ou mécénat** — région, département, fondation, en cohérence avec
   un service d'intérêt général.
3. **API partenaire payante** — presse et collectivités paient un accès
   structuré, le grand public reste gratuit. Cohérent avec l'architecture d'API
   versionnée déjà en place, et cohérent avec l'audience réelle décrite au §2.
4. **Adossement associatif** — clarifie le caractère non lucratif, simplifie la
   question du cumul d'activité, complique la gouvernance.

### Continuité

- Que devient le service si l'auteur s'arrête ? Écrire la réponse et la publier.
- Code source ouvert ou séquestre : à décider explicitement.
- Engagement public de disponibilité : tenu, ou pas annoncé du tout. Mieux vaut
  ne rien promettre que promettre et échouer en août.

---

## 6. Fenêtre d'observation

Un épisode majeur en cours est une fenêtre qui ne se représente pas avant un an.
Ce qui est **périssable** :

- ce que publient les concurrents, à quelle fréquence, avec quelles sources ;
- ce qui casse chez eux, et à quel moment de la crise ;
- ce que les préfectures publient réellement, sous quel format, à quelle
  cadence — c'est le cahier des charges de l'ingestion officielle ;
- les questions posées en commentaire et sur les réseaux : ce sont les besoins
  réels, exprimés sous stress.

Ce qui ne l'est **pas** : les détections FIRMS de l'épisode. L'archive est
consultable après coup, la constitution du jeu de calibration peut attendre.
L'effort de la semaine doit porter sur l'observation éditoriale, pas sur le
téléchargement de données.

---

## 7. Points d'arrêt

Le projet s'arrête ou change de forme si :

- ~~l'autorisation de cumul est refusée, ou assortie de conditions
  incompatibles~~ — **levé le 6 août 2026**, autorisation accordée (§3.1) ;
- l'audit de licences interdit la rediffusion d'une source structurante ;
- le regroupement en événements ne produit pas de résultat stable et
  reproductible sur données historiques ;
- le coût d'un pic de crise dépasse ce que le modèle de financement absorbe ;
- une autorité publique annonce un service équivalent — auquel cas la bonne
  réponse est de lui proposer la brique d'attribution, pas de rivaliser.

---

## 8. Décisions ouvertes

À trancher explicitement. Tant qu'elles ne le sont pas, le plan d'exécution les
signale comme bloquantes pour le jalon concerné.

### 8.1 Ordonnancement — tranché le 28 juillet 2026

**La question était mal posée.** Elle demandait « faut-il revenir à Celery et
Redis ? », alors que le besoin réel est un **déclencheur**, pas un ordonnanceur
de tâches. Les trois services que Celery et Redis rendent sont déjà rendus, et
mieux :

| besoin | réponse retenue |
|---|---|
| exclusion mutuelle | `pg_advisory_lock` de session, plus l'index partiel `import_runs_single_running` |
| file de tâches | table PostgreSQL, `for update skip locked` ([ADR-016](adr/016-file-de-taches-postgresql.md)) |
| débit | sans objet : la chaîne complète met six secondes, FIRMS publie toutes les six heures |

L'argument décisif est transactionnel et il ne joue pas en faveur de Redis :
l'insertion d'une tâche et l'écriture des données qui la motivent partagent la
même transaction. Avec Redis, un `commit` réussi suivi d'un `enqueue` échoué
perd la tâche en silence. Sur un service qui promet une fraîcheur, une tâche
perdue sans trace est le pire mode de panne possible.

Les seuils de réexamen d'ADR-016 — plus d'une instance de worker, une minute
d'attente en file, cent panaches recalculés simultanément — ne sont approchés
par aucune mesure.

**Décision** : le déclenchement passe par un workflow GitHub Actions planifié
(`.github/workflows/ingestion.yml`), toutes les dix minutes, appelant
`scripts/run-ingestion.py`. Rien à installer, rien à redémarrer, et la tâche
survit à l'extinction du poste de développement.

Deux contraintes ont dicté la forme :

- la connexion directe Supabase ne résout **qu'en IPv6**, dont les runners
  GitHub ne disposent pas. Le workflow passe donc par le pooler **en mode
  session**, port 5432 — le mode transaction, port 6543, casserait le verrou,
  qui est un verrou de session ;
- la chaîne de connexion vit chez un tiers, donc elle ne porte pas `postgres`.
  Un rôle `mapfeux_ingest` la restreint à ce que fait l'ingestion : il ne peut
  lire ni l'administration, ni l'audit, ni les messages officiels, et n'a aucun
  droit d'effacement. `scripts/verify-ingestion-role.py` rend ce périmètre
  vérifiable à tout moment.

Le déclencheur est **remplaçable en une ligne**, puisque la file, le
verrouillage et l'idempotence vivent en base : cron, tâche planifiée Windows,
minuterie systemd ou APScheduler appellent le même point d'entrée. C'est ce qui
rend la décision peu coûteuse à défaire.

### 8.2 Calendrier et saison — tranché le 5 août 2026 (D-0)

La décision D-0 cale la fenêtre de lancement **hors pic saisonnier**
(automne-hiver), pour ne pas faire coïncider la première mise en charge
nationale avec une crise. C'est la forme retenue de l'alternative envisagée
ici : ouverture discrète sur le 06 et le 83 en période calme, flux en
production pendant plusieurs mois, puis communication au printemps sur un
service déjà éprouvé — avec hypercare avant l'été suivant.

Le point de vigilance demeure : les jalons intermédiaires tombent en pleine
saison des feux, au moment où la disponibilité de l'auteur s'effondre. Les
durées du plan sont calendaires et l'assument.

### 8.3 Validation humaine des informations officielles — tranché le 26 août 2026

**Liste blanche automatique**
([ADR-026](adr/026-republication-automatique-liste-blanche.md)).

Les sources d'un registre en base — publications d'autorités sur leurs
domaines officiels — sont republiées automatiquement, attribuées et jamais
réécrites, sans valideur humain dans la boucle : exiger une validation
manuelle réintroduirait la dépendance à un opérateur disponible en août,
celle-là même que l'automatisation devait supprimer. Chaque élément capté
reste masquable sans destruction par un administrateur ; la voie
éditoriale (`official_messages`, auteur et second valideur) demeure
inchangée pour tout contenu que MapFeux formule lui-même.

### 8.4 Préfixe d'identifiant public — tranché le 10 août 2026

**`MPF-`, définitivement** ([ADR-021](adr/021-prefixe-didentifiant-public.md)).

La question demandait de figer le préfixe **avant la première URL publique** ;
cette fenêtre s'est refermée le 9 août, le catalogue national servant depuis
les URL des 933 événements réels, tous en `MPF-`. La décision ratifie l'état
servi plutôt que de payer une migration de renommage pour un bénéfice
cosmétique — l'identifiant est une référence stable, pas la marque, et doit
survivre à tout changement de nom. `DEMO-` reste réservé au jeu de
démonstration.

### 8.5 Réponse à la première erreur publique

Le jour où une détection thermique est présentée comme événement probable alors
qu'il n'y a pas de feu, pendant qu'un média regarde. Le cahier prévoit un
runbook technique ; il manque la réponse éditoriale et publique. À écrire avant
l'ouverture.
