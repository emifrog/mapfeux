"""Rattachement des détections aux événements.

Référence : cahier §17.2, §17.6 et FR-040 à FR-043.

L'algorithme est **déterministe** : les détections sont traitées dans un ordre
total et stable, et les égalités de score sont départagées par un critère fixe.
C'est la condition du critère de sortie du jalon — rejouer une saison doit
donner le même résultat, sans quoi aucun résultat n'est explicable.

Un traitement automatique ne crée que des événements au niveau de vérification
`probable_event`. Il ne peut ni les confirmer officiellement, ni leur donner un
statut opérationnel : la base le refuserait de toute façon (FR-047).

La recherche des candidats se fait **en mémoire**. Une première version
interrogeait la base pour chaque détection : sur 931 détections, près de trois
mille allers-retours et deux minutes, presque entièrement passées à attendre le
réseau. Les positions ne changent jamais, seule l'appartenance évolue : un index
construit une fois suffit, et la boucle reste identique. Les distances restent
mesurées sur l'ellipsoïde WGS84, comme le faisait PostGIS.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

from geo_worker.clustering import (
    ClusteringParams,
    attachment_score,
    confidence_level,
    confidence_score,
    spatial_window_m,
)
from geo_worker.logging import get_logger
from geo_worker.spatial import NeighbourIndex

logger = get_logger(__name__)


@dataclass
class ClusteringResult:
    attached: int = 0
    created: int = 0
    touched_events: set[str] = field(default_factory=set)
    truncated: bool = False
    """La passe a rempli son plafond : d'autres orphelines attendent peut-être.

    Conservateur par construction — si le nombre d'orphelines vaut exactement le
    plafond, le drapeau est levé alors qu'il ne restait rien. Se tromper dans ce
    sens fait tourner une passe pour rien ; se tromper dans l'autre laisserait
    une file grossir sans que personne le sache.
    """

    @property
    def processed(self) -> int:
        return self.attached + self.created


@dataclass
class _Event:
    """État courant d'un événement pendant la passe.

    `public_id` sert de dernier critère de départage. Pour un événement créé
    dans cette passe, il n'est pas encore attribué : on lui substitue son rang
    de création, en chaîne à largeur fixe. La substitution est sans risque car
    deux événements ne sont comparés sur `public_id` qu'à `created_at` égal, et
    les nouveaux portent tous l'horodatage de la transaction courante, qui
    diffère de celui de tout événement déjà en base.
    """

    event_id: str
    public_id: str
    created_at: datetime
    first_detected_at: datetime
    last_detected_at: datetime
    lon: float
    lat: float


def _pending_detections(conn: psycopg.Connection[Any], limit: int | None) -> list[dict[str, Any]]:
    """Détections publiables sans événement, dans un ordre total et stable.

    L'ordre chronologique n'est pas seulement esthétique : la fenêtre spatiale
    dépend du temps écoulé depuis la dernière observation de l'événement, donc
    traiter dans le désordre changerait les rattachements.

    `provider_key` départage les acquisitions simultanées — fréquentes, un
    satellite produisant plusieurs pixels à la même seconde.

    `limit` à `None` lève le plafond : PostgreSQL lit `limit null` comme
    l'absence de borne, ce qui évite de brancher la requête sur deux textes.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select d.id, d.acquired_at, d.provider_key, d.sensor,
                   extensions.st_x(d.location) as lon,
                   extensions.st_y(d.location) as lat
            from fire.detections d
            left join fire.event_detections ed
              on ed.detection_id = d.id and ed.detection_acquired_at = d.acquired_at
            where ed.detection_id is null
              and d.is_public
              -- Une détection classée source connue ne fonde ni ne rejoint un
              -- événement : Fos-sur-Mer produisait un « événement » de 22
              -- jours, invariant aux paramètres (dépouillement du 8 août).
              -- Elle reste en base, publiable et classée — FR-036 : la
              -- correspondance classe, elle ne supprime jamais.
              and d.known_source_id is null
            order by d.acquired_at, d.provider_key
            limit %(limit)s
            """,
            {"limit": limit},
        )
        return cur.fetchall()


def pass_was_capped(fetched: int, limit: int | None) -> bool:
    """La passe a-t-elle rempli son plafond ?

    Isolée du reste pour être vérifiable sans base : c'est la règle qui décide
    si l'appelant doit repasser, et la laisser en ligne dans `cluster_detections`
    la rendait invérifiable autrement qu'en montant tout le pipeline.

    Une passe qui ramène exactement son plafond est déclarée tronquée, faute de
    pouvoir distinguer « il n'en restait pas plus » de « il en reste » sans une
    requête supplémentaire. Le coût de l'erreur est une passe à vide.
    """
    return limit is not None and fetched >= limit


def pending_detection_count(conn: psycopg.Connection[Any]) -> int:
    """Nombre de détections publiables encore sans événement.

    Même prédicat que `_pending_detections`, sans les colonnes ni la borne. Sert
    aux outils de mesure à vérifier qu'ils ont bien consommé tout le corpus :
    une ligne de calibration établie sur une tranche, mais présentée comme
    portant sur l'ensemble, est pire qu'une ligne absente.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
            from fire.detections d
            left join fire.event_detections ed
              on ed.detection_id = d.id and ed.detection_acquired_at = d.acquired_at
            where ed.detection_id is null
              and d.is_public
              and d.known_source_id is null
            """
        )
        row = cur.fetchone()
    return 0 if row is None else int(row[0])


def delete_algorithmic_events(conn: psycopg.Connection[Any]) -> int:
    """Supprime les événements algorithmiques, jamais les décisions humaines.

    Le prédicat est le seul endroit qui définit « algorithmique » : un événement
    sans statut officiel, sans correction manuelle, ni masqué, ni issu du jeu de
    démonstration. Le banc de calibration et le remplacement de corpus partagent
    cette définition — dupliquée, elle divergerait un jour en silence, et l'un
    des deux effacerait ce que l'autre protège.

    **Ne valide pas.** L'appelant enchaîne l'opération suivante — regroupement
    ou rechargement — et valide l'ensemble, de sorte qu'un remplacement est tout
    ou rien. Une version antérieure du banc validait la suppression seule : un
    processus tué pendant la passe suivante laissait le corpus sans aucun
    événement, ses détections toutes orphelines. C'est arrivé.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from fire.events
            where algorithm_version <> 'demo-fixture'
              and official_control_status is null
              and verification_status in ('satellite_detection', 'probable_event')
              and freshness_status <> 'hidden'
              and manual_state = '{}'::jsonb
            """
        )
        return cur.rowcount


def _existing_events(
    conn: psycopg.Connection[Any], *, floor: datetime
) -> tuple[list[_Event], list[float], list[float], list[int]]:
    """Événements rattachables et positions de leurs membres.

    `floor` écarte ce qui ne pourra jamais servir : un événement dont la
    dernière observation précède la plus ancienne détection en attente de plus
    que la fenêtre de rattachement est hors d'atteinte, quel que soit l'ordre de
    traitement. La borne haute, elle, dépend de chaque détection et se vérifie
    dans la boucle.

    La distance est mesurée jusqu'au membre le plus proche, pas jusqu'au centre :
    un feu allongé sur cinq kilomètres a un centre éloigné de ses deux
    extrémités, et mesurer depuis le centre le couperait en deux événements.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id, e.public_id, e.created_at,
                   e.first_detected_at, e.last_detected_at,
                   extensions.st_x(e.representative_point) as event_lon,
                   extensions.st_y(e.representative_point) as event_lat,
                   extensions.st_x(d.location) as lon,
                   extensions.st_y(d.location) as lat
            from fire.events e
            join fire.event_detections ed on ed.event_id = e.id
            join fire.detections d
              on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
            where e.freshness_status <> 'archived'
              and e.last_detected_at >= %(floor)s
            order by e.created_at, e.public_id
            """,
            {"floor": floor},
        )
        rows = cur.fetchall()

    events: list[_Event] = []
    lons: list[float] = []
    lats: list[float] = []
    owners: list[int] = []
    by_id: dict[str, int] = {}

    for row in rows:
        event_id = str(row["id"])
        slot = by_id.get(event_id)
        if slot is None:
            slot = len(events)
            by_id[event_id] = slot
            events.append(
                _Event(
                    event_id=event_id,
                    public_id=str(row["public_id"]),
                    created_at=row["created_at"],
                    first_detected_at=row["first_detected_at"],
                    last_detected_at=row["last_detected_at"],
                    lon=float(row["event_lon"]),
                    lat=float(row["event_lat"]),
                )
            )
        lons.append(float(row["lon"]))
        lats.append(float(row["lat"]))
        owners.append(slot)

    return events, lons, lats, owners


def _transaction_now(conn: psycopg.Connection[Any]) -> datetime:
    with conn.cursor() as cur:
        cur.execute("select now()")
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("La base n'a pas retourné son horloge.")
        return row[0]  # type: ignore[no-any-return]


def _write_new_events(
    conn: psycopg.Connection[Any], events: list[_Event], params: ClusteringParams
) -> None:
    """Insère les événements créés dans la passe et récupère leur `public_id`.

    L'identifiant est engendré côté client : sans lui, il faudrait se fier à
    l'ordre du `returning` pour associer chaque ligne à son état en mémoire, ce
    que PostgreSQL ne garantit pas. L'ordinalité, elle, fixe l'ordre
    d'évaluation des valeurs par défaut, donc l'attribution des `public_id`
    suit l'ordre de création.
    """
    if not events:
        return

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into fire.events (
              id, freshness_status, verification_status,
              first_detected_at, last_detected_at, representative_point,
              detection_count, sensor_count, confidence_level, confidence_score,
              algorithm_version
            )
            select
              t.id, 'new', 'probable_event',
              t.first_at, t.last_at,
              extensions.st_setsrid(extensions.st_makepoint(t.lon, t.lat), 4326),
              0, 0, 'low', 0, %(version)s
            from unnest(
              %(ids)s::uuid[], %(first_at)s::timestamptz[], %(last_at)s::timestamptz[],
              %(lons)s::double precision[], %(lats)s::double precision[]
            ) with ordinality as t(id, first_at, last_at, lon, lat, ord)
            order by t.ord
            returning id, public_id
            """,
            {
                "version": params.version,
                "ids": [e.event_id for e in events],
                "first_at": [e.first_detected_at for e in events],
                "last_at": [e.last_detected_at for e in events],
                "lons": [e.lon for e in events],
                "lats": [e.lat for e in events],
            },
        )
        assigned = {str(row["id"]): str(row["public_id"]) for row in cur.fetchall()}

    for event in events:
        event.public_id = assigned[event.event_id]


def _write_attachments(
    conn: psycopg.Connection[Any],
    rows: list[tuple[str, str, datetime, float]],
    params: ClusteringParams,
) -> None:
    if not rows:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into fire.event_detections (
              event_id, detection_id, detection_acquired_at, method, score, algorithm_version
            )
            select t.event_id, t.detection_id, t.acquired_at, 'auto', t.score, %(version)s
            from unnest(
              %(event_ids)s::uuid[], %(detection_ids)s::uuid[],
              %(acquired)s::timestamptz[], %(scores)s::numeric[]
            ) as t(event_id, detection_id, acquired_at, score)
            on conflict (detection_id, detection_acquired_at) do nothing
            """,
            {
                "version": params.version,
                "event_ids": [r[0] for r in rows],
                "detection_ids": [r[1] for r in rows],
                "acquired": [r[2] for r in rows],
                "scores": [round(r[3], 3) for r in rows],
            },
        )


def _finalize(
    conn: psycopg.Connection[Any], event_ids: list[str], params: ClusteringParams
) -> None:
    """Recalcule les agrégats, la fiabilité, puis publie la chronologie.

    Les trois étapes sont groupées sur l'ensemble des événements touchés. Les
    faire événement par événement coûtait trois allers-retours chacun, pour un
    résultat identique.
    """
    if not event_ids:
        return

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select t.id, r.*
            from unnest(%(ids)s::uuid[]) with ordinality as t(id, ord),
                 lateral fire.recompute_event_aggregates(t.id) as r
            order by t.ord
            """,
            {"ids": event_ids},
        )
        stats = cur.fetchall()

        scores: list[float] = []
        levels: list[str] = []
        for row in stats:
            score = confidence_score(
                detection_count=row["detection_count"],
                sensor_count=row["sensor_count"],
                mean_provider_confidence=(
                    None if row["mean_confidence"] is None else float(row["mean_confidence"])
                ),
                known_source_count=row["known_source_count"],
                span_hours=float(row["span_hours"]),
            )
            scores.append(score)
            levels.append(confidence_level(score))

        cur.execute(
            """
            update fire.events e
            set confidence_score = t.score,
                confidence_level = t.level::app.confidence_level,
                algorithm_version = %(version)s
            from unnest(%(ids)s::uuid[], %(scores)s::numeric[], %(levels)s::text[])
                 as t(id, score, level)
            where e.id = t.id
            returning e.id, e.public_id, e.first_detected_at, e.last_detected_at,
                      e.detection_count, e.sensor_count
            """,
            {
                "version": params.version,
                "ids": [str(row["id"]) for row in stats],
                "scores": scores,
                "levels": levels,
            },
        )
        updated = cur.fetchall()

        # Chronologie. Les clés de déduplication rendent la génération
        # rejouable : réexécuter le regroupement ne duplique aucune entrée
        # (FR-058).
        entries: list[tuple[str, str, str, datetime, str, str, str]] = []
        for event in updated:
            event_id = str(event["id"])
            public_id = str(event["public_id"])
            entries.append(
                (
                    event_id,
                    "detection",
                    "observation",
                    event["first_detected_at"],
                    "Première détection thermique",
                    "Anomalie thermique observée par satellite.",
                    f"{public_id}:first-detection",
                )
            )
            entries.append(
                (
                    event_id,
                    "grouping",
                    "algorithmic_inference",
                    event["last_detected_at"],
                    "Regroupement en événement probable",
                    (
                        f"{event['detection_count']} détection(s) sur "
                        f"{event['sensor_count']} capteur(s) regroupées par l'algorithme "
                        f"{params.version}."
                    ),
                    f"{public_id}:grouping:{params.version}",
                )
            )

        cur.execute(
            """
            insert into fire.event_timeline_entries (
              event_id, entry_type, provenance, occurred_at, title, summary,
              visibility, deduplication_key
            )
            select t.event_id, t.entry_type::fire.timeline_entry_type,
                   t.provenance::app.provenance, t.occurred_at, t.title, t.summary,
                   'public', t.dedup_key
            from unnest(
              %(event_ids)s::uuid[], %(types)s::text[], %(provenances)s::text[],
              %(occurred)s::timestamptz[], %(titles)s::text[], %(summaries)s::text[],
              %(keys)s::text[]
            ) as t(event_id, entry_type, provenance, occurred_at, title, summary, dedup_key)
            on conflict (deduplication_key) do nothing
            """,
            {
                "event_ids": [e[0] for e in entries],
                "types": [e[1] for e in entries],
                "provenances": [e[2] for e in entries],
                "occurred": [e[3] for e in entries],
                "titles": [e[4] for e in entries],
                "summaries": [e[5] for e in entries],
                "keys": [e[6] for e in entries],
            },
        )


def cluster_detections(
    conn: psycopg.Connection[Any],
    *,
    params: ClusteringParams | None = None,
    limit: int | None = 5_000,
) -> ClusteringResult:
    """Rattache les détections orphelines. L'appelant gère la transaction.

    `limit` borne la passe, pour que le traitement périodique garde une
    transaction de taille prévisible. Une passe bornée ne vide pas forcément la
    file : l'appelant doit **soit** répéter tant que `truncated` est vrai, soit
    demander `limit=None` s'il veut une passe unique sur tout le corpus. Ignorer
    les deux revient à mesurer une fraction du corpus en la présentant comme le
    tout — la faute silencieuse que le jalon cherche justement à exclure.
    """
    settings = params or ClusteringParams()
    result = ClusteringResult()

    detections = _pending_detections(conn, limit)
    result.truncated = pass_was_capped(len(detections), limit)
    logger.info(
        "clustering.started",
        pending=len(detections),
        version=settings.version,
        truncated=result.truncated,
    )

    if not detections:
        logger.info("clustering.finished", attached=0, created=0, events=0)
        return result

    window = timedelta(hours=settings.attach_window_hours)
    floor = detections[0]["acquired_at"] - window
    events, lons, lats, owners = _existing_events(conn, floor=floor)
    created_at = _transaction_now(conn)

    # Un seul index pour les membres déjà rattachés et les détections en attente.
    # Les positions sont figées ; seul `owners` évolue au fil de la boucle, ce
    # qui rend visibles aux détections suivantes les événements créés à l'instant.
    base = len(lons)
    lons.extend(float(d["lon"]) for d in detections)
    lats.extend(float(d["lat"]) for d in detections)
    owners.extend(-1 for _ in detections)
    index = NeighbourIndex(lons, lats)

    attachments: list[tuple[str, str, datetime, float]] = []
    new_events: list[_Event] = []

    for position, detection in enumerate(detections):
        acquired_at = detection["acquired_at"]

        # Distance au membre le plus proche, par événement.
        nearest: dict[int, float] = {}
        for point, distance in index.within(
            float(detection["lon"]), float(detection["lat"]), settings.max_radius_m
        ):
            slot = owners[point]
            if slot < 0:
                continue
            if distance < nearest.get(slot, float("inf")):
                nearest[slot] = distance

        # Ordre total : la distance, puis la date de création, puis
        # l'identifiant public. Sans lui, deux exécutions pourraient différer.
        candidates = sorted(
            (distance, events[slot].created_at, events[slot].public_id, slot)
            for slot, distance in nearest.items()
            if events[slot].last_detected_at <= acquired_at
            and events[slot].last_detected_at >= acquired_at - window
        )

        best_slot: int | None = None
        best_score = 0.0
        for distance, _, _, slot in candidates:
            hours = (acquired_at - events[slot].last_detected_at).total_seconds() / 3600.0
            score = attachment_score(
                distance_m=distance,
                hours_elapsed=max(0.0, hours),
                params=settings,
            )
            if score > best_score:
                best_score = score
                best_slot = slot

        if best_slot is not None and best_score >= settings.min_score:
            slot = best_slot
            score = best_score
            result.attached += 1
        else:
            slot = len(events)
            event = _Event(
                event_id=str(uuid.uuid4()),
                # Rang de création à largeur fixe : ordonne les nouveaux
                # événements entre eux tant que leur identifiant public n'est
                # pas attribué.
                public_id=f"{len(new_events):012d}",
                created_at=created_at,
                first_detected_at=acquired_at,
                last_detected_at=acquired_at,
                lon=float(detection["lon"]),
                lat=float(detection["lat"]),
            )
            events.append(event)
            new_events.append(event)
            score = 1.0
            result.created += 1

        target = events[slot]
        # La fenêtre spatiale de la détection suivante dépend de la dernière
        # observation : elle doit rester exacte tout au long de la passe.
        target.last_detected_at = max(target.last_detected_at, acquired_at)
        target.first_detected_at = min(target.first_detected_at, acquired_at)
        owners[base + position] = slot

        attachments.append((target.event_id, str(detection["id"]), acquired_at, score))
        result.touched_events.add(target.event_id)

    _write_new_events(conn, new_events, settings)
    _write_attachments(conn, attachments, settings)
    # Agrégats complets une seule fois par événement. Les recalculer à chaque
    # rattachement rendait le coût quadratique : sur un événement de 570
    # membres, la 570e détection déclenchait un 570e recalcul de l'ensemble.
    _finalize(conn, sorted(result.touched_events), settings)

    logger.info(
        "clustering.finished",
        attached=result.attached,
        created=result.created,
        events=len(result.touched_events),
    )
    return result


__all__ = [
    "ClusteringParams",
    "ClusteringResult",
    "cluster_detections",
    "delete_algorithmic_events",
    "pass_was_capped",
    "pending_detection_count",
    "spatial_window_m",
]
