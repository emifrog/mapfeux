"""Chaîne d'ingestion complète : import, regroupement, snapshots.

Usage :
    micromamba run -n mapfeux-geo python scripts/run-ingestion.py
    micromamba run -n mapfeux-geo python scripts/run-ingestion.py --bbox 5.5,42.7,7.9,44.5

Référence : cahier §16.1 et §16.8.

Point d'entrée unique destiné à l'ordonnanceur. Les trois étapes s'enchaînent
dans le seul ordre qui a du sens : on ne regroupe pas avant d'avoir importé, et
on ne publie pas un état figé avant d'avoir regroupé.

Chaque étape est isolée. Une source indisponible n'empêche pas de regrouper les
détections déjà en base, et un regroupement en échec laisse les snapshots
précédents intacts plutôt que d'en publier de faux.

Seuls les événements touchés voient leur snapshot reconstruit : en reconstruire
la totalité à chaque passage coûterait le prix d'une saison pour la valeur de
dix minutes.

Une seule passe à la fois. Un ordonnanceur qui déclenche toutes les dix minutes
une chaîne qui en met parfois quinze superposerait deux exécutions ; le verrou
fait sortir la seconde sans erreur, ce qui est le comportement attendu d'une
tâche périodique.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, exclusive_run, load_env
from geo_worker.pipelines.clustering import (
    ClusteringResult,
    cluster_detections,
)
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
from geo_worker.storage import BUCKET_RAW, StorageError, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


@dataclass(frozen=True)
class ArchiveTarget:
    """Où déposer les fichiers bruts, et avec quelle clé."""

    supabase_url: str
    secret_key: str
    bucket: str


def archive_target(env: dict[str, str]) -> ArchiveTarget | None:
    """Cible d'archivage, ou `None` si elle n'est pas configurée.

    L'archivage est **exigé en production** et facultatif ailleurs : une
    calibration ou un essai local n'ont pas à posséder une clé de service pour
    faire tourner la chaîne. Le compromis a une limite claire — une
    configuration *partielle* est refusée, parce qu'elle signale une intention
    d'archiver que le silence trahirait.
    """
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    bucket = env.get("SUPABASE_STORAGE_BUCKET_RAW", BUCKET_RAW)

    if supabase_url == "" and secret_key == "":
        return None

    if supabase_url == "" or secret_key == "":
        manquante = "SUPABASE_URL" if supabase_url == "" else "SUPABASE_SECRET_KEY"
        sys.exit(
            f"{manquante} absente alors que l'autre est renseignée.\n"
            "L'archivage du brut est soit configuré, soit absent ; à moitié, il "
            "échouerait à chaque passe sans qu'on sache si c'était voulu."
        )

    return ArchiveTarget(supabase_url=supabase_url, secret_key=secret_key, bucket=bucket)


# France métropolitaine et Corse, avec tampon frontalier : un feu à quelques
# kilomètres de la frontière concerne les communes françaises voisines (§16.3).
FRANCE_WITH_BUFFER = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)


def parse_bbox(argv: list[str]) -> BoundingBox:
    if "--bbox" not in argv:
        return FRANCE_WITH_BUFFER
    index = argv.index("--bbox")
    if index + 1 >= len(argv):
        sys.exit("--bbox attend minLon,minLat,maxLon,maxLat.")
    parts = [float(p) for p in argv[index + 1].split(",")]
    if len(parts) != 4:
        sys.exit("--bbox attend quatre valeurs séparées par des virgules.")
    return BoundingBox(min_lon=parts[0], min_lat=parts[1], max_lon=parts[2], max_lat=parts[3])


def raw_object_path(product: str, stamp: datetime) -> str:
    """Chemin du CSV brut dans le compartiment `raw`.

    Arborescence par jour : une rétention de trente jours se purge alors par
    préfixe, sans lister le compartiment entier.
    """
    return f"firms/{stamp.strftime('%Y/%m/%d')}/{stamp.strftime('%Y%m%dT%H%M%SZ')}_{product}.csv"


def step_import(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    map_key: str,
    bbox: BoundingBox,
    archive: ArchiveTarget | None,
) -> tuple[int, int]:
    """Importe les détections récentes. Retourne (insérées, produits en échec)."""
    firms = FirmsClient(client, map_key)
    inserted_total = 0
    failures = 0

    for product in DEFAULT_PRODUCTS:
        try:
            with import_run(conn, source_key="firms", job_name=f"detections:{product}") as counters:
                body = firms.fetch_area(product=product, bbox=bbox, day_range=1)

                # Archivage **avant** analyse — §16.1, étape 6. Ce qui n'a pas
                # été conservé ne peut pas être rejoué, et un changement de
                # format chez FIRMS se diagnostique sur la donnée reçue, jamais
                # sur son interprétation.
                #
                # La chaîne planifiée ne le faisait pas : seul l'import manuel
                # écrivait le CSV, sur le disque du poste. Depuis que
                # l'ordonnanceur est chez GitHub, ce disque est celui d'un
                # runner qui disparaît à la fin du passage — la règle était donc
                # tenue nulle part, alors que le plan la portait comme acquise.
                if archive is not None:
                    stamp = datetime.now(UTC)
                    object_path = raw_object_path(product, stamp)
                    counters.checksum = upload_object(
                        client,
                        supabase_url=archive.supabase_url,
                        secret_key=archive.secret_key,
                        bucket=archive.bucket,
                        object_path=object_path,
                        payload=body.encode("utf-8"),
                        content_type="text/csv; charset=utf-8",
                    )
                    counters.artifact_path = f"{archive.bucket}/{object_path}"

                detections, rejections = parse_csv(body, product=product)
                unique = list(deduplicate(detections))

                counters.records_read = len(detections) + len(rejections)
                counters.records_rejected = len(rejections)

                result = insert_detections(
                    conn, detections=unique, source_key="firms", import_run_id=None
                )
                conn.commit()

                counters.records_inserted = result.inserted
                counters.metrics = {
                    "already_known": result.already_known,
                    "product": product,
                }
                counters.source_data_at = most_recent_acquisition(unique)
                inserted_total += result.inserted

        except FirmsQuotaError as exc:
            failures += 1
            delay = exc.retry_after_seconds
            print(f"  {product} : quota atteint" + (f", réessayer dans {delay} s" if delay else ""))
        except (FirmsUnavailableError, ImportRunError, StorageError) as exc:
            # Un dépôt refusé fait échouer **ce produit**, et le fait savoir. On
            # ne l'avale pas : analyser une donnée qu'on n'a pas conservée, c'est
            # produire un résultat qu'on ne pourra jamais réexaminer.
            failures += 1
            print(f"  {product} : {exc}")

    return inserted_total, failures


def main(argv: list[str]) -> int:
    bbox = parse_bbox(argv)
    env = load_env(ENV_FILE)

    map_key = env.get("FIRMS_MAP_KEY", "")
    if map_key == "":
        sys.exit(
            "FIRMS_MAP_KEY absente du fichier et de l'environnement.\n"
            "Clé gratuite : https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )

    archive = archive_target(env)

    started = datetime.now(UTC)
    print(f"emprise : {bbox.as_firms_area()}")
    print(
        "archivage : "
        + (
            f"compartiment « {archive.bucket} »"
            if archive is not None
            else "désactivé — aucun fichier brut ne sera conservé"
        )
        + "\n",
        flush=True,
    )

    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        exclusive_run(conn, "ingestion") as acquired,
    ):
        if not acquired:
            print("Une passe d'ingestion est déjà en cours. Rien à faire.")
            # Sortie normale : pour un ordonnanceur périodique, se recouvrir est
            # un fonctionnement attendu, pas une panne à signaler.
            return 0

        with httpx.Client() as client:
            inserted, failures = step_import(conn, client, map_key, bbox, archive)
        print(
            f"import      : {inserted} détection(s), {failures} produit(s) en échec",
            flush=True,
        )

        if inserted > 0:
            classified = mark_known_thermal_sources(conn)
            conn.commit()
            if classified > 0:
                print(
                    f"              {classified} rattachée(s) à une source connue",
                    flush=True,
                )

        # Le regroupement tourne même sans nouvelle détection : un import
        # précédent a pu échouer après insertion, laissant des orphelines.
        #
        # Les passes restent bornées — une transaction de taille prévisible est
        # ce qui rend une tâche périodique sûre — mais on les répète jusqu'à
        # vider la file. Une reprise après panne, ou un rattrapage d'historique,
        # dépose plus d'orphelines qu'un plafond n'en absorbe : s'arrêter à la
        # première passe laisserait une file grossir en silence, et la carte
        # publique manquerait des feux sans rien signaler. Le découpage est sans
        # effet sur le résultat, `verify-clustering.py --incremental` le vérifie.
        result = ClusteringResult()
        passes = 0
        while True:
            current = cluster_detections(conn)
            conn.commit()
            passes += 1
            result.created += current.created
            result.attached += current.attached
            result.touched_events |= current.touched_events
            if not current.truncated or current.processed == 0:
                break
        print(
            f"regroupement: {result.created} événement(s) créé(s), "
            f"{result.attached} rattachement(s)" + (f", {passes} passes" if passes > 1 else ""),
            flush=True,
        )

        refreshed = 0
        with conn.cursor() as cur:
            for event_id in sorted(result.touched_events):
                cur.execute("select fire.refresh_event_snapshot(%s)", (event_id,))
                if cur.fetchone() is not None:
                    refreshed += 1
            conn.commit()
        print(f"snapshots   : {refreshed} reconstruit(s)", flush=True)

    duration = (datetime.now(UTC) - started).total_seconds()
    print(f"\nterminé en {duration:.0f} s.")

    # Un échec total de l'import doit remonter à l'ordonnanceur ; un échec
    # partiel ne doit pas, sous peine d'alerter à chaque passage nocturne où
    # MODIS ne rapporte rien.
    return 1 if failures == len(DEFAULT_PRODUCTS) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
