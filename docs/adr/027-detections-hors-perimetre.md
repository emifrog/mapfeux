# ADR-027 — Les détections hors périmètre sont importées, jamais publiées

- **Statut** : accepté
- **Date** : 2026-09-15
- **Révision** : 2026-09-15 au soir — la conséquence sur le regroupement
  était écrite à l'envers (voir « Conséquences ») ; texte corrigé, le code
  n'a pas changé
- **Tranche** : applique le cahier v2.1 §2.4 et FR-001 (« France
  métropolitaine et Corse ») à l'ingestion, sans le contredire ; précise
  §17.7 (masquage)

## Contexte

La zone d'import FIRMS est un rectangle qui déborde des frontières : nord de
l'Espagne, Belgique, Sarre et Palatinat, Piémont, golfe de Gascogne, Manche.
Chaque événement reçoit la commune française la plus proche, sans limite de
distance. Le 15 septembre 2026, sur sept jours, le service publiait 716
événements dont **322 en France** ; la fiche « Anomalies thermiques près de
Condé-sur-l'Escaut » décrivait un site industriel belge près de Gand, à
quatre-vingts kilomètres de la commune ; les Pyrénées-Atlantiques
comptaient 80 événements, dont 7 dans leur polygone. Le périmètre du
service était écrit sur toutes les pages et appliqué nulle part.

Les agrégats départementaux ont été corrigés le même jour (47ᵉ migration) :
un département ne compte que ce qui est chez lui, ou en mer à moins de
0,05 degré. Restaient la carte à l'échelle d'une zone, le catalogue, les
fiches et les pages communes, qui servaient encore ces événements.

## Décision

**Les détections hors périmètre restent importées ; l'événement qu'elles
forment n'est jamais publié.**

- Le périmètre est **une règle, en un endroit** :
  `fire.point_in_territory` — dans le polygone d'un département, ou à
  moins de 0,05 degré de l'un d'eux, la même règle que les agrégats.
- `fire.events.in_territory` porte le verdict, posé par déclencheur à
  chaque insertion et à chaque déplacement du point représentatif.
- Un événement hors périmètre est **masqué par le mécanisme existant** —
  `freshness_status = 'hidden'`, motif « hors périmètre : France
  métropolitaine et Corse » —, que toutes les fonctions publiques honorent
  déjà. Le déclencheur le force quel que soit le chemin qui écrit et rend la
  main au cycle de vie si le point revient dans le périmètre.
- La fiche d'un tel identifiant **dit pourquoi** elle ne montre rien, plutôt
  qu'un 404 muet sur un lien qui a pu circuler.
- L'ingestion ne change pas : la donnée brute est archivée de toute façon
  (§16.1), rien n'est détruit, et la décision est réversible d'un
  `update`.

## Alternatives écartées

- **Filtrer à l'import** par le polygone des départements. Plus simple et
  moins de lignes en base, mais irréversible : une détection non importée
  ne se retrouve pas si le périmètre s'élargit un jour — un massif
  transfrontalier, une demande de la Corse sur la Sardaigne. Reste
  possible plus tard, par-dessus cette décision, si le volume le justifie.
- **Un état propre** (`outside_territory`) distinct de `hidden`. Plus
  expressif, mais chaque fonction publique — fiche, détections,
  périmètres, chronologie, instantané, catalogue, emprise — porte sa
  propre condition `<> 'hidden'` ; les réécrire toutes pour une règle
  géographique multiplie les endroits où elle peut manquer.

## Conséquences

- Le catalogue, la carte, les pages communes et les agrégats disent les
  mêmes nombres, ceux de la France.
- Un site industriel étranger reste **un seul événement, masqué** : le
  regroupement continue de lui rattacher ses détections — `_existing_events`
  (`clustering.py`) n'écarte que `archived`, jamais `hidden`. C'est voulu :
  écarter les masqués engendrerait un événement masqué par passe pour
  chaque site persistant, et c'est le rattachement qui déplace le point
  représentatif et permet au déclencheur de rendre la main si l'événement
  revient dans le périmètre. Le texte initial de cet ADR et de la 49ᵉ
  migration affirmaient l'inverse ; un audit externe l'a relevé le soir
  même, et la production a tranché — 53 rattachements à 14 événements déjà
  masqués depuis la migration. Un test fixe désormais la règle.
- La base garde environ une détection sur deux hors périmètre. À revoir
  avec la purge de rétention (plan §15, J5) si le volume pèse.
- Les identifiants déjà partagés d'événements hors périmètre mènent à une
  page qui l'explique ; ils ne redirigent vers rien.
