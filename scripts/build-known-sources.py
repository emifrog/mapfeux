"""Dérive le registre des sources statiques et le charge en base.

Usage :
    micromamba run -n mapfeux-geo python scripts/build-known-sources.py
    micromamba run -n mapfeux-geo python scripts/build-known-sources.py --cible calibration
    micromamba run -n mapfeux-geo python scripts/build-known-sources.py --cible production

Référence : cahier §13.11, FR-035 et FR-036 ; plan J10.

Sans `--cible`, la dérivation tourne à blanc : bilan et compte rendu JSON,
aucune écriture en base — de quoi juger les seuils avant d'engager. Le
chargement est un upsert par `source_key` : rejouer met à jour, ne duplique
pas, et ne réactive jamais une source qu'un administrateur a désactivée.

Après chargement, les détections historiques proches sont classées
(`mark_known_thermal_sources`, FR-036) — classées, jamais supprimées. Le
regroupement, lui, ignore les détections classées : c'est le masque.
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import DsnError, calibration_dsn, dsn_from_env_file, dsn_target
from geo_worker.pipelines.detections import mark_known_thermal_sources
from geo_worker.static_sources import MASK_VERSION, StaticSource, derive_static_sources

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
DEFAULT_CORPUS = ROOT / "data" / "firms" / "derive" / "firms_france_viirs_2012-2026.parquet"
REPORT_PATH = ROOT / "data" / "firms" / "derive" / f"{MASK_VERSION}.json"

#: Le classement rétroactif couvre tout l'historique importable.
BACKFILL_SINCE = datetime(2012, 1, 1, tzinfo=UTC)

_UPSERT = """
insert into fire.known_thermal_sources
  (source_key, name, category, location, match_radius_m, notes, is_active)
values (
  %(source_key)s, %(name)s, 'other',
  extensions.st_setsrid(extensions.st_makepoint(%(lon)s, %(lat)s), 4326),
  %(radius)s, %(notes)s, true
)
on conflict (source_key) do update set
  name = excluded.name,
  location = excluded.location,
  match_radius_m = excluded.match_radius_m,
  notes = excluded.notes
-- is_active volontairement absent : une désactivation administrative est une
-- décision humaine, qu'un rejeu de dérivation n'a pas le droit de défaire.
"""


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def resolve_dsn(target: str) -> str:
    try:
        if target == "calibration":
            return calibration_dsn(ENV_FILE)
        return dsn_from_env_file(ENV_FILE)
    except DsnError as exc:
        sys.exit(str(exc))


def load_registry(conn: psycopg.Connection[Any], sources: list[StaticSource]) -> None:
    with conn.cursor() as cur:
        for source in sources:
            cur.execute(
                _UPSERT,
                {
                    "source_key": source.source_key,
                    "name": source.name,
                    "lon": source.longitude,
                    "lat": source.latitude,
                    "radius": source.match_radius_m,
                    "notes": (
                        f"Dérivée du corpus FIRMS 2012-2026 : {source.detection_count} "
                        f"détections sur {source.month_count} mois "
                        f"({source.first_seen} → {source.last_seen}). "
                        "Catégorie à préciser éditorialement."
                    ),
                },
            )
    conn.commit()


def main(argv: list[str]) -> int:
    corpus_path = pathlib.Path(parse_option(argv, "--corpus") or DEFAULT_CORPUS)
    target = parse_option(argv, "--cible")
    if target not in (None, "calibration", "production"):
        sys.exit("--cible attend calibration ou production.")

    frame = pd.read_parquet(corpus_path)
    print(f"corpus  : {corpus_path.name} — {len(frame)} lignes")

    sources, stats = derive_static_sources(frame)
    print(f"masque  : {MASK_VERSION}\n")
    print(f"  détections type 2   : {stats['detections_type2']}")
    print(f"  zones candidates    : {stats['zones_candidates']}")
    print(f"  sources retenues    : {stats['sources_retenues']}")
    print(
        f"  couverture          : {stats['detections_couvertes']} détections "
        f"({stats['couverture_pct']} %)"
    )
    print(f"  empreinte           : {stats['empreinte']}")

    REPORT_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\ncompte rendu : {REPORT_PATH.relative_to(ROOT).as_posix()}")

    if target is None:
        print("\nDérivation à blanc : aucune écriture en base (--cible pour charger).")
        return 0

    dsn = resolve_dsn(target)
    host, port, database = dsn_target(dsn)
    print(f"\ncible   : {host}:{port}/{database} ({target})")

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        conn.execute("set statement_timeout = '10min'")
        load_registry(conn, sources)
        print(f"registre : {len(sources)} source(s) posée(s) ou mise(s) à jour")

        marked = mark_known_thermal_sources(conn, since=BACKFILL_SINCE)
        conn.commit()
        print(f"classées : {marked} détection(s) rattachée(s) à une source connue")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
