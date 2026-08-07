"""Régions et départements dans le référentiel des territoires.

Référence : cahier §13.1, FR-014, FR-015 et §16.7.

Les géométries ne viennent pas de l'API : elles sont construites **en base**
par union des communes déjà importées — une seule source de vérité
géométrique, pas deux tracés qui divergent le long des mêmes frontières. La
simplification (~100 m) sert le cadrage et les agrégats nationaux ; le tracé
fin reste porté par les communes, et la diffusion cartographique aura sa
propre chaîne (PMTiles).

Un territoire nouveau naît en `draft` : la vue publique ne montre que `pilot`
et `active` (FR-014), donc rien ne devient « ouvert » du seul fait de
l'import. Un territoire existant conserve statut, slug, centre et zoom —
l'import complète, il ne rétrograde jamais une décision d'ouverture.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.models import AdministrativeUnit

logger = get_logger(__name__)

#: Tolérance de simplification en degrés (~100 m). Assez fin pour un cadrage
#: départemental honnête, assez grossier pour que 96 emprises tiennent dans une
#: réponse. La simplification est faite territoire par territoire : deux
#: départements voisins peuvent laisser un jour un liseré à fort zoom — le
#: tracé de référence reste celui des communes.
SIMPLIFY_TOLERANCE_DEG = 0.001

DEFAULT_DEPARTMENT_ZOOM = 9.0
DEFAULT_REGION_ZOOM = 7.0


@dataclass(frozen=True, slots=True)
class TerritoryImportResult:
    created: int = 0
    updated: int = 0
    geometry_missing: int = 0


def slugify(name: str) -> str:
    """Clé d'URL d'un territoire, conforme à `territories_slug_format`.

    « Provence-Alpes-Côte d'Azur » devient `provence-alpes-cote-d-azur` — la
    forme que le seed a déjà figée : l'algorithme doit reproduire l'existant,
    pas inventer une seconde convention.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    words = "".join(c if c.isalnum() else " " for c in ascii_only).split()
    return "-".join(words)


_UPSERT_DEPARTMENT = """
with u as (
  select extensions.st_union(m.geometry) as geom
  from geo.municipalities m
  where m.department_code = %(code)s
    and m.valid_to is null
)
insert into app.territories
  (parent_id, type, code, slug, name, short_name, center, default_zoom, status, geometry)
select
  null, 'department', %(code)s, %(slug)s, %(name)s, %(code)s,
  extensions.st_pointonsurface(u.geom),
  %(zoom)s, 'draft',
  extensions.st_multi(
    extensions.st_collectionextract(
      extensions.st_makevalid(
        extensions.st_simplifypreservetopology(u.geom, %(tolerance)s)
      ),
      3
    )
  )
from u
where u.geom is not null
on conflict (type, code) do update set
  name = excluded.name,
  geometry = excluded.geometry,
  center = coalesce(app.territories.center, excluded.center),
  updated_at = now()
returning (created_at = updated_at) as just_created
"""

_UPSERT_REGION = """
with u as (
  select extensions.st_union(d.geometry) as geom
  from app.territories d
  where d.type = 'department'
    and d.code = any(%(department_codes)s)
    and d.geometry is not null
)
insert into app.territories
  (parent_id, type, code, slug, name, short_name, center, default_zoom, status, geometry)
select
  (select id from app.territories where type = 'country' and code = %(country)s),
  'region', %(code)s, %(slug)s, %(name)s, null,
  extensions.st_pointonsurface(u.geom),
  %(zoom)s, 'draft',
  extensions.st_multi(
    extensions.st_collectionextract(extensions.st_makevalid(u.geom), 3)
  )
from u
where u.geom is not null
on conflict (type, code) do update set
  name = excluded.name,
  geometry = excluded.geometry,
  center = coalesce(app.territories.center, excluded.center),
  parent_id = coalesce(app.territories.parent_id, excluded.parent_id),
  updated_at = now()
returning (created_at = updated_at) as just_created
"""

_ATTACH_DEPARTMENTS = """
update app.territories d
set parent_id = r.id
from app.territories r
where d.type = 'department'
  and d.code = any(%(department_codes)s)
  and d.parent_id is null
  and r.type = 'region'
  and r.code = %(region_code)s
"""

_REFRESH_COUNTRY = """
with u as (
  select extensions.st_union(r.geometry) as geom
  from app.territories r
  where r.type = 'region' and r.geometry is not null
)
update app.territories c
set geometry = extensions.st_multi(
      extensions.st_collectionextract(extensions.st_makevalid(u.geom), 3)
    ),
    updated_at = now()
from u
where c.type = 'country' and c.code = %(country)s and u.geom is not null
"""


def import_departments(
    conn: psycopg.Connection[Any], departments: list[AdministrativeUnit]
) -> TerritoryImportResult:
    """Un département par transaction : une reprise rejoue les manquants.

    L'union des communes d'un département est le coût dominant ; la faire
    statement par statement borne chaque transaction et laisse la base
    cohérente entre deux départements.
    """
    created = updated = missing = 0
    for unit in departments:
        with conn.cursor() as cur:
            cur.execute(
                _UPSERT_DEPARTMENT,
                {
                    "code": unit.code,
                    "slug": slugify(unit.name),
                    "name": unit.name,
                    "zoom": DEFAULT_DEPARTMENT_ZOOM,
                    "tolerance": SIMPLIFY_TOLERANCE_DEG,
                },
            )
            row = cur.fetchone()
        conn.commit()

        if row is None:
            # Aucune commune importée pour ce département : pas de géométrie,
            # donc pas de territoire — l'inverse fabriquerait une coquille vide.
            missing += 1
            logger.warning("territories.department_without_municipalities", code=unit.code)
        elif bool(row[0]):
            created += 1
        else:
            updated += 1

    return TerritoryImportResult(created=created, updated=updated, geometry_missing=missing)


def import_regions(
    conn: psycopg.Connection[Any],
    regions: list[AdministrativeUnit],
    departments: list[AdministrativeUnit],
    country_code: str = "FR",
) -> TerritoryImportResult:
    """Régions par union des départements, puis rattachement parent."""
    members: dict[str, list[str]] = {}
    for department in departments:
        if department.region_code is not None:
            members.setdefault(department.region_code, []).append(department.code)

    created = updated = missing = 0
    for unit in regions:
        codes = members.get(unit.code, [])
        if not codes:
            # Région sans département métropolitain — les DROM en vague B.
            continue
        with conn.cursor() as cur:
            cur.execute(
                _UPSERT_REGION,
                {
                    "code": unit.code,
                    "slug": slugify(unit.name),
                    "name": unit.name,
                    "zoom": DEFAULT_REGION_ZOOM,
                    "country": country_code,
                    "department_codes": codes,
                },
            )
            row = cur.fetchone()
            if row is None:
                missing += 1
            else:
                cur.execute(
                    _ATTACH_DEPARTMENTS,
                    {"department_codes": codes, "region_code": unit.code},
                )
                if bool(row[0]):
                    created += 1
                else:
                    updated += 1
        conn.commit()

    with conn.cursor() as cur:
        cur.execute(_REFRESH_COUNTRY, {"country": country_code})
    conn.commit()

    return TerritoryImportResult(created=created, updated=updated, geometry_missing=missing)


__all__ = [
    "DEFAULT_DEPARTMENT_ZOOM",
    "DEFAULT_REGION_ZOOM",
    "SIMPLIFY_TOLERANCE_DEG",
    "TerritoryImportResult",
    "import_departments",
    "import_regions",
    "slugify",
]
