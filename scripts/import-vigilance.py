"""Importe le dernier bulletin de vigilance Météo-France.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-vigilance.py

Référence : cahier §16.1, stratégie §4.

Le fichier brut est archivé **avant** toute analyse : ce qui n'a pas été
conservé ne peut pas être rejoué, et un changement de format se diagnostique sur
la donnée reçue, pas sur son interprétation.

Retrouver un bulletin déjà connu est le cas courant, pas une anomalie :
Météo-France diffuse au moins deux fois par jour, l'ingestion passe plus
souvent. Le script le dit et sort en succès.

`METEOFRANCE_VIGILANCE_API_KEY` commande la voie d'accès. Avec elle, l'API temps
réel ; sans elle, le dépôt d'archive de data.gouv.fr, qui accuse environ un jour
de retard — le script le dit alors en clair, parce qu'une vigilance d'hier servie
sans le dire est pire qu'une vigilance absente.

Clé gratuite : portail-api.meteofrance.fr, application « Bulletin Vigilance ».
Le nom porte l'application parce que le portail délivre une clé par
application : celle du radar ne vaut pas ici, et poser l'une pour l'autre
produirait un 403 sans motif visible.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.vigilance import store_bulletin
from geo_worker.providers.vigilance import (
    VigilanceClient,
    VigilanceError,
    api_key_from,
    parse_carte,
)
from geo_worker.storage import StorageConfigError, StorageError, archive_target, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
RAW_DIR = ROOT / "data" / "raw" / "vigilance"

SOURCE_KEY = "vigilance"


def raw_object_path(label: str, stamp: datetime) -> str:
    """Chemin du bulletin brut dans le compartiment `raw`.

    Arborescence par jour, comme pour FIRMS : une rétention de trente jours se
    purge alors par préfixe, sans lister le compartiment entier.

    Le libellé vient de l'adaptateur et identifie la diffusion. L'extension
    n'est ajoutée que si le libellé n'en porte pas déjà : la déduire de l'URL
    avait produit des objets en `.json.json`.
    """
    safe = label.replace("/", "").removesuffix(".json")
    horodatage = stamp.strftime("%Y%m%dT%H%M%SZ")
    return f"vigilance/{stamp.strftime('%Y/%m/%d')}/{horodatage}_{safe}.json"


def archive_local(reference_path: str, body: str, stamp: datetime) -> tuple[pathlib.Path, str]:
    """Écrit le bulletin brut sur le disque et retourne son chemin et son empreinte.

    Repli lorsque le stockage objet n'est pas configuré — un poste de
    développement n'a pas à détenir une clé de service. Sur un ordonnanceur, ce
    repli ne conserve rien : le disque du runner disparaît avec le passage, et
    c'est pourquoi l'archivage distant est le chemin nominal.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = reference_path.replace("/", "")
    path = RAW_DIR / f"{stamp.strftime('%Y%m%dT%H%M%SZ')}_{safe}.json"
    path.write_text(body, encoding="utf-8")
    return path, hashlib.sha256(body.encode("utf-8")).hexdigest()


def main() -> int:
    stamp = datetime.now(UTC)
    try:
        archive = archive_target(load_env(ENV_FILE))
    except StorageConfigError as exc:
        sys.exit(str(exc))

    api_key = api_key_from(load_env(ENV_FILE))

    print(
        "archivage : "
        + (
            f"compartiment « {archive.bucket} »"
            if archive is not None
            else "disque local — aucune conservation sur un ordonnanceur"
        ),
        flush=True,
    )
    if api_key == "":
        # L'avertissement est le point : sans clé, la donnée servie a près
        # d'une journée de retard, et rien à l'écran ne le dirait autrement.
        print(
            "accès     : dépôt d'archive — METEOFRANCE_VIGILANCE_API_KEY absente.\n"
            "            Le dépôt accuse environ un jour de retard : la vigilance\n"
            "            restera affichée « trop ancienne ».",
            flush=True,
        )
    else:
        print("accès     : API temps réel Météo-France", flush=True)

    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        httpx.Client() as http,
    ):
        client = VigilanceClient(http, api_key=api_key)

        try:
            with import_run(conn, source_key=SOURCE_KEY, job_name="vigilance:carte") as counters:
                fetched = client.fetch_latest()
                body = fetched.body
                url = fetched.url
                label = fetched.label
                print(f"bulletin : {label}")

                # Archivage avant analyse — §16.1, étape 6.
                if archive is None:
                    path, checksum = archive_local(label, body, stamp)
                    counters.artifact_path = str(path.relative_to(ROOT))
                else:
                    object_path = raw_object_path(label, stamp)
                    checksum = upload_object(
                        http,
                        supabase_url=archive.supabase_url,
                        secret_key=archive.secret_key,
                        bucket=archive.bucket,
                        object_path=object_path,
                        payload=body.encode("utf-8"),
                        content_type="application/json; charset=utf-8",
                    )
                    counters.artifact_path = f"{archive.bucket}/{object_path}"

                counters.checksum = checksum

                bulletin, levels, rejections = parse_carte(json.loads(body))
                counters.records_read = len(levels) + len(rejections)
                counters.records_rejected = len(rejections)
                for rejection in rejections[:5]:
                    print(f"  rejet : {rejection}")

                result = store_bulletin(
                    conn,
                    bulletin=bulletin,
                    levels=levels,
                    source_url=url,
                    checksum=checksum,
                    raw=body,
                )
                conn.commit()

                counters.records_inserted = result.levels_inserted
                counters.metrics = {
                    "already_known": result.already_known,
                    "vigilance_version": bulletin.vigilance_version,
                    "domains": len({level.domain_id for level in levels}),
                    # Sans cette trace, une donnée vieille d'un jour serait
                    # indiscernable d'une donnée fraîche dans l'historique des
                    # imports.
                    "acces": fetched.access,
                }
                # Date de la donnée, pas de l'import : c'est elle qui fait la
                # fraîcheur affichée (§5.13).
                counters.source_data_at = bulletin.published_at

                if result.already_known:
                    print(f"déjà connu : bulletin du {bulletin.published_at.isoformat()}")
                else:
                    above = [level for level in levels if level.colour != "vert"]
                    print(
                        f"importé  : {result.levels_inserted} niveaux, "
                        f"{len(above)} au-dessus du vert"
                    )

        # Un dépôt refusé fait échouer l'import : analyser un bulletin qu'on n'a
        # pas conservé, c'est produire des niveaux de vigilance qu'on ne pourra
        # jamais réexaminer contre leur source.
        except (VigilanceError, ImportRunError, StorageError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
