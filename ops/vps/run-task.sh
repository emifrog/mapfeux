#!/usr/bin/env bash
# Exécute une tâche MapFeux du registre `ops/tasks.json`.
#
# Point d'entrée unique des minuteries systemd (stratégie §8.1). Chaque
# script tourne dans l'environnement micromamba `mapfeux-geo`, depuis la
# racine du dépôt ; la sortie va au journal de l'unité. Une tâche à
# plusieurs scripts — CAMS : import puis dérivation — s'arrête au premier
# échec, et le code de sortie est le sien.
#
# Les scripts lisent eux-mêmes `services/geo-worker/.env` par un chemin
# absolu depuis leur propre emplacement ; le répertoire courant ne leur
# importe pas, on le pose quand même pour les artefacts relatifs.
#
# Usage : run-task.sh <Nom>   (Ingestion, Radar, Prefectures, …)

set -euo pipefail

TASK="${1:-}"
if [[ -z "$TASK" ]]; then
  echo "usage : $0 <Nom de tâche> — voir ops/tasks.json" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
REGISTRY="$ROOT/ops/tasks.json"

# micromamba vit dans le dépôt lui-même, hors de tout profil utilisateur :
# la tâche tourne sous un compte système sans shell ni environnement.
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$ROOT/.micromamba}"
MICROMAMBA="${MICROMAMBA:-$MAMBA_ROOT_PREFIX/bin/micromamba}"
if [[ ! -x "$MICROMAMBA" ]]; then
  echo "micromamba introuvable : $MICROMAMBA — lancer ops/vps/install.sh" >&2
  exit 3
fi

# Python en UTF-8 quoi qu'il arrive : le journal est fait pour être lu.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

# Les scripts de la tâche, un par ligne, lus du registre par le python du
# système — la bibliothèque standard suffit, et l'environnement conda n'a
# pas à être prêt pour lire un JSON.
mapfile -t SCRIPTS < <(python3 - "$REGISTRY" "$TASK" <<'PY'
import json, sys
registry = json.load(open(sys.argv[1], encoding="utf-8"))
for task in registry["tasks"]:
    if task["name"] == sys.argv[2]:
        print("\n".join(task["scripts"]))
        break
else:
    sys.exit(f"tâche inconnue : {sys.argv[2]}")
PY
)

cd "$ROOT"
echo "=== $TASK : début ==="
START=$(date +%s)
for script in "${SCRIPTS[@]}"; do
  echo "> $script"
  if ! "$MICROMAMBA" run -n mapfeux-geo python "$ROOT/$script"; then
    code=$?
    echo "< $script : code $code"
    echo "=== $TASK : fin en échec, code $code, $(( $(date +%s) - START )) s ==="
    exit "$code"
  fi
  echo "< $script : code 0"
done
echo "=== $TASK : fin, code 0, $(( $(date +%s) - START )) s ==="
