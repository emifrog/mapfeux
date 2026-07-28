"""Import des limites communales.

Référence : cahier §16.7 et §13.2.

Le pipeline suit la règle du §16.7 : staging complet, validation des codes,
correction géométrique, puis publication transactionnelle. Un import qui échoue
à mi-chemin ne doit jamais laisser un département à moitié réécrit — c'est la
raison d'être de la table temporaire.

Une commune disparue d'un import n'est pas supprimée : elle est datée. Les
fusions de communes sont fréquentes, et une détection historique peut encore
la référencer (§13.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.models import MunicipalityBoundary

logger = get_logger(__name__)

# La géométrie subit trois traitements en base :
#   st_makevalid       corrige les auto-intersections fréquentes du trait de côte
#   st_collectionextract(…, 3) ne garde que les polygones — st_makevalid peut
#                      renvoyer une collection mêlant lignes et points
#   st_multi           la colonne est typée MultiPolygon, y compris pour une
#                      commune d'un seul tenant
_GEOMETRY_EXPR = """
extensions.st_multi(
  extensions.st_collectionextract(
    extensions.st_makevalid(
      extensions.st_setsrid(extensions.st_geomfromgeojson(%(geometry)s), 4326)
    ),
    3
  )
)
"""


@dataclass
class MunicipalityImportResult:
    inserted: int = 0
    updated: int = 0
    retired: int = 0
    rejected: int = 0

    @property
    def total_written(self) -> int:
        return self.inserted + self.updated


def import_department(
    conn: psycopg.Connection[Any],
    *,
    department_code: str,
    boundaries: list[MunicipalityBoundary],
) -> MunicipalityImportResult:
    """Publie les communes d'un département en une seule transaction.

    L'appelant est responsable du `commit` : le pipeline peut ainsi enchaîner
    plusieurs départements et tout annuler si l'un d'eux échoue.
    """
    if not boundaries:
        raise ValueError(f"Aucune commune à importer pour le département {department_code}.")

    result = MunicipalityImportResult()
    log = logger.bind(department=department_code)

    with conn.cursor() as cur:
        # Zone de staging : la géométrie n'entre dans la table publiée qu'une
        # fois l'intégralité du département validée.
        cur.execute("""
            create temp table staging_municipalities (
              insee_code text primary key,
              name text not null,
              department_code text not null,
              postal_codes text[] not null,
              geometry extensions.geometry(MultiPolygon, 4326) not null,
              centroid extensions.geometry(Point, 4326),
              area_km2 numeric,
              source_version text not null
            ) on commit drop
        """)

        for boundary in boundaries:
            cur.execute(
                f"""
                insert into staging_municipalities
                  (insee_code, name, department_code, postal_codes, geometry, centroid,
                   area_km2, source_version)
                values (
                  %(insee_code)s, %(name)s, %(department_code)s, %(postal_codes)s::text[],
                  {_GEOMETRY_EXPR},
                  -- Transtypages explicites : sur un paramètre pouvant être NULL,
                  -- PostgreSQL ne peut pas inférer le type et refuse la requête.
                  case
                    when %(lon)s::double precision is null then null
                    else extensions.st_setsrid(
                      extensions.st_makepoint(%(lon)s::double precision, %(lat)s::double precision),
                      4326
                    )
                  end,
                  %(area_km2)s::numeric, %(source_version)s
                )
                on conflict (insee_code) do nothing
                """,  # noqa: S608 — _GEOMETRY_EXPR est une constante du module
                {
                    "insee_code": boundary.insee_code,
                    "name": boundary.name,
                    "department_code": boundary.department_code,
                    "postal_codes": list(boundary.postal_codes),
                    "geometry": boundary.geometry_geojson,
                    "lon": boundary.centroid_lon,
                    "lat": boundary.centroid_lat,
                    "area_km2": boundary.area_km2,
                    "source_version": boundary.source_version,
                },
            )

        # Une géométrie vide après correction signale une donnée source
        # inexploitable : on la retire plutôt que de publier un polygone nul.
        cur.execute("""
            delete from staging_municipalities
            where extensions.st_isempty(geometry)
        """)
        result.rejected = cur.rowcount

        cur.execute("select count(*) from staging_municipalities")
        row = cur.fetchone()
        staged = 0 if row is None else int(row[0])
        if staged == 0:
            raise ValueError(
                f"Staging vide pour le département {department_code} : import interrompu."
            )

        # Publication. Le centroïde manquant est calculé par PostGIS avec
        # st_pointonsurface, qui garantit un point à l'intérieur du polygone —
        # ce qu'un centroïde géométrique ne garantit pas sur une commune
        # concave ou littorale.
        cur.execute("""
            insert into geo.municipalities
              (insee_code, department_code, name, normalized_name, postal_codes,
               geometry, centroid, area_km2, source_version, valid_from, valid_to)
            select
              s.insee_code,
              s.department_code,
              s.name,
              geo.normalize_name(s.name),
              s.postal_codes,
              s.geometry,
              coalesce(s.centroid, extensions.st_pointonsurface(s.geometry)),
              coalesce(s.area_km2, extensions.st_area(s.geometry::extensions.geography) / 1e6),
              s.source_version,
              current_date,
              null
            from staging_municipalities s
            on conflict (insee_code) do update set
              department_code = excluded.department_code,
              name = excluded.name,
              normalized_name = excluded.normalized_name,
              postal_codes = excluded.postal_codes,
              geometry = excluded.geometry,
              centroid = excluded.centroid,
              area_km2 = excluded.area_km2,
              source_version = excluded.source_version,
              -- Une commune réapparue dans la source redevient en vigueur.
              valid_to = null
            returning (xmax = 0) as was_inserted
        """)

        written = cur.fetchall()
        result.inserted = sum(1 for (was_inserted,) in written if was_inserted)
        result.updated = len(written) - result.inserted

        # Communes du département absentes de la source : datées, jamais
        # supprimées. Une fusion ne doit pas effacer l'historique (§13.2).
        cur.execute(
            """
            update geo.municipalities m
            set valid_to = current_date
            where m.department_code = %(department)s
              and m.valid_to is null
              and not exists (
                select 1 from staging_municipalities s where s.insee_code = m.insee_code
              )
            """,
            {"department": department_code},
        )
        result.retired = cur.rowcount

        cur.execute("drop table staging_municipalities")

    log.info(
        "municipalities.imported",
        inserted=result.inserted,
        updated=result.updated,
        retired=result.retired,
        rejected=result.rejected,
    )
    return result
