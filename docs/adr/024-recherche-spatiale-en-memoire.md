# ADR-024 — Recherche des candidats de regroupement en mémoire

**Statut** : accepté
**Date** : 28 juillet 2026
**Cahier** : §17.2, §17.6
**Remplace** : rien. Complète ADR-006 (algorithme de regroupement), à rédiger.

## Contexte

Le regroupement traite les détections dans un ordre chronologique strict et
cherche, pour chacune, les événements dont un membre se trouve à portée. La
première implémentation posait cette question à PostGIS, détection par
détection : une requête `ST_DWithin` puis `min(ST_Distance)` sur le type
`geography`.

Sur le corpus de calibration — 939 détections, 90 jours du Var et des
Alpes-Maritimes — cela représentait près de trois mille allers-retours vers un
projet Supabase hébergé, et **120 secondes** pour un recalcul complet. Le profil
était sans ambiguïté : le temps passait en attente réseau, pas en calcul.

Deux besoins rendaient ce coût bloquant :

1. **La calibration.** Comparer des jeux de paramètres suppose de rejouer le
   corpus entier pour chacun. À deux minutes le jeu, un balayage croisé de cent
   douze combinaisons demanderait près de quatre heures — en pratique, on ne le
   fait pas, et on règle l'algorithme sur des variations isolées qui ne montrent
   pas les interactions.
2. **L'ouverture nationale.** Le corpus est aujourd'hui celui de deux
   départements. À l'échelle du pays, le coût par détection est le même mais le
   nombre de détections est d'un autre ordre.

## Décision

La recherche des candidats se fait **en mémoire**, dans le worker.

Les positions des détections sont chargées une fois par passe et indexées dans
un arbre k-d construit sur les coordonnées cartésiennes de la sphère unité. La
présélection par corde ne peut pas manquer un voisin, la corde croissant avec
l'angle au centre. La distance effectivement retenue est ensuite calculée sur
l'ellipsoïde WGS84 avec pyproj — **la même grandeur que `ST_Distance` sur le
type `geography`**, à la précision du millimètre près. L'approximation sphérique
ne sert qu'à écarter ; elle n'entre jamais dans un résultat.

L'index est statique alors que l'appartenance aux événements évolue au fil de la
boucle. C'est cette dissociation qui rend le procédé applicable à un traitement
séquentiel : une détection rattachée devient immédiatement visible pour les
suivantes, sans reconstruire quoi que ce soit.

Les écritures et le recalcul des agrégats sont groupés sur l'ensemble des
événements touchés, au lieu de trois requêtes par événement.

## Conséquences

**Le coût s'effondre** : recalcul complet de 120,2 s à 1,8 s, soit un facteur
67. Le balayage croisé devient une opération de quelques minutes.

**Une seconde implémentation de la distance géodésique existe désormais**, à
côté de celle de PostGIS. C'est le vrai prix de cette décision, et il n'est pas
nul : deux bibliothèques peuvent diverger, et une divergence silencieuse sur une
distance change des rattachements sans rien signaler.

Trois garde-fous l'encadrent :

1. `scripts/verify-clustering.py` compare l'**empreinte du partitionnement**
   avant et après recalcul. Le passage en mémoire a été validé ainsi : même
   empreinte `66849fb15a6445ff`, mêmes 124 événements, mêmes 939 membres, mêmes
   123 créations et 809 rattachements. Sans cette égalité, la décision aurait
   été refusée.
2. `tests/test_spatial.py` compare l'index à une recherche exhaustive sur une
   grille, et vérifie que la marge de présélection ne perd pas un voisin situé
   juste sous la limite, à trois latitudes et quatre azimuts.
3. Le même script établit que le regroupement **par tranches** donne le même
   résultat qu'en bloc — propriété nécessaire puisque la production traitera
   quelques détections toutes les dix minutes alors que la calibration en rejoue
   une saison.

**La logique de décision n'a pas bougé.** `attachment_score`,
`spatial_window_m`, `confidence_score` et les seuils restent des fonctions pures
versionnées et testées unitairement ; seule la façon de trouver les candidats a
changé. C'est ce qui distingue cette décision d'une réécriture de l'algorithme
en PL/pgSQL, qui aurait au contraire déplacé la logique hors du code testé.

**Le worker doit tenir le corpus en mémoire.** À l'échelle nationale, ce sera à
réexaminer : la parade est un découpage par emprise, déjà nécessaire pour
d'autres raisons, et dont ce même contrôle de tranches montre qu'il ne change
pas le résultat tant que le découpage suit le temps.

## Alternatives écartées

**Porter la boucle en PL/pgSQL.** Supprimait tous les allers-retours et gardait
la distance PostGIS, donc sans risque de divergence. Écartée parce qu'elle
aurait sorti la formule de score et les seuils du code testé unitairement, pour
les enfouir dans une fonction SQL — au prix, cette fois, d'une seconde
implémentation de ce qui compte vraiment.

**Grouper les requêtes de candidats par lots.** Impossible sans changer le
résultat : le rattachement d'une détection dépend de l'état laissé par la
précédente. La boucle est séquentielle par construction, et c'est cette
séquentialité qui la rend reproductible.

**Se contenter de la lenteur.** Tenable pour un pilote sur deux départements,
intenable pour la calibration : un banc qu'on ne lance pas est un banc qui ne
sert à rien, et les paramètres de regroupement seraient alors réglés à l'estime.
