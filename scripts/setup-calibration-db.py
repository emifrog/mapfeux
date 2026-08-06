"""Monte le schéma complet sur la base de calibration.

Usage :
    micromamba run -n mapfeux-geo python scripts/setup-calibration-db.py
    micromamba run -n mapfeux-geo python scripts/setup-calibration-db.py --dry-run

Référence : cahier §24.2, ADR-014.

Applique les migrations dans l'ordre, puis le seed, sur la base désignée par
`CALIBRATION_DATABASE_URL`.

## Pourquoi ne pas passer par `supabase db push`

Le CLI pousse vers le **projet lié**. S'en servir ici demanderait de délier le
projet de production, pousser, puis relier — trois gestes dont le troisième
s'oublie. Un `pnpm db:push` lancé plus tard partirait alors vers la base de
calibration, ou pire, un `db:push` destiné à la calibration atteindrait la
production.

Appliquer le SQL directement supprime ce risque : la cible ne vient jamais d'un
état enregistré quelque part, mais d'une variable que le garde-fou compare à
`DATABASE_URL` et refuse si elle désigne la même base.

C'est exactement ce que fait la CI depuis toujours, à la boucle `psql` près.

## Ce que le script suppose

Un projet Supabase **neuf**. Les rôles `anon`, `authenticated`, `service_role`,
le schéma `auth` et le registre `storage.buckets` sont fournis par la
plateforme ; les migrations les tiennent pour acquis. Sur un PostgreSQL nu, il
faudrait le préambule que la CI applique — ce n'est pas le cas visé ici.
"""

from __future__ import annotations

import pathlib
import sys
import time

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import DsnError, calibration_dsn, dsn_target

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
MIGRATIONS = ROOT / "supabase" / "migrations"
SEED = ROOT / "supabase" / "seed"


def sql_files() -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Migrations puis seed, chacun trié par nom.

    L'ordre lexicographique des migrations est leur ordre chronologique : le
    préfixe est un horodatage à largeur fixe. Le seed vient après, et jamais
    avant — les migrations créent les tables qu'il remplit, et c'est ce qui fait
    qu'un `update` de migration sur une table encore vide ne touche rien.

    `glob` ne descend pas dans `seed/dev/`, et c'est voulu : le jeu de
    démonstration y vit. Charger des événements inventés sur la base qui sert à
    calibrer fausserait toutes les mesures, et rien ne les distinguerait ensuite
    des observations réelles dans les agrégats.
    """
    return (sorted(MIGRATIONS.glob("*.sql")), sorted(SEED.glob("*.sql")))


def apply_file(conn: psycopg.Connection[object], path: pathlib.Path) -> float:
    """Applique un fichier en une transaction. Retourne sa durée en secondes.

    Une transaction par fichier : un fichier qui échoue laisse la base dans
    l'état qui précédait, et le message dit lequel. Tout appliquer en une seule
    transaction rendrait le diagnostic muet sur le point de rupture.
    """
    started = time.monotonic()
    with conn.cursor() as cur:
        # Le SQL vient d'un fichier versionné du dépôt, jamais d'une entrée.
        cur.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    return time.monotonic() - started


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    try:
        dsn = calibration_dsn(ENV_FILE)
    except DsnError as exc:
        sys.exit(str(exc))

    host, port, database = dsn_target(dsn)
    migrations, seeds = sql_files()

    print(f"cible      : {host}:{port}/{database}")
    print(f"migrations : {len(migrations)}")
    print(f"seed       : {len(seeds)} fichier(s)")

    if dry_run:
        print("\n--dry-run : rien n'est appliqué.")
        for path in [*migrations, *seeds]:
            print(f"  {path.relative_to(ROOT).as_posix()}")
        return 0

    print(flush=True)
    started = time.monotonic()

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        for path in migrations:
            try:
                elapsed = apply_file(conn, path)
            except psycopg.Error as exc:
                conn.rollback()
                sys.exit(
                    f"\nÉchec sur {path.name} :\n  {str(exc).strip()}\n\n"
                    "La base est restée dans l'état qui précédait ce fichier."
                )
            print(f"  {path.name:<52} {elapsed:5.1f} s", flush=True)

        print()
        for path in seeds:
            try:
                elapsed = apply_file(conn, path)
            except psycopg.Error as exc:
                conn.rollback()
                sys.exit(f"\nÉchec sur le seed {path.name} :\n  {str(exc).strip()}")
            print(f"  {path.name:<52} {elapsed:5.1f} s", flush=True)

        # Contrôle de sortie : la source `firms` conditionne tout l'import du
        # corpus. Sans elle, `import-corpus.py` échouerait bien plus loin, sur
        # un message qui ne dirait pas que le seed a manqué.
        with conn.cursor() as cur:
            cur.execute("select count(*) from ingest.data_sources")
            row = cur.fetchone()
            sources = 0 if row is None else int(row[0])

    print(f"\nterminé en {time.monotonic() - started:.0f} s.")
    print(f"{sources} source(s) au registre.")

    if sources == 0:
        print("\nAucune source enregistrée : l'import du corpus échouera.")
        return 1

    print("\nÉtape suivante :")
    print("  python scripts/import-corpus.py --limite 20000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
