"""Importe les détections thermiques NASA FIRMS.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-firms.py
    micromamba run -n mapfeux-geo python scripts/import-firms.py --days 3
    micromamba run -n mapfeux-geo python scripts/import-firms.py --bbox 5.9,42.9,7.8,44.4

Référence : cahier §16.1 et §16.3.

Le fichier brut est écrit sur disque **avant** toute analyse : ce qui n'a pas
été conservé ne peut pas être rejoué, et un changement de format chez le
fournisseur se diagnostique sur la donnée reçue, pas sur son interprétation.

Chaque produit ouvre son propre `import_run`. Un capteur indisponible n'empêche
donc pas les autres d'aboutir, et /statut montre lequel a échoué.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.pipelines.detections import (
    insert_detections,
    mark_known_thermal_sources,
)
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.providers.firms import (
    DEFAULT_PRODUCTS,
    FirmsClient,
    FirmsQuotaError,
    FirmsUnavailableError,
    deduplicate,
    most_recent_acquisition,
    parse_csv,
)
from geo_worker.providers.models import BoundingBox

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
RAW_DIR = ROOT / "data" / "raw" / "firms"

# France métropolitaine et Corse, avec un tampon frontalier : un feu à quelques
# kilomètres de la frontière concerne les communes françaises voisines (§16.3).
FRANCE_WITH_BUFFER = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        sys.exit(f"Fichier introuvable : {ENV_FILE}")

    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip()
    return values


def build_dsn(raw: str) -> str:
    """Répare un `@` non encodé dans le mot de passe, sans double encodage."""
    scheme, sep, rest = raw.partition("://")
    if sep == "":
        return raw
    authority, slash, path = rest.partition("/")
    if authority.count("@") <= 1:
        return raw
    userinfo, _, hostpart = authority.rpartition("@")
    user, _, password = userinfo.partition(":")
    return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}{slash}{path}"


def archive(product: str, body: str, stamp: datetime) -> tuple[pathlib.Path, str]:
    """Écrit le CSV brut et retourne son chemin et son empreinte."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{stamp.strftime('%Y%m%dT%H%M%SZ')}_{product}.csv"
    path = RAW_DIR / name
    path.write_text(body, encoding="utf-8")
    checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return path, checksum


def parse_args(argv: list[str]) -> tuple[int, BoundingBox]:
    days = 1
    bbox = FRANCE_WITH_BUFFER

    if "--days" in argv:
        index = argv.index("--days")
        if index + 1 >= len(argv):
            sys.exit("--days attend un nombre de jours.")
        days = int(argv[index + 1])

    if "--bbox" in argv:
        index = argv.index("--bbox")
        if index + 1 >= len(argv):
            sys.exit("--bbox attend minLon,minLat,maxLon,maxLat.")
        parts = [float(p) for p in argv[index + 1].split(",")]
        if len(parts) != 4:
            sys.exit("--bbox attend quatre valeurs séparées par des virgules.")
        bbox = BoundingBox(
            min_lon=parts[0], min_lat=parts[1], max_lon=parts[2], max_lat=parts[3]
        )

    return days, bbox


def main(argv: list[str]) -> int:
    days, bbox = parse_args(argv)
    env = read_env()

    map_key = env.get("FIRMS_MAP_KEY", "")
    if map_key == "":
        sys.exit(
            "FIRMS_MAP_KEY absente de services/geo-worker/.env.\n"
            "Clé gratuite : https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )

    dsn = build_dsn(env.get("DATABASE_URL", ""))
    stamp = datetime.now(UTC)

    print(f"emprise : {bbox.as_firms_area()}")
    print(f"fenêtre : {days} jour(s)\n")

    total_inserted = 0
    failures = 0

    with psycopg.connect(dsn, connect_timeout=30) as conn, httpx.Client() as http:
        firms = FirmsClient(http, map_key)

        for product in DEFAULT_PRODUCTS:
            try:
                with import_run(
                    conn, source_key="firms", job_name=f"detections:{product}"
                ) as counters:
                    body = firms.fetch_area(product=product, bbox=bbox, day_range=days)

                    # Archivage avant analyse. §16.1, étape 6.
                    path, checksum = archive(product, body, stamp)
                    counters.artifact_path = str(path.relative_to(ROOT))
                    counters.checksum = checksum

                    detections, rejections = parse_csv(body, product=product)
                    unique = list(deduplicate(detections))

                    counters.records_read = len(detections) + len(rejections)
                    counters.records_rejected = len(rejections)
                    for rejection in rejections[:3]:
                        print(f"  rejet : {rejection}")

                    inserted = insert_detections(
                        conn,
                        detections=unique,
                        source_key="firms",
                        import_run_id=None,
                    )
                    conn.commit()

                    counters.records_inserted = inserted.inserted
                    # Une republication déjà connue n'est ni une insertion ni un
                    # rejet : elle est comptée à part pour que /statut ne
                    # présente pas un import correct comme un import vide.
                    counters.metrics = {
                        "already_known": inserted.already_known,
                        "product": product,
                    }
                    # Date de la donnée, pas de l'import : c'est elle qui fait
                    # la fraîcheur affichée (§5.13).
                    counters.source_data_at = most_recent_acquisition(unique)

                    total_inserted += inserted.inserted
                    print(
                        f"{product:<20} {inserted.inserted} nouvelles, "
                        f"{inserted.already_known} déjà connues, "
                        f"{len(rejections)} rejetées"
                    )

            except FirmsQuotaError as exc:
                failures += 1
                delay = exc.retry_after_seconds
                print(
                    f"{product:<20} quota atteint"
                    + (f", réessayer dans {delay} s" if delay else "")
                )
            except (FirmsUnavailableError, ImportRunError) as exc:
                failures += 1
                print(f"{product:<20} échec : {exc}")

        if total_inserted > 0:
            classified = mark_known_thermal_sources(conn)
            conn.commit()
            if classified > 0:
                print(
                    f"\n{classified} détection(s) rattachée(s) à une source thermique connue."
                )

    print(
        f"\n{total_inserted} détection(s) insérée(s), {failures} produit(s) en échec."
    )
    # Un échec partiel n'est pas un succès : le code de sortie doit le dire à
    # l'ordonnanceur.
    return 1 if failures == len(DEFAULT_PRODUCTS) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
