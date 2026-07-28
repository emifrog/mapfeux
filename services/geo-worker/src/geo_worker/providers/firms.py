"""Connecteur NASA FIRMS.

Référence : cahier §9.1, §16.3 et §17.1.

Deux règles structurent ce module :

1. Une détection n'est jamais interprétée. Le connecteur normalise des champs,
   il ne conclut pas qu'un incendie est en cours (§9.1).
2. La clé d'idempotence est calculée ici et nulle part ailleurs. Elle est la
   seule protection contre les doublons au rejeu d'un import (FR-033), et sa
   définition ne doit pas diverger entre le worker et les tests.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from geo_worker.providers.models import BoundingBox, ThermalDetection

PROVIDER = "nasa_firms"

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Jeux NRT disponibles. L'ordre est celui de l'import : les VIIRS d'abord, dont
# la résolution de 375 m est meilleure que le kilomètre de MODIS (§9.1).
DEFAULT_PRODUCTS: tuple[str, ...] = (
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "VIIRS_SNPP_NRT",
    "MODIS_NRT",
)

# L'API Area accepte au plus cinq jours par requête. Vérifié contre le service :
# au-delà elle répond 400 « Invalid day range. Expects [1..5] ».
MAX_DAY_RANGE = 5

# Précision retenue pour la clé d'idempotence. FIRMS publie 5 décimales ; figer
# l'arrondi évite qu'une variation de formatage côté fournisseur ne produise une
# clé différente pour la même observation.
_COORD_PRECISION = 5

# VIIRS publie une confiance qualitative, MODIS un pourcentage. Les deux sont
# ramenés à un score interne 0-1, la valeur brute restant conservée.
_VIIRS_CONFIDENCE = {"l": 0.25, "n": 0.60, "h": 0.90}

_SENSOR_BY_INSTRUMENT = {
    "VIIRS": "VIIRS",
    "MODIS": "MODIS",
}


class FirmsParseError(ValueError):
    """Ligne inexploitable : elle est rejetée et comptée, sans interrompre l'import."""


def build_provider_key(
    *,
    product: str,
    satellite: str,
    sensor: str,
    acquired_at: datetime,
    latitude: float,
    longitude: float,
    version: str | None,
) -> str:
    """Calcule la clé idempotente d'une détection.

    Le hash porte sur les seuls attributs qui identifient l'observation. Les
    champs enrichis ultérieurement (score, source thermique connue) en sont
    volontairement exclus : ils changent, l'observation non.
    """
    if acquired_at.tzinfo is None:
        raise FirmsParseError("acquired_at doit être conscient du fuseau et exprimé en UTC.")

    parts = (
        PROVIDER,
        product,
        satellite,
        sensor,
        acquired_at.astimezone(UTC).isoformat(),
        f"{latitude:.{_COORD_PRECISION}f}",
        f"{longitude:.{_COORD_PRECISION}f}",
        version or "",
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def parse_acquisition_time(acq_date: str, acq_time: str) -> datetime:
    """Combine `acq_date` (YYYY-MM-DD) et `acq_time` (HHMM) en UTC.

    FIRMS transmet l'heure sans séparateur et parfois sans zéro initial :
    « 45 » signifie 00:45.
    """
    try:
        # Seule la partie date est retenue ; le fuseau est appliqué plus bas.
        date_part = datetime.strptime(acq_date.strip(), "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError as exc:
        raise FirmsParseError(f"Date d'acquisition illisible : {acq_date!r}") from exc

    raw_time = acq_time.strip().replace(":", "")
    if not raw_time.isdigit() or len(raw_time) > 4:
        raise FirmsParseError(f"Heure d'acquisition illisible : {acq_time!r}")

    padded = raw_time.zfill(4)
    hours, minutes = int(padded[:2]), int(padded[2:])
    if hours > 23 or minutes > 59:
        raise FirmsParseError(f"Heure d'acquisition hors bornes : {acq_time!r}")

    return datetime(date_part.year, date_part.month, date_part.day, hours, minutes, tzinfo=UTC)


def normalize_confidence(raw: str | None, sensor: str) -> tuple[str | None, float | None]:
    """Ramène la confiance fournisseur à un score interne 0-1.

    Retourne le couple (valeur brute conservée, score normalisé). Un format
    inattendu produit un score nul plutôt qu'une erreur : la détection reste
    valide, seule sa pondération est inconnue.
    """
    if raw is None or raw.strip() == "":
        return None, None

    value = raw.strip()

    if sensor == "VIIRS":
        return value, _VIIRS_CONFIDENCE.get(value.lower())

    try:
        percent = float(value)
    except ValueError:
        return value, None

    if not 0 <= percent <= 100:
        return value, None
    return value, round(percent / 100, 3)


def _optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _required_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "").strip()
    try:
        return float(value)
    except ValueError as exc:
        raise FirmsParseError(f"Champ numérique obligatoire absent ou invalide : {key}") from exc


def parse_row(row: dict[str, str], *, product: str) -> ThermalDetection:
    """Normalise une ligne CSV FIRMS.

    `product` est le jeu demandé (VIIRS_NOAA20_NRT, MODIS_NRT, …) : il fait
    partie de la clé d'idempotence car un même pixel peut être publié dans
    plusieurs jeux.
    """
    instrument = row.get("instrument", "").strip().upper()
    sensor = _SENSOR_BY_INSTRUMENT.get(instrument, instrument or "UNKNOWN")

    latitude = _required_float(row, "latitude")
    longitude = _required_float(row, "longitude")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise FirmsParseError(f"Coordonnées hors bornes : {latitude}, {longitude}")

    acquired_at = parse_acquisition_time(row.get("acq_date", ""), row.get("acq_time", ""))
    satellite = row.get("satellite", "").strip() or "UNKNOWN"
    version = row.get("version", "").strip() or None

    confidence_raw, confidence_score = normalize_confidence(row.get("confidence"), sensor)

    # MODIS et VIIRS ne nomment pas la température de brillance de la même façon.
    brightness = _optional_float(row, "brightness")
    if brightness is None:
        brightness = _optional_float(row, "bright_ti4")

    day_night = row.get("daynight", "").strip() or None
    if day_night is not None:
        day_night = day_night.upper()[:1]
        if day_night not in {"D", "N"}:
            day_night = None

    return ThermalDetection(
        provider_key=build_provider_key(
            product=product,
            satellite=satellite,
            sensor=sensor,
            acquired_at=acquired_at,
            latitude=latitude,
            longitude=longitude,
            version=version,
        ),
        sensor=sensor,
        satellite=satellite,
        product_version=version,
        acquired_at=acquired_at,
        latitude=latitude,
        longitude=longitude,
        confidence_raw=confidence_raw,
        confidence_score=confidence_score,
        frp_mw=_optional_float(row, "frp"),
        brightness=brightness,
        day_night=day_night,
        scan_km=_optional_float(row, "scan"),
        track_km=_optional_float(row, "track"),
        thermal_type=(row.get("type", "").strip() or None),
        raw_payload=dict(row),
    )


def parse_csv(content: str, *, product: str) -> tuple[list[ThermalDetection], list[str]]:
    """Normalise un export CSV complet.

    Retourne les détections valides et les motifs de rejet. Une ligne
    inexploitable est comptée puis ignorée : elle ne doit pas faire échouer
    l'import entier (§16.2, « erreur métier isolée »).
    """
    detections: list[ThermalDetection] = []
    rejections: list[str] = []

    reader: Iterable[dict[str, Any]] = csv.DictReader(content.splitlines())

    for index, raw_row in enumerate(reader, start=2):  # ligne 1 = en-têtes
        row = {key: (value or "") for key, value in raw_row.items() if key is not None}
        try:
            detections.append(parse_row(row, product=product))
        except FirmsParseError as exc:
            rejections.append(f"ligne {index} : {exc}")

    return detections, rejections


class FirmsQuotaError(RuntimeError):
    """Quota atteint. L'appelant doit patienter, pas réessayer immédiatement."""

    def __init__(self, retry_after_seconds: int | None) -> None:
        super().__init__("Quota FIRMS atteint.")
        self.retry_after_seconds = retry_after_seconds


class FirmsUnavailableError(RuntimeError):
    """FIRMS injoignable ou en erreur. L'import échoue sans corrompre la base."""


def looks_like_csv(body: str) -> bool:
    """FIRMS répond parfois 200 avec un message d'erreur en texte brut.

    Une clé invalide ou un quota dépassé peut arriver ainsi. Sans ce contrôle,
    le message serait analysé comme un CSV, produirait zéro détection, et
    l'import serait déclaré réussi alors qu'il n'a rien importé — le pire des
    résultats, puisqu'il est silencieux.
    """
    first_line = body.lstrip().split("\n", 1)[0].lower()
    return "latitude" in first_line and "longitude" in first_line


class FirmsClient:
    """Client de l'API Area de NASA FIRMS.

    Référence : cahier §9.1 et §16.3.

    Le quota annoncé par FIRMS est de 5 000 transactions par tranche de dix
    minutes. Une requête par produit et par emprise, toutes les dix minutes,
    reste très en deçà : le garde-fou ici porte sur le comportement en cas de
    dépassement, pas sur un décompte que nous ne pouvons pas connaître avec
    certitude.
    """

    key = "firms"

    def __init__(self, client: httpx.Client, map_key: str, base_url: str = BASE_URL) -> None:
        if map_key.strip() == "":
            raise ValueError("Clé FIRMS absente : le connecteur ne peut pas être construit.")
        self._client = client
        self._map_key = map_key
        self._base_url = base_url.rstrip("/")

    def fetch_area(
        self,
        *,
        product: str,
        bbox: BoundingBox,
        day_range: int = 1,
        start_date: datetime | None = None,
    ) -> str:
        """Récupère le CSV brut d'un produit sur une emprise.

        Le corps est retourné tel quel : l'archivage du fichier brut précède
        toute analyse (§16.1, étape 6). Ce qui n'a pas été conservé ne peut pas
        être rejoué.
        """
        if not 1 <= day_range <= MAX_DAY_RANGE:
            raise ValueError(f"day_range doit être compris entre 1 et {MAX_DAY_RANGE}.")

        path = f"{self._base_url}/{self._map_key}/{product}/{bbox.as_firms_area()}/{day_range}"
        if start_date is not None:
            path = f"{path}/{start_date.astimezone(UTC).date().isoformat()}"

        try:
            response = self._client.get(path, timeout=120.0)
        except httpx.HTTPError as exc:
            raise FirmsUnavailableError(f"Appel FIRMS impossible : {exc}") from exc

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise FirmsQuotaError(
                int(retry_after) if retry_after is not None and retry_after.isdigit() else None
            )

        if response.status_code >= 400:
            # Le corps porte l'explication — « Invalid day range », « Invalid
            # MAP_KEY »… La taire obligerait à sonder l'API à la main pour
            # comprendre. Il est tronqué et l'URL n'est jamais journalisée :
            # c'est elle, et non le message, qui contient la clé.
            detail = response.text.strip().replace("\n", " ")[:160]
            raise FirmsUnavailableError(f"FIRMS a répondu {response.status_code} : {detail}")

        body = response.text
        if not looks_like_csv(body):
            # Le message d'erreur est tronqué : il peut contenir la clé.
            raise FirmsUnavailableError(
                f"Réponse FIRMS inattendue, non CSV : {body.strip()[:120]!r}"
            )

        return body

    def fetch_detections(
        self,
        *,
        bbox: BoundingBox,
        products: Iterable[str] = DEFAULT_PRODUCTS,
        day_range: int = 1,
    ) -> Iterator[tuple[str, str]]:
        """Itère sur (produit, CSV brut) pour chaque jeu configuré.

        Un produit indisponible n'interrompt pas les autres : les capteurs sont
        indépendants, et perdre MODIS ne doit pas faire perdre VIIRS (§2.4,
        dégradation maîtrisée).
        """
        for product in products:
            yield product, self.fetch_area(product=product, bbox=bbox, day_range=day_range)


def split_bbox(bbox: BoundingBox, max_span_deg: float = 10.0) -> list[BoundingBox]:
    """Découpe une emprise trop large en sous-emprises.

    L'API Area limite la taille de la zone demandée. Le découpage permet aussi
    de reprendre un import partiel sans tout rejouer (§16.3).
    """
    if max_span_deg <= 0:
        raise ValueError("max_span_deg doit être strictement positif.")

    lon_steps = max(1, int(-(-(bbox.max_lon - bbox.min_lon) // max_span_deg)))
    lat_steps = max(1, int(-(-(bbox.max_lat - bbox.min_lat) // max_span_deg)))

    lon_size = (bbox.max_lon - bbox.min_lon) / lon_steps
    lat_size = (bbox.max_lat - bbox.min_lat) / lat_steps

    tiles: list[BoundingBox] = []
    for i in range(lon_steps):
        for j in range(lat_steps):
            tiles.append(
                BoundingBox(
                    min_lon=bbox.min_lon + i * lon_size,
                    min_lat=bbox.min_lat + j * lat_size,
                    max_lon=bbox.min_lon + (i + 1) * lon_size,
                    max_lat=bbox.min_lat + (j + 1) * lat_size,
                )
            )
    return tiles


def most_recent_acquisition(detections: Iterable[ThermalDetection]) -> datetime | None:
    """Heure d'acquisition la plus récente du lot.

    C'est cette valeur, et non l'heure d'import, qui alimente `source_data_at`
    et donc la fraîcheur affichée sur /statut. Les confondre présenterait un
    import réussi sur des données vieilles de six heures comme une donnée
    fraîche (§5.13).
    """
    times = [detection.acquired_at for detection in detections]
    return max(times) if times else None


def is_stale(acquired_at: datetime, now: datetime, max_age: timedelta = timedelta(hours=6)) -> bool:
    """Une acquisition dépasse-t-elle la latence attendue de FIRMS ?

    FIRMS annonce une disponibilité en général sous trois heures. Au-delà de
    six, il ne s'agit plus du délai normal mais d'un retard à signaler.
    """
    return now - acquired_at > max_age


def deduplicate(detections: Iterable[ThermalDetection]) -> Iterator[ThermalDetection]:
    """Élimine les doublons d'un même lot, la première occurrence gagnant.

    FIRMS peut republier une observation d'un appel à l'autre ; la contrainte
    d'unicité en base tranche en dernier ressort, mais dédoublonner en amont
    évite des transactions inutiles.
    """
    seen: set[str] = set()
    for detection in detections:
        if detection.provider_key in seen:
            continue
        seen.add(detection.provider_key)
        yield detection
