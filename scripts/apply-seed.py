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
from urllib.parse import quote

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SEED_DIR = ROOT / "supabase" / "seed"
DEV_SEED_DIR = SEED_DIR / "dev"


def read_dsn() -> str:
    """Lit DATABASE_URL, en réparant le seul défaut courant : un `@` non encodé.

    Les mots de passe générés par Supabase contiennent fréquemment un `@`. Collé
    tel quel dans une URL, il déplace la séparation utilisateur/hôte et produit
    une erreur de résolution DNS trompeuse, qui fait chercher un problème réseau
    là où il n'y a qu'un problème de format.

    Le correctif est délibérément étroit : il n'agit que si la partie autorité
    contient plus d'une arobase. Encoder inconditionnellement produirait un
    double encodage sur une chaîne déjà correcte — `%40` deviendrait `%2540` —
    et l'authentification échouerait sans que la cause soit visible.
    """
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

        # Un nom d'hôte ne contient jamais d'arobase : la dernière sépare.
        userinfo, _, hostpart = authority.rpartition("@")
        user, _, password = userinfo.partition(":")
        print("DATABASE_URL : mot de passe encodé en pourcent pour cette connexion")
        return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}{slash}{path}"

    sys.exit(f"DATABASE_URL absente de {ENV_FILE}")


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
                print(f"  {label:<14} {cur.fetchone()[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
