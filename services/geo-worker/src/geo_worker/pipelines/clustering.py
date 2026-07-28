"""Rattachement des détections aux événements.

Référence : cahier §17.2, §17.6 et FR-040 à FR-043.

L'algorithme est **déterministe** : les détections sont traitées dans un ordre
total et stable, et les égalités de score sont départagées par un critère fixe.
C'est la condition du critère de sortie du jalon — rejouer une saison doit
donner le même résultat, sans quoi aucun résultat n'est explicable.

Un traitement automatique ne crée que des événements au niveau de vérification
`probable_event`. Il ne peut ni les confirmer officiellement, ni leur donner un
statut opérationnel : la base le refuserait de toute façon (FR-047).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

logger = get_logger(__name__)


@dataclass
class ClusteringResult:
    attached: int = 0
    created: int = 0
    touched_events: set[str] = field(default_factory=set)

    @property
    def processed(self) -> int:
        return self.attached + self.created


def _unattached_detections(conn: psycopg.Connection[Any], limit: int) -> list[dict[str, Any]]:
    """Détections publiables sans événement, dans un ordre total et stable.

    L'ordre chronologique n'est pas seulement esthétique : la fenêtre spatiale
    dépend du temps écoulé depuis la dernière observation de l'événement, donc
    traiter dans le désordre changerait les rattachements.

    `provider_key` départage les acquisitions simultanées — fréquentes, un
    satellite produisant plusieurs pixels à la même seconde.
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
            order by d.acquired_at, d.provider_key
            limit %(limit)s
            """,
            {"limit": limit},
        )
        return cur.fetchall()


def _candidates(
    conn: psycopg.Connection[Any],
    *,
    detection: dict[str, Any],
    params: ClusteringParams,
) -> list[dict[str, Any]]:
    """Événements auxquels la détection pourrait se rattacher.

    La distance est mesurée jusqu'à la détection membre la plus proche, pas
    jusqu'au centre de l'événement : un feu allongé sur cinq kilomètres a un
    centre éloigné de ses deux extrémités, et mesurer depuis le centre le
    couperait en deux événements.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            with point as (
              select extensions.st_setsrid(
                extensions.st_makepoint(%(lon)s::double precision, %(lat)s::double precision),
                4326
              )::extensions.geography as g
            )
            select
              e.id,
              e.public_id,
              e.created_at,
              extract(epoch from (%(acquired_at)s - e.last_detected_at)) / 3600.0 as hours_elapsed,
              min(extensions.st_distance(d.location::extensions.geography, point.g)) as distance_m
            from fire.events e
            join fire.event_detections ed on ed.event_id = e.id
            join fire.detections d
              on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
            cross join point
            where e.freshness_status <> 'archived'
              and e.last_detected_at <= %(acquired_at)s
              and e.last_detected_at >= %(acquired_at)s - make_interval(
                    hours => %(window_hours)s::integer
                  )
              and extensions.st_dwithin(
                    d.location::extensions.geography, point.g, %(max_radius)s::double precision
                  )
            group by e.id, e.public_id, e.created_at, e.last_detected_at
            -- Ordre total : le score départage, puis la date de création, puis
            -- l'identifiant. Sans quoi deux exécutions pourraient différer.
            order by distance_m, e.created_at, e.public_id
            """,
            {
                "lon": detection["lon"],
                "lat": detection["lat"],
                "acquired_at": detection["acquired_at"],
                "window_hours": int(params.attach_window_hours),
                "max_radius": params.max_radius_m,
            },
        )
        return cur.fetchall()


def _create_event(
    conn: psycopg.Connection[Any], *, detection: dict[str, Any], params: ClusteringParams
) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into fire.events (
              freshness_status, verification_status,
              first_detected_at, last_detected_at, representative_point,
              detection_count, sensor_count, confidence_level, confidence_score,
              algorithm_version
            )
            values (
              'new', 'probable_event',
              %(acquired_at)s, %(acquired_at)s,
              extensions.st_setsrid(
                extensions.st_makepoint(%(lon)s::double precision, %(lat)s::double precision),
                4326
              ),
              0, 0, 'low', 0, %(version)s
            )
            returning id, public_id
            """,
            {
                "acquired_at": detection["acquired_at"],
                "lon": detection["lon"],
                "lat": detection["lat"],
                "version": params.version,
            },
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Création d'événement sans retour.")
        return str(row["id"])


def _attach(
    conn: psycopg.Connection[Any],
    *,
    event_id: str,
    detection: dict[str, Any],
    score: float,
    params: ClusteringParams,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into fire.event_detections (
              event_id, detection_id, detection_acquired_at, method, score, algorithm_version
            )
            values (%(event_id)s, %(detection_id)s, %(acquired_at)s, 'auto', %(score)s, %(version)s)
            on conflict (detection_id, detection_acquired_at) do nothing
            """,
            {
                "event_id": event_id,
                "detection_id": detection["id"],
                "acquired_at": detection["acquired_at"],
                "score": round(score, 3),
                "version": params.version,
            },
        )


def _finalize(conn: psycopg.Connection[Any], event_id: str, params: ClusteringParams) -> None:
    """Recalcule les agrégats puis la fiabilité, et publie la chronologie."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("select * from fire.recompute_event_aggregates(%s)", (event_id,))
        stats = cur.fetchone()
        if stats is None:
            raise RuntimeError(f"Agrégats introuvables pour {event_id}.")

        score = confidence_score(
            detection_count=stats["detection_count"],
            sensor_count=stats["sensor_count"],
            mean_provider_confidence=(
                None if stats["mean_confidence"] is None else float(stats["mean_confidence"])
            ),
            known_source_count=stats["known_source_count"],
            span_hours=float(stats["span_hours"]),
        )

        cur.execute(
            """
            update fire.events
            set confidence_score = %(score)s,
                confidence_level = %(level)s,
                algorithm_version = %(version)s
            where id = %(id)s
            returning public_id, first_detected_at, last_detected_at, detection_count, sensor_count
            """,
            {
                "score": score,
                "level": confidence_level(score),
                "version": params.version,
                "id": event_id,
            },
        )
        event = cur.fetchone()
        if event is None:
            return

        # Chronologie. Les clés de déduplication rendent la génération
        # rejouable : réexécuter le regroupement ne duplique aucune entrée
        # (FR-058).
        cur.execute(
            """
            insert into fire.event_timeline_entries (
              event_id, entry_type, provenance, occurred_at, title, summary,
              visibility, deduplication_key
            )
            values
              (%(id)s, 'detection', 'observation', %(first)s,
               'Première détection thermique',
               'Anomalie thermique observée par satellite.',
               'public', %(key_first)s),
              (%(id)s, 'grouping', 'algorithmic_inference', %(last)s,
               'Regroupement en événement probable',
               %(summary)s,
               'public', %(key_group)s)
            on conflict (deduplication_key) do nothing
            """,
            {
                "id": event_id,
                "first": event["first_detected_at"],
                "last": event["last_detected_at"],
                "key_first": f"{event['public_id']}:first-detection",
                "key_group": f"{event['public_id']}:grouping:{params.version}",
                "summary": (
                    f"{event['detection_count']} détection(s) sur "
                    f"{event['sensor_count']} capteur(s) regroupées par l'algorithme "
                    f"{params.version}."
                ),
            },
        )


def cluster_detections(
    conn: psycopg.Connection[Any],
    *,
    params: ClusteringParams | None = None,
    limit: int = 5_000,
) -> ClusteringResult:
    """Rattache les détections orphelines. L'appelant gère la transaction."""
    settings = params or ClusteringParams()
    result = ClusteringResult()

    detections = _unattached_detections(conn, limit)
    logger.info("clustering.started", pending=len(detections), version=settings.version)

    for detection in detections:
        best_event: str | None = None
        best_score = 0.0

        for candidate in _candidates(conn, detection=detection, params=settings):
            hours = float(candidate["hours_elapsed"])
            score = attachment_score(
                distance_m=float(candidate["distance_m"]),
                hours_elapsed=max(0.0, hours),
                params=settings,
            )
            if score > best_score:
                best_score = score
                best_event = str(candidate["id"])

        if best_event is not None and best_score >= settings.min_score:
            event_id = best_event
            _attach(conn, event_id=event_id, detection=detection, score=best_score, params=settings)
            result.attached += 1
        else:
            event_id = _create_event(conn, detection=detection, params=settings)
            _attach(conn, event_id=event_id, detection=detection, score=1.0, params=settings)
            result.created += 1

        result.touched_events.add(event_id)

        # Les agrégats sont rafraîchis à chaque rattachement, et non en fin de
        # passe : la fenêtre spatiale de la détection suivante dépend de
        # `last_detected_at`, qui vient d'être modifié.
        _finalize(conn, event_id, settings)

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
    "spatial_window_m",
]
