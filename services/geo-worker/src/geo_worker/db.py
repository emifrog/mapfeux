"""Accès à la base depuis les scripts d'exploitation.

Référence : cahier annexe C.

La lecture de `DATABASE_URL` était recopiée dans chaque script, avec sa
correction d'encodage. Cette duplication a déjà produit un défaut : une version
encodait le mot de passe sans condition, doublant l'encodage d'une chaîne déjà
correcte et provoquant un échec d'authentification impossible à rattacher à sa
cause. Une seule implémentation, testée, ferme le sujet.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import quote

import psycopg


class DsnError(RuntimeError):
    """Chaîne de connexion absente ou inexploitable."""


def advisory_key(name: str) -> int:
    """Clé de verrou stable, dérivée d'un nom.

    `hash()` intégré ne convient pas : Python le randomise à chaque démarrage,
    donc deux processus concurrents — précisément le cas qu'on veut détecter —
    obtiendraient des clés différentes et ne se verraient pas.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


@contextmanager
def exclusive_run(conn: psycopg.Connection[Any], name: str) -> Iterator[bool]:
    """Verrou d'exécution : cède `True` si la place était libre.

    Deux passes d'ingestion simultanées ne sont pas anodines. L'insertion des
    détections est idempotente et le rattachement protégé par une contrainte
    d'unicité, mais rien n'empêche deux processus de créer chacun un événement
    pour la même détection orpheline : le perdant garde un événement sans
    membre, et le recalcul des agrégats échoue dessus. Un ordonnanceur qui
    déclenche toutes les dix minutes une chaîne qui en met parfois quinze
    produirait ce cas régulièrement.

    Le verrou est **de session** et non de transaction : la chaîne valide
    plusieurs fois, et un verrou de transaction serait relâché dès la première
    validation. Il tombe de lui-même si le processus meurt, la connexion étant
    alors fermée par le serveur — pas de verrou orphelin à nettoyer.

    Cela suppose une connexion directe, ou un pooler en mode session. Derrière
    un pooler en mode **transaction**, chaque transaction peut atterrir sur une
    connexion serveur différente : le verrou serait pris sur l'une et le travail
    fait sur une autre, sans que rien ne le signale.
    """
    key = advisory_key(name)
    with conn.cursor() as cur:
        cur.execute("select pg_try_advisory_lock(%s)", (key,))
        row = cur.fetchone()
        acquired = bool(row[0]) if row is not None else False

    try:
        yield acquired
    finally:
        if acquired:
            with conn.cursor() as cur:
                cur.execute("select pg_advisory_unlock(%s)", (key,))


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


def load_env(path: pathlib.Path) -> dict[str, str]:
    """Configuration effective : le fichier, surclassé par l'environnement.

    Sur un poste de développement la configuration vit dans un fichier ; chez un
    ordonnanceur elle vient de variables, et aucun fichier n'existe. Exiger l'un
    ou l'autre obligerait à écrire un `.env` à la volée en CI, c'est-à-dire à
    poser un secret sur le disque d'un runner partagé pour le relire aussitôt.

    L'environnement l'emporte, ce qui est l'ordre habituel : on surcharge une
    valeur le temps d'une commande sans éditer le fichier, et l'absence de
    fichier n'est pas une erreur.
    """
    values: dict[str, str] = {}
    if path.exists():
        values.update(read_env_file(path))
    values.update(os.environ)
    return values


def dsn_from_env_file(path: pathlib.Path) -> str:
    """Chaîne de connexion prête à l'emploi."""
    raw = load_env(path).get("DATABASE_URL", "")
    if raw == "":
        raise DsnError(
            f"DATABASE_URL absente de {path} et de l'environnement.\n"
            "Sur un poste de développement, la renseigner dans le fichier ; "
            "chez un ordonnanceur, la passer en variable."
        )
    return normalise_dsn(raw)


def dsn_target(dsn: str) -> tuple[str, str, str]:
    """Cible d'une chaîne de connexion : (hôte, port, base), sans identifiants.

    Sert à comparer deux chaînes qui désignent la même base sous des comptes
    différents — le cas exact qu'il faut détecter, un rôle de calibration
    pointant par mégarde sur la base de production.
    """
    _, separator, rest = dsn.partition("://")
    if separator == "":
        return ("", "", dsn)

    authority, _, path = rest.partition("/")
    _, _, hostpart = authority.rpartition("@")
    host, _, port = hostpart.partition(":")
    database = path.partition("?")[0]
    return (host.lower(), port or "5432", database)


def calibration_dsn(path: pathlib.Path) -> str:
    """Chaîne de connexion de la base de calibration.

    Le banc efface et réécrit `fire.events` à chaque jeu de paramètres. Sur le
    corpus de quatorze saisons, un balayage complet dure des heures : le faire
    sur la base que le site public lit reviendrait à servir des regroupements
    expérimentaux pendant tout ce temps, sous les mêmes URL et sans que la page
    puisse le dire.

    D'où une variable distincte, et le refus explicite de désigner la même base
    que `DATABASE_URL`. Se tromper de cible ici ne produit pas d'erreur visible
    — le chargement réussit, la calibration tourne — et c'est ce qui rend le
    contrôle nécessaire plutôt que superflu.
    """
    values = load_env(path)

    raw = values.get("CALIBRATION_DATABASE_URL", "")
    if raw == "":
        raise DsnError(
            f"CALIBRATION_DATABASE_URL absente de {path} et de l'environnement.\n"
            "La calibration exige une base distincte de celle que le site lit : "
            "le banc y efface et réécrit les événements pendant des heures."
        )

    dsn = normalise_dsn(raw)

    public = values.get("DATABASE_URL", "")
    if public != "" and dsn_target(dsn) == dsn_target(normalise_dsn(public)):
        host, port, database = dsn_target(dsn)
        raise DsnError(
            f"CALIBRATION_DATABASE_URL désigne la même base que DATABASE_URL "
            f"({host}:{port}/{database}).\n"
            "Le banc effacerait les événements servis au public. "
            "Monter une base distincte, ou corriger la variable."
        )

    return dsn


__all__ = [
    "DsnError",
    "advisory_key",
    "calibration_dsn",
    "dsn_from_env_file",
    "dsn_target",
    "exclusive_run",
    "load_env",
    "normalise_dsn",
    "read_env_file",
]
