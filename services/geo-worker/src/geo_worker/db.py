"""Accès à la base depuis les scripts d'exploitation.

Référence : cahier annexe C.

La lecture de `DATABASE_URL` était recopiée dans chaque script, avec sa
correction d'encodage. Cette duplication a déjà produit un défaut : une version
encodait le mot de passe sans condition, doublant l'encodage d'une chaîne déjà
correcte et provoquant un échec d'authentification impossible à rattacher à sa
cause. Une seule implémentation, testée, ferme le sujet.
"""

from __future__ import annotations

import pathlib
from urllib.parse import quote


class DsnError(RuntimeError):
    """Chaîne de connexion absente ou inexploitable."""


def normalise_dsn(raw: str) -> str:
    """Répare le seul défaut courant : un `@` non encodé dans le mot de passe.

    Les mots de passe générés par Supabase en contiennent fréquemment. Collé
    tel quel dans une URL, le `@` déplace la séparation utilisateur/hôte et
    produit une erreur de résolution DNS trompeuse, qui fait chercher un
    problème réseau là où il n'y a qu'un problème de format.

    La correction est **délibérément étroite** : elle n'agit que si la partie
    autorité contient plus d'une arobase. Encoder sans condition doublerait
    l'encodage d'une chaîne déjà correcte — `%40` deviendrait `%2540` — et
    l'authentification échouerait sans que la cause soit visible.
    """
    scheme, separator, rest = raw.partition("://")
    if separator == "":
        return raw

    authority, slash, path = rest.partition("/")
    if authority.count("@") <= 1:
        return raw

    # Un nom d'hôte ne contient jamais d'arobase : la dernière sépare.
    userinfo, _, hostpart = authority.rpartition("@")
    user, _, password = userinfo.partition(":")
    return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}{slash}{path}"


def read_env_file(path: pathlib.Path) -> dict[str, str]:
    """Lit un fichier d'environnement simple. Les commentaires sont ignorés."""
    if not path.exists():
        raise DsnError(f"Fichier d'environnement introuvable : {path}")

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def dsn_from_env_file(path: pathlib.Path) -> str:
    """Chaîne de connexion prête à l'emploi, lue depuis un fichier .env."""
    values = read_env_file(path)
    raw = values.get("DATABASE_URL", "")
    if raw == "":
        raise DsnError(f"DATABASE_URL absente de {path}")
    return normalise_dsn(raw)
