#!/usr/bin/env python3
"""Engendre les unités systemd des tâches MapFeux depuis `ops/tasks.json`.

Usage :
    generate-units.py [--out /etc/systemd/system] [--root /opt/mapfeux] [--user mapfeux]

Une paire par tâche — `mapfeux-<unit>.service` (oneshot) et
`mapfeux-<unit>.timer` — écrite telle quelle, écrasée si elle existe :
rejouable après toute retouche du registre. `--out` vers un répertoire
quelconque permet de relire ce qui serait écrit sans toucher au système.

Référence : stratégie §8.1, retranché le 13 septembre 2026.

## Ce que systemd apporte, et qu'on n'a plus à écrire

- **pas de chevauchement** : une minuterie qui tire pendant que le service
  est encore actif ne relance rien — l'équivalent de l'`IgnoreNew` du
  planificateur Windows, sans réglage ;
- **rattrapage** (`Persistent=true`) : une passe manquée pendant un arrêt
  part au redémarrage plutôt que d'attendre la suivante ;
- **journal** : la sortie va dans journald, `journalctl -u mapfeux-radar`,
  avec rotation et horodatage. Le fichier `logs/` du poste Windows n'a pas
  d'équivalent ici parce qu'il n'en a pas besoin ;
- **limite de temps** (`TimeoutStartSec`) : au-delà, le processus est tué.
  Aucun `finally` ne s'exécute alors ; le verrou d'exclusion tombe avec la
  session PostgreSQL, la file en base reprend à la passe suivante.

Les heures sont en **UTC**, explicitement, dans chaque `OnCalendar` : les
crons GitHub Actions remplacés l'étaient, et une minuterie ne doit pas
changer d'heure parce que la machine a changé de fuseau.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REGISTRY = HERE.parent / "tasks.json"


def on_calendar(schedule: dict) -> str:
    """Traduit une entrée `schedule` du registre en expression `OnCalendar`."""
    kind = schedule["kind"]
    if kind == "daily":
        hours, minutes = schedule["at_utc"].split(":")
        return f"*-*-* {int(hours):02d}:{int(minutes):02d}:00 UTC"
    if kind == "every":
        every = int(schedule["minutes"])
        minute = int(schedule.get("minute", 0))
        if every < 60:
            if 60 % every != 0:
                raise ValueError(f"un intervalle sous l'heure doit diviser 60 : {every}")
            return f"*-*-* *:0/{every}:00 UTC"
        if every % 60 != 0:
            raise ValueError(f"un intervalle au-delà de l'heure doit être un multiple de 60 : {every}")
        hours = every // 60
        hour_expr = "*" if hours == 1 else f"0/{hours}"
        return f"*-*-* {hour_expr}:{minute:02d}:00 UTC"
    raise ValueError(f"cadence inconnue : {kind}")


def service_unit(task: dict, root: str, user: str) -> str:
    return f"""[Unit]
Description=MapFeux — {task['description']}
Documentation=https://github.com/emifrog/mapfeux/tree/main/ops/vps
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={user}
WorkingDirectory={root}
ExecStart={root}/ops/vps/run-task.sh {task['name']}
TimeoutStartSec={int(task['time_limit_min'])}min
# L'ingestion n'a pas à concurrencer le système pour le processeur.
Nice=10
"""


def timer_unit(task: dict) -> str:
    return f"""[Unit]
Description=Déclencheur MapFeux — {task['name']}

[Timer]
OnCalendar={on_calendar(task['schedule'])}
Persistent=true
AccuracySec=30s
Unit=mapfeux-{task['unit']}.service

[Install]
WantedBy=timers.target
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="/etc/systemd/system", help="répertoire des unités")
    parser.add_argument("--root", default="/opt/mapfeux", help="racine du dépôt sur la machine")
    parser.add_argument("--user", default="mapfeux", help="compte d'exécution")
    args = parser.parse_args(argv)

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for task in registry["tasks"]:
        stem = f"mapfeux-{task['unit']}"
        (out / f"{stem}.service").write_text(service_unit(task, args.root, args.user), encoding="utf-8")
        (out / f"{stem}.timer").write_text(timer_unit(task), encoding="utf-8")
        written.append(stem)
        print(f"{stem:<24} {on_calendar(task['schedule'])}")

    print(f"\n{len(written)} paires écrites dans {out}")
    print("timers : " + " ".join(f"{stem}.timer" for stem in written))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
