"""Extraction et archivage froid des champs AROME utiles au calcul FWI.

Référence : ADR-025 point 4, cahier §16.4.

On télécharge un paquet de surface, on n'en garde que quatre champs sur
l'emprise nationale, et on dépose l'extrait dans Supabase Storage. Le paquet
pèse une cinquantaine de mégaoctets, l'extrait deux ordres de grandeur de
moins : c'est ce rapport qui rend l'archivage quotidien tenable.

Le paquet brut n'est pas conservé. La règle « archiver le brut avant analyse »
vaut pour ce qu'on ne peut pas retrouver ; Météo-France republie ses paquets, et
en garder vingt gigaoctets par an pour cette raison serait payer cher une
assurance déjà souscrite ailleurs.
"""

from __future__ import annotations

import hashlib
import pathlib
import tempfile
from dataclasses import dataclass

import httpx
import xarray as xr

from geo_worker.logging import get_logger
from geo_worker.providers.arome import FWI_FIELDS, AromeError, PackageRef
from geo_worker.providers.models import BoundingBox

logger = get_logger(__name__)


@dataclass
class ArchiveResult:
    object_path: str
    checksum: str
    source_bytes: int
    archived_bytes: int
    fields: tuple[str, ...]

    @property
    def reduction(self) -> float:
        """Facteur de réduction obtenu. Zéro si la source était vide."""
        return 0.0 if self.source_bytes == 0 else self.source_bytes / self.archived_bytes


def extract(path: pathlib.Path, extent: BoundingBox, lead_hours: int) -> xr.Dataset:
    """Ouvre le GRIB et n'en retient que les champs FWI, sur l'emprise.

    Un paquet AROME mélange des grilles de géométries différentes ; xarray ne
    sait pas les réunir en un seul jeu et refuserait l'ouverture directe.
    `open_datasets` les rend séparément, à charge de reprendre les variables là
    où elles se trouvent.
    """
    import cfgrib

    found: dict[str, xr.DataArray] = {}
    for dataset in cfgrib.open_datasets(str(path)):
        for name in FWI_FIELDS:
            if name in dataset.data_vars and name not in found:
                # Les coordonnées scalaires sont retirées avant fusion : la
                # température est à deux mètres et le vent à dix, si bien que
                # `heightAboveGround` diffère d'une variable à l'autre et
                # empêcherait la réunion. Le nom de la variable porte déjà la
                # hauteur, la coordonnée n'apprend rien de plus.
                found[name] = dataset[name].reset_coords(drop=True)

    missing = [name for name in FWI_FIELDS if name not in found]
    if missing:
        raise AromeError(f"Champs absents du paquet : {', '.join(missing)}")

    merged = xr.Dataset(found)

    # Les latitudes AROME sont décroissantes : une tranche croissante
    # retournerait un jeu vide sans lever d'erreur.
    lat = merged["latitude"]
    lat_slice = (
        slice(extent.max_lat, extent.min_lat)
        if float(lat[0]) > float(lat[-1])
        else slice(extent.min_lat, extent.max_lat)
    )
    subset = merged.sel(latitude=lat_slice, longitude=slice(extent.min_lon, extent.max_lon))

    if subset.sizes.get("latitude", 0) == 0 or subset.sizes.get("longitude", 0) == 0:
        raise AromeError("L'emprise demandée ne recoupe pas la grille du modèle.")

    subset.attrs["mapfeux_lead_hours"] = lead_hours
    subset.attrs["mapfeux_extent"] = extent.as_firms_area()
    return subset


def upload(
    client: httpx.Client,
    *,
    supabase_url: str,
    secret_key: str,
    bucket: str,
    object_path: str,
    payload: bytes,
) -> None:
    """Dépose l'extrait, en écrasant une éventuelle version antérieure.

    `x-upsert` évite qu'un rejeu quotidien échoue sur un objet déjà présent :
    rejouer une journée doit être anodin, pas une erreur à diagnostiquer.
    """
    response = client.post(
        f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{object_path}",
        content=payload,
        headers={
            # Les clés `sb_secret_…` ne sont pas des JWT : Storage refuse de les
            # analyser comme tel et répond « Invalid Compact JWS ». Elles se
            # présentent en `apikey` ; l'en-tête `Authorization` reste envoyé
            # pour les déploiements servant encore l'ancien format.
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        },
        timeout=180,
    )
    if response.status_code >= 300:
        # Le corps porte le motif ; l'URL porte le compartiment, pas de secret.
        raise AromeError(f"Dépôt refusé ({response.status_code}) : {response.text[:200]}")


def archive_package(
    http: httpx.Client,
    *,
    reference: PackageRef,
    extent: BoundingBox,
    lead_hours: int,
    supabase_url: str,
    secret_key: str,
    bucket: str,
) -> ArchiveResult:
    """Télécharge, extrait, dépose. Retourne de quoi renseigner l'import_run."""
    logger.info("arome.fetch", url=reference.url)

    with tempfile.TemporaryDirectory() as workspace:
        # Le nom publié porte l'horodatage ISO du run, deux-points compris, que
        # Windows refuse dans un chemin. Le nom local est donc assaini ; l'URL,
        # elle, reste celle du fournisseur.
        grib = pathlib.Path(workspace) / reference.filename.replace(":", "")
        with http.stream("GET", reference.url, timeout=300) as response:
            if response.status_code != 200:
                raise AromeError(f"Paquet indisponible : HTTP {response.status_code}")
            with grib.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)

        source_bytes = grib.stat().st_size
        subset = extract(grib, extent, lead_hours)

        extract_path = pathlib.Path(workspace) / "extract.nc"
        # La compression est ce qui fait tenir l'archive : sans elle, l'extrait
        # reste dix fois trop lourd pour une conservation quotidienne.
        encoding = {name: {"zlib": True, "complevel": 5} for name in subset.data_vars}
        subset.to_netcdf(extract_path, encoding=encoding)
        payload = extract_path.read_bytes()

    checksum = hashlib.sha256(payload).hexdigest()
    object_path = (
        f"arome/{reference.run.strftime('%Y/%m/%d')}/"
        f"{reference.run_key.replace(':', '')}__{reference.span}__fwi.nc"
    )

    upload(
        http,
        supabase_url=supabase_url,
        secret_key=secret_key,
        bucket=bucket,
        object_path=object_path,
        payload=payload,
    )

    result = ArchiveResult(
        object_path=object_path,
        checksum=checksum,
        source_bytes=source_bytes,
        archived_bytes=len(payload),
        fields=FWI_FIELDS,
    )
    logger.info(
        "arome.archived",
        object_path=object_path,
        source_mo=round(source_bytes / 1e6, 1),
        archived_mo=round(len(payload) / 1e6, 2),
        reduction=round(result.reduction, 1),
    )
    return result


__all__ = ["ArchiveResult", "archive_package", "extract", "upload"]
