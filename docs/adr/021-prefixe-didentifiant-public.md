# ADR-021 — Préfixe d'identifiant public : `MPF-`, figé

**Statut** : accepté
**Date** : 10 août 2026
**Cahier** : §15.1, §15.3 ; FR-041
**Remplace** : rien. Clôt la [décision §8.4](../strategie.md#84-préfixe-didentifiant-public--tranché-le-10-août-2026) de la stratégie.

## Contexte

`fire.generate_public_id` produit des identifiants opaques en base32 de
Crockford (FR-041), préfixés par défaut `MPF-` depuis la migration du
27 juillet 2026. La stratégie (§8.4) demandait de figer ce préfixe **avant la
première URL publique durable**, le comment de la fonction le disant
« configurable tant que la marque n'est pas arrêtée ».

Cette fenêtre s'est refermée le 9 août sans décision explicite : le catalogue
national `/evenements` et les archives servent depuis cette date les URL des
933 événements réels, tous porteurs du préfixe `MPF-`. La carte de partage
Open Graph (FR-067, fin de J7) va de surcroît graver ces URL dans les partages
sociaux, où elles ne se corrigent plus.

Une réserve a été examinée : le plan nomme « FeuScope » l'expérience publique
(J7). Si la marque devait s'écarter de « MapFeux », fallait-il un préfixe qui
la suive ?

## Décision

Le préfixe d'identifiant public est **`MPF-`, définitivement**.

L'identifiant n'est pas la marque : c'est une référence stable, dictable au
téléphone, qui doit survivre à tout changement de nom, de domaine ou
d'habillage. Le figer sur l'état effectivement servi évite une migration de
renommage, des redirections permanentes et une rupture des liens déjà
partagés — pour un bénéfice qui aurait été purement cosmétique.

Le préfixe `DEMO-` reste réservé au jeu de démonstration de `seed/dev/`, ce
qui rend un événement inventé reconnaissable à l'identifiant seul.

## Conséquences

- FR-067 et FR-068 (carte de partage, version imprimable) peuvent embarquer
  les URL d'événement sans risque de les voir invalidées.
- Le paramètre `prefix` de `fire.generate_public_id` demeure — le figement est
  une décision, pas une contrainte technique. Son comment en base, qui annonce
  un préfixe « configurable tant que la marque n'est pas arrêtée », est devenu
  faux ; il sera corrigé par la prochaine migration touchant cette fonction,
  en la référençant par sa signature complète (discipline du §15 du plan),
  plutôt que par une migration dédiée sans bénéfice public.
- La décision §8.4 sort de la liste des décisions ouvertes ; il en reste deux
  (§8.3 validation humaine, §8.5 première erreur publique).

## Alternatives écartées

**Changer de préfixe maintenant.** C'était la dernière fenêtre — avant FR-067.
Écartée : le coût est réel (migration renommant tous les `public_id`,
redirections 308 permanentes par la table d'alias, reconstruction des
snapshots) et croît chaque jour, alors qu'aucun élément de marque ne l'exige.

**Reporter.** Chaque jour de catalogue en ligne figeait `MPF-` un peu plus,
sans trace. Un figement de fait sans décision écrite est la pire des issues :
le même état final, moins la possibilité de dire pourquoi.
