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

Le script est **rejouable** : c'est aussi la mise à jour (`git pull`,
environnement, unités), après tout changement du dépôt ou de
`ops/tasks.json`.

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

## Bascule depuis le poste Windows

Les deux déclencheurs ne doivent pas tourner ensemble : le verrou en base
empêche deux passes simultanées, pas deux passes consécutives, et la
cadence mesurée n'aurait plus de sens.

1. Sur le poste, **désactiver** sans retirer :
   `Get-ScheduledTask -TaskPath '\MapFeux\' | Disable-ScheduledTask`
2. Installer et vérifier sur le VPS (ci-dessus).
3. Après sept jours de cadence tenue — la même mesure que celle qui a
   condamné GitHub Actions —, retirer les tâches Windows :
   `ops\windows\unregister-tasks.ps1`.

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
