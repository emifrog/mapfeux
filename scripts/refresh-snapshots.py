"""Reconstruit les snapshots publics des événements.

Usage :
    micromamba run -n mapfeux-geo python scripts/refresh-snapshots.py
    micromamba run -n mapfeux-geo python scripts/refresh-snapshots.py --stale 30

Référence : cahier §21.5.

En exploitation, le rafraîchissement est déclenché par le pipeline qui modifie
l'événement. Ce script est le filet : il rattrape les snapshots manquants ou
périmés, par exemple après une panne du worker ou une correction manuelle.

`--stale N` limite le travail aux snapshots plus vieux que N minutes ou absents.
Sans argument, tous les événements publiables sont reconstruits.
"""

from __future__ import annotations

import pathlib
import sys
from urllib.parse import quote

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def read_dsn() -> str:
    """Lit DATABASE_URL, en réparant un `@` non encodé dans le mot de passe."""
    if not ENV_FILE.exists():
        sys.exit(f"Fichier introuvable : {ENV_FILE}")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("DATABASE_URL="):
            continue
        dsn = line.split("=", 1)[1].strip()
        scheme, sep, rest = dsn.partition("://")
        if sep == "":
            return dsn
        authority, slash, path = rest.partition("/")
        if authority.count("@") <= 1:
            return dsn
        userinfo, _, hostpart = authority.rpartition("@")
        user, _, password = userinfo.partition(":")
        return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}{slash}{path}"

    sys.exit(f"DATABASE_URL absente de {ENV_FILE}")


def parse_stale_minutes(argv: list[str]) -> int | None:
    if "--stale" not in argv:
        return None
    index = argv.index("--stale")
    if index + 1 >= len(argv):
        sys.exit("--stale attend un nombre de minutes.")
    try:
        return int(argv[index + 1])
    except ValueError:
        sys.exit(f"Valeur --stale invalide : {argv[index + 1]!r}")


def main(argv: list[str]) -> None:
    stale_minutes = parse_stale_minutes(argv)

    select_sql = """
        select e.id, e.public_id
        from fire.events e
        left join fire.event_snapshots s on s.event_id = e.id
        where e.freshness_status <> 'hidden'
    """
    params: dict[str, object] = {}
    if stale_minutes is not None:
        select_sql += """
          and (
            s.event_id is null
            or s.generated_at < now() - make_interval(mins => %(stale)s)
          )
        """
        params["stale"] = stale_minutes
    select_sql += " order by e.last_detected_at desc"

    try:
        conn = psycopg.connect(read_dsn(), connect_timeout=30)
    except psycopg.OperationalError as exc:
        sys.exit(f"Connexion impossible : {exc}")

    refreshed = 0
    skipped = 0

    with conn, conn.cursor() as cur:
        cur.execute(select_sql, params)
        events = cur.fetchall()

        for event_id, public_id in events:
            # Un événement par transaction : l'échec de l'un ne fait pas perdre
            # les snapshots reconstruits avant lui.
            cur.execute("select fire.refresh_event_snapshot(%s)", (event_id,))
            row = cur.fetchone()
            generated = None if row is None else row[0]
            conn.commit()

            if generated is None:
                skipped += 1
                print(f"  ignoré  : {public_id}")
            else:
                refreshed += 1
                print(f"  publié  : {public_id}")

    print(f"\n{refreshed} snapshot(s) reconstruit(s), {skipped} ignoré(s).")


if __name__ == "__main__":
    main(sys.argv[1:])
