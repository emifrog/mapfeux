"""Applique les fichiers de `supabase/seed/` à la base configurée.

Usage :
    micromamba run -n mapfeux-geo python scripts/apply-seed.py

Les migrations construisent le schéma ; ce script y verse les données de
référence — registre des sources et territoires d'amorçage. Les deux fichiers
sont idempotents (`on conflict do nothing`) et peuvent être rejoués.

La chaîne de connexion est lue depuis `services/geo-worker/.env`, qui n'est
jamais versionné. Aucune valeur n'est affichée.
"""

from __future__ import annotations

import pathlib
import sys
from urllib.parse import quote

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SEED_DIR = ROOT / "supabase" / "seed"


def read_dsn() -> str:
    """Lit DATABASE_URL et encode le mot de passe si nécessaire.

    Les mots de passe générés par Supabase contiennent fréquemment des
    caractères réservés d'URL. Un `@` non encodé décale la séparation
    utilisateur/hôte et produit une erreur de résolution DNS trompeuse, qui
    donne l'impression d'un problème réseau plutôt que de format.
    """
    if not ENV_FILE.exists():
        sys.exit(f"Fichier introuvable : {ENV_FILE}")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("DATABASE_URL="):
            continue

        dsn = line.split("=", 1)[1].strip()
        scheme, sep, rest = dsn.partition("://")
        if sep == "" or "@" not in rest:
            return dsn

        # Un nom d'hôte ne contient jamais d'arobase : la dernière sépare.
        userinfo, _, hostpart = rest.rpartition("@")
        user, _, password = userinfo.partition(":")
        return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}"

    sys.exit(f"DATABASE_URL absente de {ENV_FILE}")


def main() -> None:
    seeds = sorted(SEED_DIR.glob("*.sql"))
    if not seeds:
        sys.exit(f"Aucun fichier de seed dans {SEED_DIR}")

    with psycopg.connect(read_dsn(), connect_timeout=30) as conn:
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
            ):
                cur.execute(query)
                print(f"  {label:<14} {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
