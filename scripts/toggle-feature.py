"""Bascule un interrupteur de fonction — FR-106 et FR-155.

Usage :
    micromamba run -n mapfeux-geo python scripts/toggle-feature.py --liste
    micromamba run -n mapfeux-geo python scripts/toggle-feature.py \
        --fonction smoke_forecast --etat off --motif "vent aberrant sur le run de 06 h"
    micromamba run -n mapfeux-geo python scripts/toggle-feature.py \
        --fonction smoke_forecast --etat on --motif "run suivant sain, réactivation"
    micromamba run -n mapfeux-geo python scripts/toggle-feature.py \
        --fonction smoke_forecast --etat off --territoire var --motif "..."

Référence : cahier v2.1 §18.5 ; plan J8.

C'est le geste d'exploitation : une écriture en base, effective à l'instant,
sans déploiement. Le motif est obligatoire — un interrupteur sans motif est
une panne déguisée en décision — et chaque bascule passe au journal d'audit
avant d'être appliquée, dans la même transaction.
"""

from __future__ import annotations

import getpass
import json
import pathlib
import sys
from typing import Any

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def show_state(conn: psycopg.Connection[Any]) -> None:
    rows = conn.execute(
        """
        select s.feature, t.slug, s.is_enabled, s.reason, s.updated_at, s.updated_by
        from app.feature_switches s
        left join app.territories t on t.id = s.territory_id
        order by s.feature, t.slug nulls first
        """
    ).fetchall()
    if not rows:
        print("Aucun interrupteur posé : toutes les fonctions sont actives.")
        return
    for feature, slug, enabled, reason, updated_at, updated_by in rows:
        scope = "global" if slug is None else f"territoire {slug}"
        state = "actif" if enabled else "COUPÉ"
        print(f"{feature} [{scope}] : {state} — {reason}")
        print(f"    le {updated_at:%d/%m %H:%M} UTC par {updated_by}")


def main(argv: list[str]) -> int:
    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}\n")

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        if "--liste" in argv:
            show_state(conn)
            return 0

        feature = parse_option(argv, "--fonction")
        state = parse_option(argv, "--etat")
        reason = parse_option(argv, "--motif")
        territory_slug = parse_option(argv, "--territoire")

        if feature is None or state not in ("on", "off"):
            sys.exit("--fonction et --etat on|off sont requis (ou --liste).")
        if reason is None or reason.strip() == "":
            sys.exit("--motif est requis : un interrupteur sans motif est une panne déguisée.")

        territory_id = None
        if territory_slug is not None:
            row = conn.execute(
                "select id from app.territories where slug = %(slug)s",
                {"slug": territory_slug},
            ).fetchone()
            if row is None:
                sys.exit(f"Territoire inconnu : {territory_slug!r}")
            territory_id = row[0]

        is_enabled = state == "on"
        updated_by = f"exploitation — {getpass.getuser()}"
        scope = "global" if territory_slug is None else f"territoire {territory_slug}"

        with conn.cursor() as cur:
            # Le journal d'abord, la bascule ensuite, même transaction : une
            # coupure sans trace serait une panne déguisée en décision.
            cur.execute(
                """
                insert into audit.entries
                  (actor_type, actor_label, action, resource_type, resource_id,
                   after_state, reason)
                values
                  ('admin', %(actor)s, 'feature_switch.set', 'app.feature_switches',
                   %(resource)s, %(after)s, %(reason)s)
                """,
                {
                    "actor": updated_by,
                    "resource": f"{feature}/{scope}",
                    "after": json.dumps(
                        {"feature": feature, "scope": scope, "is_enabled": is_enabled},
                        ensure_ascii=False,
                    ),
                    "reason": reason,
                },
            )
            if territory_id is None:
                cur.execute(
                    """
                    insert into app.feature_switches
                      (feature, territory_id, is_enabled, reason, updated_by)
                    values (%(feature)s, null, %(enabled)s, %(reason)s, %(by)s)
                    on conflict (feature) where territory_id is null do update set
                      is_enabled = excluded.is_enabled,
                      reason = excluded.reason,
                      updated_by = excluded.updated_by
                    """,
                    {"feature": feature, "enabled": is_enabled, "reason": reason, "by": updated_by},
                )
            else:
                cur.execute(
                    """
                    insert into app.feature_switches
                      (feature, territory_id, is_enabled, reason, updated_by)
                    values (%(feature)s, %(territory)s, %(enabled)s, %(reason)s, %(by)s)
                    on conflict (feature, territory_id) where territory_id is not null
                    do update set
                      is_enabled = excluded.is_enabled,
                      reason = excluded.reason,
                      updated_by = excluded.updated_by
                    """,
                    {
                        "feature": feature,
                        "territory": territory_id,
                        "enabled": is_enabled,
                        "reason": reason,
                        "by": updated_by,
                    },
                )
        conn.commit()

        print(f"{feature} [{scope}] → {'actif' if is_enabled else 'COUPÉ'} (effet immédiat)\n")
        show_state(conn)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
