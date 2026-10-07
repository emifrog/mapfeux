# Le déclencheur sur un VPS

Référence : stratégie §8.1, retranché le 13 septembre 2026. Ce dossier
remplace le planificateur Windows du poste de développement (`ops/windows`,
transitoire) par des minuteries systemd sur une machine qui reste allumée.

Ce qui vit ici est le **déclencheur** seulement. La file de tâches, le
verrou d'exclusion et l'idempotence vivent en base ; les scripts sont ceux
de `scripts/` ; le registre des cadences est `ops/tasks.json`, commun aux
deux déclencheurs.

## Ce qu'il faut chez Hostinger

- Un VPS **KVM 1** suffit largement : une passe complète tient en quelques
  secondes, la dérivation CAMS quotidienne en une minute. Choisir l'image
  **Ubuntu 24.04** nue, sans panneau ni Docker préinstallé.
- **IPv6** : l'activer dans le panneau si l'option existe. La connexion
  directe à Supabase ne résout qu'en IPv6 ; sans lui, on passe par le pooler
  en mode session — `install.sh` teste et vous le dit, ce n'est pas
  bloquant.
- Une **clé SSH** posée à la création, et le mot de passe root désactivé
  ensuite. Rien ici n'a besoin d'un mot de passe.
- Un **dépôt joignable** : s'il est privé, une clé de déploiement en lecture
  seule sur GitHub, et `MAPFEUX_REPO=git@github.com:emifrog/mapfeux.git`.

## Installation

Une fois connecté en root :

```bash
curl -fsSL https://raw.githubusercontent.com/emifrog/mapfeux/main/ops/vps/install.sh | bash
```

Le script s'arrête une première fois, exprès : il vient de créer
`/opt/mapfeux/services/geo-worker/.env` depuis `env.template`, **vide de
secrets**. Remplissez-le — les valeurs sont celles des secrets GitHub du
même nom, `DATABASE_URL` étant celle d'`INGESTION_DATABASE_URL`, le rôle
`mapfeux_ingest` et non `postgres` — puis relancez la même commande. La
seconde fois, il va au bout : environnement micromamba, unités systemd,
minuteries actives, état affiché.

Le script est **rejouable** : c'est aussi la mise à jour. L'ordre à tenir
est à la section suivante.

## Mettre à jour — l'ordre des gestes

Le VPS exécute `/opt/mapfeux` tel qu'il était au dernier `install.sh`. Un
push sur `main` ne l'atteint pas : le site, lui, se déploie seul sur Vercel
au push, le worker non. Déployer un changement du worker est donc un geste,
et il a un ordre :

1. **La migration d'abord, depuis le poste** — `pnpm db:push`, avec la
   chaîne d'administration, qui ne va jamais sur le VPS. Entre ce moment et
   l'étape 3, le code **ancien** tourne sur le VPS contre la base
   **nouvelle** : une migration doit être additive — ajouter une colonne,
   une fonction, une vue — et ne jamais retirer ni renommer ce que les
   scripts en place appellent. Sinon, migration et étape 3 dans la même
   séance, sans quitter le clavier entre les deux.
2. **Commit, push, CI verte.** La CI rejoue toutes les migrations sur une
   base vierge, puis une passe complète sous `mapfeux_ingest`, depuis le
   verrou conda — la même pile que le VPS, linux-64.
3. **Sur le VPS, rejouer `install.sh`** (la commande d'installation,
   ci-dessus). Il tire `main`, ne recrée l'environnement conda **que si
   `conda-lock.yml` a changé** — l'empreinte du verrou est gardée dans
   l'environnement —, régénère les unités depuis `ops/tasks.json`, et
   affiche l'état. Quelques secondes quand le verrou n'a pas bougé.
4. **Vérifier** : `status.sh`, le journal de la première passe qui suit,
   et la base (section suivante).

Une passe en cours pendant l'étape 3 finit sur l'ancien code — `git pull`
remplace les fichiers, pas le processus — ; la suivante part sur le nouveau.

## La machine

- **Mises à jour de sécurité** : `install.sh` pose `unattended-upgrades`,
  mises à jour quotidiennes, et le **redémarrage automatique à 04:30**
  (heure de la machine) quand un noyau le demande — sans lui, le noyau ne
  changerait jamais. Une passe tuée par le redémarrage reprend à la
  suivante ; les minuteries rattrapent (`Persistent=true`). `status.sh`
  dit si un redémarrage attend.
- **Rien d'unique dessus, sauf le `.env`.** Le dépôt, l'environnement, les
  unités se refont en dix minutes par `install.sh` sur une machine neuve ;
  le `.env` est la seule chose à ressaisir — depuis les secrets GitHub du
  même nom. C'est le plan de reprise, et il n'y a pas de sauvegarde à
  faire.
- **Rien n'écoute** : aucun port ouvert par MapFeux, pas de service web.
  Clé SSH seule, mot de passe root coupé.
- **Les secrets existent en trois exemplaires** : ce `.env`, celui du
  poste (avec la chaîne d'administration et `ENVIRONMENT=local`), et les
  secrets GitHub. Faire tourner une clé, c'est les trois.

## Vérifier

Sur la machine :

```bash
/opt/mapfeux/ops/vps/status.sh
journalctl -u mapfeux-radar -n 40
journalctl -u mapfeux-ingestion --since "1 hour ago"
```

Depuis n'importe où, la preuve qui compte est **en base** : les lignes
d'`ingest.import_runs` postérieures à l'installation, et le champ
`environment: production` dans leurs journaux — le poste de développement
écrit `local`. Puis `/statut` sur le site, qui doit cesser de dire
« Retardée » sur FIRMS et le radar.

## Tâches réservées au poste

Une tâche du registre peut porter `"only_on": "poste"`, avec son motif
dans `only_on_reason`. Le kit VPS ne lui pose aucune unité, et retire la
minuterie si un passage antérieur l'avait posée ; le planificateur Windows,
lui, l'enregistre comme les autres.

C'est le cas des **préfectures** depuis le 7 octobre 2026 : leurs sites
ferment la connexion aux adresses de centres de données — `ENHANCE_YOUR_CALM`
en HTTP/2, réponse vide en HTTP/1.1, même refus depuis un runner GitHub —,
et seule une adresse résidentielle les lit. Sur le poste, une seule tâche
reste donc active : `Enable-ScheduledTask -TaskPath '\MapFeux\' -TaskName
MapFeux-Prefectures`. Retirer l'exception du registre remet la minuterie
sur le VPS au passage suivant d'`install.sh`.

## Bascule depuis le poste Windows

Les deux déclencheurs ne doivent pas tourner ensemble : le verrou en base
empêche deux passes simultanées, pas deux passes consécutives, et la
cadence mesurée n'aurait plus de sens.

1. Sur le poste, **désactiver** sans retirer :
   `Get-ScheduledTask -TaskPath '\MapFeux\' | Disable-ScheduledTask`
2. Installer et vérifier sur le VPS (ci-dessus).
3. Après sept jours de cadence tenue — la même mesure que celle qui a
   condamné GitHub Actions —, retirer les tâches Windows sauf celle qui
   reste au poste : `ops\windows\unregister-tasks.ps1 -Except Prefectures`
   (`-WhatIf` d'abord, pour lire ce qui partirait).

En cas de panne du VPS, l'inverse : `Enable-ScheduledTask` sur le poste, ou
le `workflow_dispatch` de chaque workflow GitHub pour une passe isolée.

## Retirer

```bash
systemctl disable --now 'mapfeux-*.timer'
rm /etc/systemd/system/mapfeux-*.{service,timer}
systemctl daemon-reload
```

Le dépôt, l'environnement et le `.env` restent en place ; les supprimer est
un geste distinct, à faire en connaissance de cause — le `.env` contient
les secrets.
