"""Applique les fichiers de `supabase/seed/` à la base configurée.

Usage :
    micromamba run -n mapfeux-geo python scripts/apply-seed.py
    micromamba run -n mapfeux-geo python scripts/apply-seed.py --dev

Les migrations construisent le schéma ; ce script y verse les données de
référence — registre des sources et territoires d'amorçage. Les deux fichiers
sont idempotents (`on conflict do nothing`) et peuvent être rejoués.

`--dev` ajoute les fixtures de `supabase/seed/dev/`, qui contiennent des
observations inventées destinées au développement. Elles exigent un drapeau
explicite : un jeu de détections fictives affiché sans distinction dans une
commune réelle serait exactement la désinformation que le cahier §2.4 cherche à
éviter. **Ne jamais employer `--dev` sur la base de production.**

La chaîne de connexion est lue depuis `services/geo-worker/.env`, qui n'est
jamais versionné. Aucune valeur n'est affichée.
"""

from __future__ import annotations

import pathlib
import sys

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SEED_DIR = ROOT / "supabase" / "seed"
DEV_SEED_DIR = SEED_DIR / "dev"


def read_dsn() -> str:
    return dsn_from_env_file(ENV_FILE)


def main(argv: list[str]) -> None:
    include_dev = "--dev" in argv

    seeds = sorted(SEED_DIR.glob("*.sql"))
    if not seeds:
        sys.exit(f"Aucun fichier de seed dans {SEED_DIR}")

    if include_dev:
        dev_seeds = sorted(DEV_SEED_DIR.glob("*.sql"))
        if not dev_seeds:
            sys.exit(f"Aucune fixture de développement dans {DEV_SEED_DIR}")
        print("--dev : fixtures de développement incluses. Jamais en production.\n")
        seeds += dev_seeds

    try:
        conn = psycopg.connect(read_dsn(), connect_timeout=30)
    except psycopg.OperationalError as exc:
        sys.exit(
            f"Connexion impossible : {exc}\n"
            "Vérifier DATABASE_URL dans services/geo-worker/.env. Les caractères "
            "réservés du mot de passe doivent y être encodés en pourcent : "
            "@ devient %40."
        )

    with conn:
        for seed in seeds:
            with conn.cursor() as cur:
                cur.execute(seed.read_text(encoding="utf-8"))
            conn.commit()
            print(f"appliqué : {seed.name}")

        with conn.cursor() as cur:
            print()
            for label, query in (
                ("sources", "select count(*) from ingest.data_sources"),
                ("territoires", "select count(*) from app.territories"),
                ("communes", "select count(*) from geo.municipalities"),
                ("événements", "select count(*) from fire.events"),
                ("détections", "select count(*) from fire.detections"),
            ):
                cur.execute(query)
                row = cur.fetchone()
                print(f"  {label:<14} {'?' if row is None else row[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
