"""Importe les détections thermiques NASA FIRMS.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-firms.py
    micromamba run -n mapfeux-geo python scripts/import-firms.py --days 3
    micromamba run -n mapfeux-geo python scripts/import-firms.py --history 60
    micromamba run -n mapfeux-geo python scripts/import-firms.py --bbox 5.9,42.9,7.8,44.4

`--history N` remonte N jours en arrière par tranches de dix, la limite d'une
requête à l'API Area. Sert à constituer le corpus de calibration du
regroupement : un algorithme de rattachement ne se valide pas sur une journée.

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
from datetime import UTC, datetime, timedelta

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import DsnError, normalise_dsn, read_env_file
from geo_worker.pipelines.detections import (
    insert_detections,
    mark_known_thermal_sources,
)
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.providers.firms import (
    DEFAULT_PRODUCTS,
    MAX_DAY_RANGE,
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
    # FIRMS_MAP_KEY et DATABASE_URL viennent du même fichier : on le lit une
    # fois plutôt que d'ouvrir deux accès distincts au même contenu.
    try:
        return read_env_file(ENV_FILE)
    except DsnError as exc:
        sys.exit(str(exc))


def archive(product: str, body: str, stamp: datetime) -> tuple[pathlib.Path, str]:
    """Écrit le CSV brut et retourne son chemin et son empreinte."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{stamp.strftime('%Y%m%dT%H%M%SZ')}_{product}.csv"
    path = RAW_DIR / name
    path.write_text(body, encoding="utf-8")
    checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return path, checksum


def option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def parse_args(argv: list[str]) -> tuple[int, int, BoundingBox]:
    """Retourne (jours par requête, jours d'historique, emprise)."""
    days = int(option(argv, "--days") or 1)
    history = int(option(argv, "--history") or 0)

    bbox = FRANCE_WITH_BUFFER
    raw_bbox = option(argv, "--bbox")
    if raw_bbox is not None:
        parts = [float(p) for p in raw_bbox.split(",")]
        if len(parts) != 4:
            sys.exit("--bbox attend quatre valeurs séparées par des virgules.")
        bbox = BoundingBox(min_lon=parts[0], min_lat=parts[1], max_lon=parts[2], max_lat=parts[3])

    if history > 0:
        days = MAX_DAY_RANGE

    return days, history, bbox


def windows(history_days: int, chunk: int, now: datetime) -> list[datetime | None]:
    """Dates de début des tranches, de la plus ancienne à la plus récente.

    `None` signifie « les N derniers jours », forme sans date que l'API accepte
    et qui suit la fenêtre courante sans qu'on ait à la calculer.
    """
    if history_days <= 0:
        return [None]

    starts: list[datetime] = []
    offset = history_days
    while offset > 0:
        starts.append(now - timedelta(days=offset))
        offset -= chunk
    return list(starts)


def main(argv: list[str]) -> int:
    days, history, bbox = parse_args(argv)
    env = read_env()

    map_key = env.get("FIRMS_MAP_KEY", "")
    if map_key == "":
        sys.exit(
            "FIRMS_MAP_KEY absente de services/geo-worker/.env.\n"
            "Clé gratuite : https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )

    dsn = normalise_dsn(env.get("DATABASE_URL", ""))
    stamp = datetime.now(UTC)

    chunks = windows(history, days, stamp)

    print(f"emprise : {bbox.as_firms_area()}")
    if history > 0:
        print(f"historique : {history} jour(s) en {len(chunks)} tranche(s) de {days}\n")
    else:
        print(f"fenêtre : {days} jour(s)\n")

    total_inserted = 0
    failures = 0

    with psycopg.connect(dsn, connect_timeout=30) as conn, httpx.Client() as http:
        firms = FirmsClient(http, map_key)

        for product in DEFAULT_PRODUCTS:
            suffix = ":history" if history > 0 else ""
            try:
                # Un seul import_run par produit, quelles que soient les
                # tranches : c'est le produit qui réussit ou échoue du point de
                # vue de l'exploitation, pas chaque requête.
                with import_run(
                    conn, source_key="firms", job_name=f"detections:{product}{suffix}"
                ) as counters:
                    product_inserted = 0
                    product_known = 0
                    latest = None

                    for start in chunks:
                        try:
                            body = firms.fetch_area(
                                product=product,
                                bbox=bbox,
                                day_range=days,
                                start_date=start,
                            )
                        except FirmsUnavailableError as exc:
                            # Une tranche hors de la fenêtre disponible ou en
                            # erreur ne doit pas faire perdre les autres : le
                            # rejet est isolé et compté (§16.2).
                            print(f"  tranche {start.date() if start else 'courante'} : {exc}")
                            counters.records_rejected += 1
                            continue

                        # Archivage avant analyse. §16.1, étape 6.
                        label = product if start is None else f"{product}_{start.date()}"
                        path, checksum = archive(label, body, stamp)
                        counters.artifact_path = str(path.relative_to(ROOT))
                        counters.checksum = checksum

                        detections, rejections = parse_csv(body, product=product)
                        unique = list(deduplicate(detections))

                        counters.records_read += len(detections) + len(rejections)
                        counters.records_rejected += len(rejections)
                        for rejection in rejections[:3]:
                            print(f"  rejet : {rejection}")

                        inserted = insert_detections(
                            conn,
                            detections=unique,
                            source_key="firms",
                            import_run_id=None,
                        )
                        conn.commit()

                        product_inserted += inserted.inserted
                        product_known += inserted.already_known

                        chunk_latest = most_recent_acquisition(unique)
                        if chunk_latest is not None and (latest is None or chunk_latest > latest):
                            latest = chunk_latest

                    counters.records_inserted = product_inserted
                    # Une republication déjà connue n'est ni une insertion ni un
                    # rejet : elle est comptée à part pour que /statut ne
                    # présente pas un import correct comme un import vide.
                    counters.metrics = {
                        "already_known": product_known,
                        "product": product,
                        "chunks": len(chunks),
                    }
                    # Date de la donnée, pas de l'import : c'est elle qui fait
                    # la fraîcheur affichée (§5.13).
                    counters.source_data_at = latest

                    total_inserted += product_inserted
                    print(
                        f"{product:<20} {product_inserted} nouvelles, {product_known} déjà connues"
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
                print(f"\n{classified} détection(s) rattachée(s) à une source thermique connue.")

    print(f"\n{total_inserted} détection(s) insérée(s), {failures} produit(s) en échec.")
    # Un échec partiel n'est pas un succès : le code de sortie doit le dire à
    # l'ordonnanceur.
    return 1 if failures == len(DEFAULT_PRODUCTS) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
