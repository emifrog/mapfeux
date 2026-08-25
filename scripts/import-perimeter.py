"""Importe une version de périmètre pour un événement.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-perimeter.py \
        --evenement MPF-XXXXXXXX --fichier perimetre.geojson \
        --nature effis --valide-le 2026-08-24T18:00 \
        [--source effis] [--publie-le ISO] [--surface-annoncee 830] \
        [--resolution 375] [--confiance medium] [--source-url https://…]

Référence : cahier v2.1 §13.23 et FR-090 à FR-096 ; plan J9.

Chaque import est une **version** : il s'ajoute, chaîné à la précédente de
même nature et de même source, et ne remplace rien (FR-094). Le fichier brut
est archivé avant analyse, la surface est recalculée par la base et la
méthode consignée (FR-095) — la surface annoncée par la source, si fournie,
est conservée à côté sans jamais être confondue avec la nôtre.

La passe est journalisée sous la source correspondante (`import_run`), et le
brut part dans le compartiment `raw`.
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.perimeters import (
    PerimeterError,
    geojson_to_multipolygon_wkt,
    store_perimeter,
)
from geo_worker.storage import upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"

NATURES = ("official", "institutional", "effis", "estimated", "editorial", "historical")
CONFIDENCES = ("low", "medium", "high", "not_applicable")


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def parse_instant(raw: str, flag: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        sys.exit(f"{flag} attend un horodatage ISO, reçu {raw!r}.")
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def main(argv: list[str]) -> int:
    public_id = parse_option(argv, "--evenement")
    file_option = parse_option(argv, "--fichier")
    nature = parse_option(argv, "--nature")
    valid_option = parse_option(argv, "--valide-le")
    if public_id is None or file_option is None or nature is None or valid_option is None:
        sys.exit("--evenement, --fichier, --nature et --valide-le sont requis.")
    if nature not in NATURES:
        sys.exit(f"--nature attend {', '.join(NATURES)}.")

    source_key = parse_option(argv, "--source") or "effis"
    confidence = parse_option(argv, "--confiance") or "medium"
    if confidence not in CONFIDENCES:
        sys.exit(f"--confiance attend {', '.join(CONFIDENCES)}.")
    valid_at = parse_instant(valid_option, "--valide-le")
    published_option = parse_option(argv, "--publie-le")
    published_at = (
        None if published_option is None else parse_instant(published_option, "--publie-le")
    )
    source_area = parse_option(argv, "--surface-annoncee")
    resolution = parse_option(argv, "--resolution")
    source_url = parse_option(argv, "--source-url")

    geojson_path = pathlib.Path(file_option)
    if not geojson_path.is_file():
        sys.exit(f"Fichier introuvable : {geojson_path}")
    raw_bytes = geojson_path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))
    wkt = geojson_to_multipolygon_wkt(payload)

    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    bucket = env.get("SUPABASE_STORAGE_BUCKET_RAW", "raw")
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour archiver le brut.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}")

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        event = conn.execute(
            "select id from fire.events where public_id = %(pid)s",
            {"pid": public_id.upper()},
        ).fetchone()
        if event is None:
            sys.exit(f"Événement inconnu : {public_id}")

        # Le chemin porte la date de publication source (ou, à défaut, l'heure
        # d'import) : deux versions d'un même instant représenté ne doivent
        # jamais partager un chemin — le second dépôt écraserait le brut de la
        # première, ce que FR-096 interdit. Mesuré au premier exercice réel.
        discriminant = published_at or datetime.now(UTC)
        object_path = (
            f"perimetres/{public_id.upper()}/"
            f"{valid_at:%Y-%m-%dT%H%M%SZ}__{nature}__{source_key}"
            f"__{discriminant:%Y%m%dT%H%M%SZ}.geojson"
        )

        try:
            with import_run(
                conn,
                source_key=source_key,
                job_name=f"{source_key}:perimetre:{public_id.upper()}",
            ) as counters:
                with httpx.Client() as http:
                    checksum = upload_object(
                        http,
                        supabase_url=supabase_url,
                        secret_key=secret_key,
                        bucket=bucket,
                        object_path=object_path,
                        payload=raw_bytes,
                        content_type="application/geo+json",
                    )

                perimeter_id, area_ha, supersedes = store_perimeter(
                    conn,
                    event_id=event[0],
                    source_key=source_key,
                    perimeter_type=nature,
                    valid_at=valid_at,
                    published_at=published_at,
                    geometry_wkt=wkt,
                    source_area_ha=None if source_area is None else float(source_area),
                    resolution_m=None if resolution is None else float(resolution),
                    confidence=confidence,
                    raw_payload={
                        "archive": f"{bucket}/{object_path}",
                        "checksum": checksum,
                        "source_url": source_url,
                        "fichier": geojson_path.name,
                    },
                )

                counters.records_read = 1
                counters.records_inserted = 1
                counters.artifact_path = f"{bucket}/{object_path}"
                counters.checksum = checksum
                counters.source_data_at = valid_at
                counters.metrics = {
                    "evenement": public_id.upper(),
                    "nature": nature,
                    "surface_recalculee_ha": area_ha,
                    "surface_annoncee_ha": None if source_area is None else float(source_area),
                }

                print(f"\npérimètre : {perimeter_id} ({nature}, {source_key})")
                print(f"validité  : {valid_at:%Y-%m-%d %H:%M} UTC")
                print(f"surface   : {area_ha} ha recalculés", end="")
                if source_area is not None:
                    print(f" · {float(source_area)} ha annoncés par la source", end="")
                print()
                if supersedes is not None:
                    print(f"remplace  : {supersedes} (version conservée, FR-094)")
                print(f"brut      : {bucket}/{object_path}")
        except (PerimeterError, ImportRunError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
