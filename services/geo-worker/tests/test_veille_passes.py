"""La veille exterieure des passes : ce qui alerte, ce qui signale, ce qui se tait.

Le script vit dans `scripts/` sans dependance hors bibliotheque standard — le
runner GitHub n'a que Python. Il est charge ici par son chemin, comme un module,
pour fixer la regle qui decide d'un courriel : « trop ancienne » et « jamais
livree » alertent, « en retard » signale, le manuel et l'a-venir se taisent.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "veille-passes.py"
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def veille() -> ModuleType:
    spec = importlib.util.spec_from_file_location("veille_passes", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Les dataclasses resolvent leurs annotations via `sys.modules` : un module
    # charge par son chemin doit y etre inscrit avant d'etre execute.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tout_a_jour_ne_dit_rien(veille: ModuleType) -> None:
    verdict = veille.evaluer(
        {
            "firms": {"status": "fresh", "dataAt": "2026-09-17T11:50:00+00:00"},
            "ign_admin_express": {"status": "manual", "dataAt": None},
        },
        NOW,
    )
    assert verdict.alertes == ()
    assert verdict.signalements == ()
    assert not verdict.echoue


def test_trop_ancienne_et_jamais_livree_alertent(veille: ModuleType) -> None:
    verdict = veille.evaluer(
        {
            "firms": {"status": "stale", "dataAt": "2026-09-16T20:00:00+00:00"},
            "radar": {"status": "unavailable", "dataAt": None},
            "cams": {"status": "fresh", "dataAt": "2026-09-17T00:00:00+00:00"},
        },
        NOW,
    )
    assert verdict.alertes == ("firms", "radar")
    assert verdict.echoue


def test_en_retard_signale_sans_alerter(veille: ModuleType) -> None:
    verdict = veille.evaluer(
        {"vigilance": {"status": "delayed", "dataAt": "2026-09-17T04:00:00+00:00"}},
        NOW,
    )
    assert verdict.alertes == ()
    assert verdict.signalements == ("vigilance",)
    assert not verdict.echoue


def test_manuel_a_venir_et_maintenance_ne_sont_pas_veilles(veille: ModuleType) -> None:
    verdict = veille.evaluer(
        {
            "effis": {"status": "manual", "dataAt": "2026-07-31T00:00:00+00:00"},
            "smoke": {"status": "upcoming", "dataAt": None},
            "arome": {"status": "maintenance", "dataAt": None},
        },
        NOW,
    )
    assert verdict.alertes == ()
    assert verdict.signalements == ()


def test_un_etat_inconnu_n_est_pas_a_jour(veille: ModuleType) -> None:
    verdict = veille.evaluer({"firms": {"status": "operational", "dataAt": None}}, NOW)
    assert verdict.alertes == ("firms",)


def test_l_age_se_lit(veille: ModuleType) -> None:
    assert veille.age_lisible("2026-09-17T11:23:00+00:00", NOW) == "il y a 37 min"
    assert veille.age_lisible("2026-09-17T07:23:00Z", NOW) == "il y a 4 h 37 min"
    assert veille.age_lisible("2026-09-14T11:00:00+00:00", NOW) == "il y a 3 j 1 h"
    assert veille.age_lisible(None, NOW) == "—"


def test_le_compte_rendu_marque_les_alertes(veille: ModuleType) -> None:
    verdict = veille.evaluer(
        {
            "firms": {"status": "stale", "dataAt": "2026-09-16T20:00:00+00:00"},
            "cams": {"status": "delayed", "dataAt": "2026-09-16T00:00:00+00:00"},
        },
        NOW,
    )
    texte = veille.compte_rendu(verdict, "https://exemple.test", NOW, "degraded")
    assert "| `firms` | 🔴 trop ancienne | il y a 16 h 00 min |" in texte
    assert "| `cams` | 🟠 en retard | il y a 36 h 00 min |" in texte
    assert "**Alerte** : `firms`" in texte
