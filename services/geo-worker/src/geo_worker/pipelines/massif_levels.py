"""Enregistrement des niveaux d'accès aux massifs.

Référence : cahier v2.1 §9.2 et §20.4, FR-140 ; ADR-026 ; plan J4.

Une ligne par massif et par jour. En conflit, le niveau, la procédure et
le libellé suivent la dernière capture — une ré-émission intra-journalière
remplace la précédente, la valeur courante étant la vérité opposable ; la
première capture (`first_captured_at`, run d'origine) ne bouge pas, et les
révisions se retracent par les JSON bruts archivés à chaque passe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg

from geo_worker.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MassifLevel:
    """Le niveau d'un massif pour un jour, libellé officiel compris."""

    massif_id: str
    massif_name: str
    level: int
    procedure_flag: int
    level_label: str | None


def assemble_levels(
    levels: dict[str, tuple[int, int]],
    names: dict[str, str],
    labels: dict[int, str],
    *,
    department_path: str = "",
) -> tuple[list[MassifLevel], list[str]]:
    """Croise niveaux, référentiel et libellés ; l'inconnu est dit, pas tu.

    Le JSON quotidien préfixe toujours l'identifiant par le segment du
    département (« 61 » = 6 + massif 1) mais les référentiels divergent :
    celui du Var est préfixé (831), celui des Alpes-Maritimes est nu (1) —
    constaté sur les deux sites le 28 août. Le croisement essaie donc la
    clé telle quelle, puis sans son préfixe. Un massif toujours introuvable
    est rejeté et compté — capté sans nom, il ne serait qu'un numéro, et un
    numéro seul n'informe personne.
    """
    assembled: list[MassifLevel] = []
    rejections: list[str] = []
    for massif_id, (level, procedure_flag) in sorted(levels.items()):
        name = names.get(massif_id)
        if name is None and department_path and massif_id.startswith(department_path):
            name = names.get(massif_id[len(department_path) :])
        if name is None:
            rejections.append(f"massif {massif_id} : absent du référentiel des noms")
            continue
        assembled.append(
            MassifLevel(
                massif_id=massif_id,
                massif_name=name,
                level=level,
                procedure_flag=procedure_flag,
                level_label=labels.get(level),
            )
        )
    return assembled, rejections


def record_levels(
    conn: psycopg.Connection[Any],
    *,
    department_code: str,
    valid_on: date,
    levels: list[MassifLevel],
    source_url: str,
    import_run_id: str | None,
) -> tuple[int, int]:
    """Range les niveaux du jour — (créés, mis à jour)."""
    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        for item in levels:
            cur.execute(
                """
                insert into app.massif_access_levels
                  (department_code, massif_id, massif_name, valid_on, level,
                   procedure_flag, level_label, source_url, import_run_id)
                values (%(dept)s, %(massif)s, %(name)s, %(valid_on)s, %(level)s,
                        %(procedure)s, %(label)s, %(source)s, %(run_id)s)
                on conflict (department_code, massif_id, valid_on) do update set
                  massif_name = excluded.massif_name,
                  level = excluded.level,
                  procedure_flag = excluded.procedure_flag,
                  level_label = excluded.level_label,
                  source_url = excluded.source_url,
                  last_captured_at = now()
                returning (xmax = 0) as inserted
                """,
                {
                    "dept": department_code,
                    "massif": item.massif_id,
                    "name": item.massif_name,
                    "valid_on": valid_on,
                    "level": item.level,
                    "procedure": item.procedure_flag,
                    "label": item.level_label,
                    "source": source_url,
                    "run_id": import_run_id,
                },
            )
            row = cur.fetchone()
            if row is not None and bool(row[0]):
                inserted += 1
            else:
                updated += 1

    logger.info(
        "massifs.recorded",
        department=department_code,
        valid_on=valid_on.isoformat(),
        inserted=inserted,
        updated=updated,
    )
    return inserted, updated


__all__ = ["MassifLevel", "assemble_levels", "record_levels"]
