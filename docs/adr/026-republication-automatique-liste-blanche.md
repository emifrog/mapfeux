# ADR-026 — Republication automatique en liste blanche des informations officielles

- **Statut** : accepté
- **Date** : 2026-08-26
- **Tranche** : décision ouverte [stratégie §8.3](../strategie.md#83-validation-humaine-des-informations-officielles) ;
  précise le cahier v2.1 §20.4 sans le contredire

## Contexte

Le cahier exige que toute information officielle publiée par MapFeux soit
attribuée à son organisme et jamais réécrite (§20.4, FR-141, FR-142). Le
modèle `app.official_messages` implémente ce contrat pour la voie
**éditoriale** : un auteur humain, un second valideur, et une contrainte en
base qui interdit la publication sans validation.

L'ingestion automatisée des informations officielles (J4) a été ajoutée au
MVP précisément pour ne pas dépendre d'un opérateur disponible en août.
Exiger qu'une information captée automatiquement passe par le circuit de
validation humaine réintroduirait exactement cette dépendance : en pleine
saison, les communiqués préfectoraux attendraient un valideur qui est sur
le terrain.

## Décision

**Les sources d'une liste blanche sont republiées automatiquement,
attribuées et jamais réécrites, sans valideur humain dans la boucle.**

- La liste blanche est un **registre en base**, administrable sans
  déploiement : organisme, URL exacte de la page ou du flux capté,
  rattachement départemental, interrupteur d'activation. N'y entrent que
  des publications d'**autorités** sur leurs domaines officiels
  (préfectures sur `*.gouv.fr`, vigilance Météo-France déjà en service).
- La republication est une **citation datée** : titre verbatim, lien vers
  la source, organisme, date de publication de l'autorité. Aucun résumé,
  aucune reformulation, aucun classement éditorial — ce que MapFeux ajoute
  (rattachement géographique, proximité d'un événement) est de la
  structure, jamais du sens.
- Chaque élément capté reste **masquable sans destruction** par un
  administrateur (`is_public`) : le retrait d'une erreur de capture est un
  geste d'exploitation, pas une validation préalable.
- La voie éditoriale `app.official_messages` — auteur, second valideur —
  **demeure inchangée** pour tout contenu que MapFeux formule lui-même.

## Conséquences

- Les tables de capture sont distinctes du modèle éditorial (comme la
  vigilance a les siennes) : la contrainte « publié exige validé » de
  `official_messages` reste intacte et vraie.
- La qualité de la republication repose sur la qualité de la liste
  blanche : y ajouter une source est un acte d'administration qui engage,
  au même titre qu'un lien officiel de territoire.
- Une capture défaillante (page restructurée, contenu inattendu) doit
  échouer **franchement** et se voir sur `/statut` — republier du bruit
  sous le nom d'une préfecture serait pire qu'un retard.
- La réponse à la première erreur publique (stratégie §8.5, toujours
  ouverte) couvre aussi ce canal.
