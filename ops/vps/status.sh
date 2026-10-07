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
  # Une propriété par appel : `systemctl show` rend les propriétés dans son
  # ordre à lui, pas dans celui des `-p`, et l'horodatage contient des
  # espaces — lu en une ligne, le code de sortie recevait le jour de la
  # semaine (vu le 7 octobre 2026, première passe radar du VPS).
  result=$(systemctl show "$unit" -p Result --value)
  status=$(systemctl show "$unit" -p ExecMainStatus --value)
  stamp=$(systemctl show "$unit" -p ExecMainExitTimestamp --value)
  printf '%-26s %-10s %-6s %s\n' "$unit" "${result:-—}" "${status:-—}" "${stamp:-jamais}"
done

echo
echo "journal d'une tâche : journalctl -u mapfeux-radar -n 40"
