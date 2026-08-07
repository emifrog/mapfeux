"""Crée ou habilite un compte administrateur.

Usage :
    micromamba run -n mapfeux-geo python scripts/grant-admin.py \
        --email prenom@exemple.fr --nom "Prénom Nom" --role data_admin

Référence : cahier §14.1, §14.2 et §14.4.

La page de connexion n'inscrit personne (`shouldCreateUser: false`) : ce script
est le seul chemin d'entrée d'un administrateur. Il crée l'utilisateur auth
s'il n'existe pas — API d'administration, clé secrète serveur uniquement — puis
pose le profil dans `admin.profiles`, seule source de vérité des rôles. La
personne se connecte ensuite par lien magique sur /admin/connexion.

`super_admin` implique `mfa_required` (contrainte en base), mais l'application
ne sait pas encore exiger le second facteur : l'enrôlement TOTP arrive en J5.
D'ici là, ne pas employer un compte super_admin au quotidien.

La clé secrète n'est jamais affichée, même en cas d'erreur.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, load_env

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"

ROLES = ("viewer_admin", "content_admin", "data_admin", "super_admin")

#: Au-delà, l'annuaire n'est plus une liste d'administrateurs : quelque chose
#: ne va pas, et parcourir des milliers de comptes masquerait le problème.
MAX_USER_PAGES = 20


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def admin_headers(secret_key: str) -> dict[str, str]:
    return {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}


def find_user_id(client: httpx.Client, base: str, headers: dict[str, str], email: str) -> str:
    """Retrouve un utilisateur existant par son adresse, page par page."""
    for page in range(1, MAX_USER_PAGES + 1):
        response = client.get(
            f"{base}/auth/v1/admin/users",
            headers=headers,
            params={"page": page, "per_page": 100},
        )
        response.raise_for_status()
        users = response.json().get("users", [])
        if not users:
            break
        for user in users:
            if str(user.get("email", "")).lower() == email:
                return str(user["id"])
    sys.exit(f"Compte annoncé existant mais introuvable dans l'annuaire : {email}")


def ensure_auth_user(client: httpx.Client, base: str, headers: dict[str, str], email: str) -> str:
    """Crée l'utilisateur auth, ou retrouve son identifiant s'il existe déjà.

    `email_confirm` : l'adresse est réputée vérifiée — le compte est créé par
    l'exploitant pour une personne identifiée, pas par un inconnu.
    """
    response = client.post(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "email_confirm": True},
    )
    if response.status_code in (200, 201):
        payload: dict[str, Any] = response.json()
        print("compte auth : créé")
        return str(payload["id"])
    if response.status_code == 422:
        print("compte auth : déjà existant")
        return find_user_id(client, base, headers, email)

    # Le corps de la réponse d'erreur ne contient pas de secret ; la clé, elle,
    # ne vit que dans les en-têtes, qui ne sont jamais affichés.
    sys.exit(f"Création refusée ({response.status_code}) : {response.text[:200]}")


def upsert_profile(dsn: str, user_id: str, display_name: str, role: str) -> None:
    with psycopg.connect(dsn, connect_timeout=30) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into admin.profiles (user_id, role, status, display_name, mfa_required)
                values (%(user_id)s, %(role)s::admin.role, 'active', %(display_name)s,
                        %(mfa_required)s)
                on conflict (user_id) do update set
                  role = excluded.role,
                  status = 'active',
                  display_name = excluded.display_name,
                  mfa_required = excluded.mfa_required
                """,
                {
                    "user_id": user_id,
                    "role": role,
                    "display_name": display_name,
                    "mfa_required": role == "super_admin",
                },
            )
        conn.commit()


def main(argv: list[str]) -> int:
    email_raw = parse_option(argv, "--email")
    display_name = parse_option(argv, "--nom")
    role = parse_option(argv, "--role") or "viewer_admin"

    if email_raw is None or display_name is None:
        sys.exit("Usage : grant-admin.py --email <adresse> --nom <nom affiché> [--role <rôle>]")
    if role not in ROLES:
        sys.exit(f"Rôle inconnu : {role}. Attendu : {', '.join(ROLES)}")

    email = email_raw.strip().lower()

    env = load_env(ENV_FILE)
    base = env.get("SUPABASE_URL", "").rstrip("/")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    if not base or not secret_key:
        sys.exit(f"SUPABASE_URL ou SUPABASE_SECRET_KEY absente de {ENV_FILE}.")

    dsn = dsn_from_env_file(ENV_FILE)

    print(f"adresse : {email}")
    print(f"rôle    : {role}\n")

    with httpx.Client(timeout=30) as client:
        user_id = ensure_auth_user(client, base, admin_headers(secret_key), email)

    upsert_profile(dsn, user_id, display_name, role)
    print(f"profil      : actif ({role})")

    if role == "super_admin":
        print(
            "\n⚠ super_admin exige la MFA (contrainte en base) ; son enrôlement"
            "\n  n'existe pas encore (J5). Réserver ce compte aux opérations rares."
        )

    print("\nÉtape suivante : se connecter par lien magique sur /admin/connexion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
