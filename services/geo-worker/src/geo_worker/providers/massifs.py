"""Niveaux d'accès aux massifs — site interservices des préfectures.

Référence : cahier v2.1 §9.2 et §20.4, FR-140 ; ADR-026 ; plan J4.

risque-prevention-incendie.fr publie chaque jour, par département, le
niveau d'accès de chaque massif forestier — la carte quotidienne que les
arrêtés préfectoraux rendent opposable. Trois pièces, toutes constatées
sur le site réel le 28 août :

- `/static/{dept}/import_data/{AAAAMMJJ}.json` — les niveaux du jour :
  `{"massifs": {"831": [niveau, procédure], …}}`. La prévision du
  lendemain paraît vers 18 h ; son absence le matin n'est pas une panne ;
- `/static/{dept}/js/massifs_centre.js` — le référentiel des massifs
  (identifiant, nom), un GeoJSON embarqué dans du JavaScript ;
- `/static/{dept}/translation/fr.json` — les libellés officiels des
  niveaux, **au vocabulaire propre à chaque département** : tableau
  indexé `legend` dans le Var, clés nommées (`green_access`…) dans les
  Alpes-Maritimes. C'est ce verbatim qui se republie, jamais une
  reformulation (ADR-026).

Le segment de chemin n'est pas le code INSEE : le 06 vit sous `/6/`.
"""

from __future__ import annotations

import json
import re
from typing import Any

BASE_URL = "https://www.risque-prevention-incendie.fr"

#: Département → segment de chemin du site (le 06 perd son zéro).
DEPARTMENT_PATHS: dict[str, str] = {"83": "83", "06": "6"}


#: Pages publiques par département — la source affichée et liée.
def department_page_url(department: str) -> str:
    pages = {"83": f"{BASE_URL}/var", "06": f"{BASE_URL}/alpes-maritimes"}
    return pages.get(department, BASE_URL)


def daily_levels_url(department: str, day: str) -> str:
    """L'URL du JSON quotidien ; `day` au format AAAAMMJJ."""
    return f"{BASE_URL}/static/{DEPARTMENT_PATHS[department]}/import_data/{day}.json"


def massif_names_url(department: str) -> str:
    return f"{BASE_URL}/static/{DEPARTMENT_PATHS[department]}/js/massifs_centre.js"


def translation_url(department: str) -> str:
    return f"{BASE_URL}/static/{DEPARTMENT_PATHS[department]}/translation/fr.json"


def parse_daily_levels(payload: str) -> dict[str, tuple[int, int]]:
    """`{identifiant de massif: (niveau, procédure)}` — refuse plutôt que deviner."""
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON quotidien illisible : {exc}") from exc
    massifs = document.get("massifs")
    if not isinstance(massifs, dict) or not massifs:
        raise ValueError("JSON quotidien sans bloc « massifs ».")

    levels: dict[str, tuple[int, int]] = {}
    for massif_id, values in massifs.items():
        if (
            not isinstance(values, list)
            or len(values) < 1
            or not all(isinstance(v, int) for v in values)
        ):
            raise ValueError(f"Massif {massif_id!r} : valeurs inattendues {values!r}.")
        level = values[0]
        if not 0 <= level <= 5:
            raise ValueError(f"Massif {massif_id!r} : niveau hors échelle {level!r}.")
        levels[str(massif_id)] = (level, values[1] if len(values) > 1 else 0)
    return levels


#: Les features du GeoJSON embarqué : `"ID": 838 … "NOM_MASSIF": "ESTEREL"`.
_FEATURE = re.compile(r'"ID"\s*:\s*(\d+)[^}]*?"NOM_MASSIF"\s*:\s*"([^"]+)"')


def parse_massif_names(js_text: str) -> dict[str, str]:
    """Le référentiel identifiant → nom, extrait de `massifs_centre.js`."""
    names = {massif_id: name for massif_id, name in _FEATURE.findall(js_text)}
    if not names:
        raise ValueError("Aucun massif dans massifs_centre.js : page restructurée ?")
    return names


def parse_level_labels(payload: str) -> dict[int, str]:
    """Les libellés officiels par niveau, dans les deux formes constatées.

    Var : tableau `legend` indexé par niveau, dont la queue compose le
    libellé du niveau 5 exceptionnel. Alpes-Maritimes : clés nommées.
    Aucune des deux ? Dictionnaire vide — le niveau s'affichera nu plutôt
    que sous un libellé inventé.
    """
    try:
        translation: dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Traduction illisible : {exc}") from exc

    legend = translation.get("legend")
    if isinstance(legend, list) and len(legend) >= 5:
        labels = {
            level: str(legend[level]).strip() for level in range(0, 5) if str(legend[level]).strip()
        }
        if len(legend) > 5:
            tail = " ".join(str(part).strip() for part in legend[5:] if str(part).strip())
            if tail:
                labels[5] = tail
        return labels

    named = {
        0: translation.get("no_data"),
        1: translation.get("green_access"),
        2: translation.get("yellow_access"),
        3: translation.get("orange_access"),
        4: translation.get("red_access"),
        5: translation.get("red_access"),
    }
    return {level: str(label).strip() for level, label in named.items() if isinstance(label, str)}


__all__ = [
    "BASE_URL",
    "DEPARTMENT_PATHS",
    "daily_levels_url",
    "department_page_url",
    "massif_names_url",
    "parse_daily_levels",
    "parse_level_labels",
    "parse_massif_names",
    "translation_url",
]
