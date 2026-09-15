#!/usr/bin/env bash
# Installe — ou remet à jour — le déclencheur MapFeux sur un VPS Ubuntu.
#
# Stratégie §8.1, retranché le 13 septembre 2026 : le poste de développement
# ne peut pas rester la machine qui porte l'ingestion. Ce script pose tout ce
# qu'il faut sur une machine neuve, et se rejoue sans dommage sur une machine
# déjà installée — c'est ainsi qu'on met à jour.
#
# Usage, en root, sur Ubuntu 24.04 :
#     curl -fsSL https://raw.githubusercontent.com/emifrog/mapfeux/main/ops/vps/install.sh | bash
# ou, dépôt déjà cloné :
#     sudo ops/vps/install.sh
#
# Variables acceptées :
#     MAPFEUX_REPO   URL du dépôt (défaut : https://github.com/emifrog/mapfeux.git)
#     MAPFEUX_ROOT   racine d'installation (défaut : /opt/mapfeux)
#
# Ce que ce script ne fait PAS, et ne fera jamais : écrire un secret. Le
# fichier `.env` est à remplir à la main depuis `env.template` ; il s'arrête
# et le dit tant qu'il manque.

set -euo pipefail

REPO="${MAPFEUX_REPO:-https://github.com/emifrog/mapfeux.git}"
ROOT="${MAPFEUX_ROOT:-/opt/mapfeux}"
USER_NAME="mapfeux"
ENV_FILE="$ROOT/services/geo-worker/.env"

if [[ $EUID -ne 0 ]]; then
  echo "à lancer en root (sudo) : il crée un compte et des unités systemd" >&2
  exit 1
fi

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- Paquets système ----------------------------------------------------------
say "paquets système"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates bzip2 tzdata python3 >/dev/null

# --- Compte d'exécution -------------------------------------------------------
# Un compte système, sans shell ni mot de passe : il ne sert qu'à porter les
# tâches. Le dépôt lui appartient, rien d'autre.
say "compte $USER_NAME"
if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "/var/lib/$USER_NAME" \
    --shell /usr/sbin/nologin "$USER_NAME"
  echo "créé"
else
  echo "déjà présent"
fi

# --- Dépôt --------------------------------------------------------------------
say "dépôt dans $ROOT"
if [[ -d "$ROOT/.git" ]]; then
  git -C "$ROOT" pull --ff-only
else
  git clone --depth 1 "$REPO" "$ROOT"
fi

# --- micromamba, dans le dépôt lui-même ----------------------------------------
# Hors de tout profil utilisateur : le compte d'exécution n'a ni shell ni
# environnement, et une mise à jour du dépôt ne doit pas casser l'outil qui
# l'exécute.
say "micromamba"
export MAMBA_ROOT_PREFIX="$ROOT/.micromamba"
MICROMAMBA="$MAMBA_ROOT_PREFIX/bin/micromamba"
if [[ ! -x "$MICROMAMBA" ]]; then
  mkdir -p "$MAMBA_ROOT_PREFIX"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xj -C "$MAMBA_ROOT_PREFIX" bin/micromamba
  echo "installé"
else
  echo "déjà présent : $("$MICROMAMBA" --version)"
fi

# --- Environnement géospatial -------------------------------------------------
# `conda-lock.yml` porte toute la pile, dérivation raster comprise, **aux
# versions exactes** que la CI valide (linux-64) : une seule création, rien à
# ajouter par pip, et la même combinaison à chaque recréation. `environment.yml`
# reste la source, le verrou s'en régénère (voir son en-tête). Un verrou ne se
# met pas à jour en place : on recrée, ce qui remplace l'environnement existant.
say "environnement mapfeux-geo"
if [[ -d "$MAMBA_ROOT_PREFIX/envs/mapfeux-geo" ]]; then
  "$MICROMAMBA" create -y -q -n mapfeux-geo -f "$ROOT/services/geo-worker/conda-lock.yml"
  echo "recréé depuis le verrou"
else
  "$MICROMAMBA" create -y -q -n mapfeux-geo -f "$ROOT/services/geo-worker/conda-lock.yml"
  echo "créé depuis le verrou"
fi
"$MICROMAMBA" run -n mapfeux-geo python -c "import rasterio, psycopg, httpx; print('pile géospatiale : ok')"

chown -R "$USER_NAME:$USER_NAME" "$ROOT"

# --- Secrets : à la main, jamais par ce script ---------------------------------
say "fichier .env"
if [[ ! -f "$ENV_FILE" ]]; then
  install -o "$USER_NAME" -g "$USER_NAME" -m 600 "$ROOT/ops/vps/env.template" "$ENV_FILE"
  cat >&2 <<EOF

  $ENV_FILE vient d'être créé depuis le gabarit : il est VIDE de secrets.
  Remplissez-le (DATABASE_URL, clés FIRMS, Météo-France, Copernicus, Supabase)
  puis relancez ce script. Voir ops/vps/README.md.

EOF
  exit 4
fi
chmod 600 "$ENV_FILE"
chown "$USER_NAME:$USER_NAME" "$ENV_FILE"

# --- Connexion à la base : IPv6 ou pooler ? ------------------------------------
# La connexion directe Supabase ne résout qu'en IPv6. Si la machine n'en a
# pas, il faut le pooler en mode *session* (port 5432) — jamais le mode
# transaction (6543), qui casserait le verrou d'exclusion.
say "réseau"
DB_HOST="$(python3 - "$ENV_FILE" <<'PY'
import sys, re
from urllib.parse import urlparse
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("DATABASE_URL="):
        print(urlparse(line.split("=", 1)[1].strip().strip('"')).hostname or "")
        break
PY
)"
if [[ -n "$DB_HOST" ]]; then
  if getent ahostsv6 "$DB_HOST" >/dev/null 2>&1 && curl -6 -fsS --max-time 5 https://api64.ipify.org >/dev/null 2>&1; then
    echo "IPv6 sortant : oui — la connexion directe ($DB_HOST) convient"
  elif getent ahostsv4 "$DB_HOST" >/dev/null 2>&1; then
    echo "IPv6 sortant : non, mais $DB_HOST résout en IPv4 — pooler, bien"
  else
    echo "ATTENTION : pas d'IPv6 sortant et $DB_HOST ne résout pas en IPv4."
    echo "  Employer la chaîne du pooler en mode session (port 5432) dans DATABASE_URL."
  fi
fi

# --- Unités systemd -------------------------------------------------------------
say "unités systemd"
python3 "$ROOT/ops/vps/generate-units.py" --out /etc/systemd/system --root "$ROOT" --user "$USER_NAME"
chmod +x "$ROOT/ops/vps/run-task.sh" "$ROOT/ops/vps/status.sh"
systemctl daemon-reload
for unit in $(python3 -c "import json;print(' '.join('mapfeux-'+t['unit']+'.timer' for t in json.load(open('$ROOT/ops/tasks.json'))['tasks']))"); do
  systemctl enable --now "$unit" >/dev/null
done

say "état"
"$ROOT/ops/vps/status.sh"

cat <<EOF

Installé. Les minuteries sont actives ; la première passe de chacune part à
sa prochaine échéance. Vérifier dans quelques minutes :
    $ROOT/ops/vps/status.sh
    journalctl -u mapfeux-radar -n 30
EOF
