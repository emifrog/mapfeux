# Polices de la carte de partage (FR-067)

WOFF v1 recopiés depuis `@fontsource/instrument-sans` et
`@fontsource/ibm-plex-mono` (sous-ensemble latin — les accents français y
sont), licences OFL jointes.

Pourquoi des copies plutôt que node_modules : le moteur de la carte Open
Graph (`opengraph-image.tsx`) lit ses polices par `readFile`, et le traçage
de fichiers du déploiement n'embarque que ce qu'il peut prouver — un chemin
**littéral** vers une ressource du projet. La première version lisait
node_modules par des chemins composés : parfaite en local, 500 en
production, les fichiers n'ayant jamais été empaquetés. Motif documenté par
Next (« Using Node.js runtime with local assets »).

Mise à jour : recopier depuis les paquets fontsource, licences comprises.
