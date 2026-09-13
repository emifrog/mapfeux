#!/usr/bin/env bash
# État des minuteries MapFeux : prochaine échéance, dernière passe, résultat.
#
# Ce que systemd sait — pas ce que la base sait. La trace durable d'une
# passe est `ingest.import_runs` ; ici on lit le déclencheur, pour
# distinguer « la tâche n'est pas partie » de « la tâche est partie et n'a
# rien trouvé ».

set -euo pipefail

echo "== minuteries =="
systemctl list-timers --all 'mapfeux-*' --no-pager

echo
echo "== dernière passe par service =="
printf '%-26s %-10s %-6s %s\n' "service" "résultat" "code" "fin"
for unit in $(systemctl list-units --all 'mapfeux-*.service' --no-legend --plain | awk '{print $1}'); do
  read -r result status stamp < <(systemctl show "$unit" \
    -p Result -p ExecMainStatus -p ExecMainExitTimestamp --value | paste -sd' ')
  printf '%-26s %-10s %-6s %s\n' "$unit" "${result:-—}" "${status:-—}" "${stamp:-jamais}"
done

echo
echo "journal d'une tâche : journalctl -u mapfeux-radar -n 40"
