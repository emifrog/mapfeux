# MapFeux — Stratégie

**Version 1.1 — 6 août 2026** — décision D-0 (option A) répercutée au §4,
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

### 8.3 Validation humaine des informations officielles

L'ingestion automatisée a été ajoutée au MVP pour ne pas dépendre d'un opérateur
disponible en août. Exiger ensuite qu'une information captée soit validée à la
main avant publication réintroduit exactement cette dépendance.

Il faut trancher : soit une liste blanche de sources dont la republication
**attribuée et non réécrite** est automatique, soit assumer le second valideur
et l'identifier dès maintenant.

### 8.4 Préfixe d'identifiant public

`fire.generate_public_id` utilise aujourd'hui `MPF-` par défaut. Le préfixe doit
être figé **avant la première URL publique** : après, il est permanent.

### 8.5 Réponse à la première erreur publique

Le jour où une détection thermique est présentée comme événement probable alors
qu'il n'y a pas de feu, pendant qu'un média regarde. Le cahier prévoit un
runbook technique ; il manque la réponse éditoriale et publique. À écrire avant
l'ouverture.
