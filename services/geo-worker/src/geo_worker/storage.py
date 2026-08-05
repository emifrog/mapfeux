"""Dépôt d'objets dans Supabase Storage.

Référence : cahier §12.4, §14.2 et §16.1.

Un seul chemin de dépôt pour tout le worker. L'archivage AROME portait sa
propre implémentation ; l'archivage du brut FIRMS en aurait produit une seconde,
avec ses propres en-têtes et sa propre gestion d'erreur. Or c'est exactement le
genre de duplication où une correction s'applique à une copie et pas à l'autre —
le cas de l'en-tête `apikey` ci-dessous en est un exemple vivant.
"""

from __future__ import annotations

import hashlib

import httpx

from geo_worker.logging import get_logger

logger = get_logger(__name__)

#: Compartiments connus, et ce qu'ils promettent.
#:
#: `cold` porte l'exception de rétention PR-1 : jamais purgé. `raw` est soumis à
#: une rétention de trente jours, `derived` contient du régénérable.
BUCKET_RAW = "raw"
BUCKET_DERIVED = "derived"
BUCKET_COLD = "cold"


class StorageError(RuntimeError):
    """Le dépôt a échoué. Porte le motif rendu par Storage, jamais la clé."""


def upload_object(
    client: httpx.Client,
    *,
    supabase_url: str,
    secret_key: str,
    bucket: str,
    object_path: str,
    payload: bytes,
    content_type: str = "application/octet-stream",
    timeout: float = 180.0,
) -> str:
    """Dépose un objet et retourne son empreinte SHA-256.

    L'empreinte est calculée sur ce qui est **réellement envoyé**, et rendue
    pour être consignée dans l'`import_run`. C'est ce qui permet, plus tard, de
    vérifier qu'un fichier retrouvé est bien celui qui a été analysé.

    `x-upsert` évite qu'un rejeu échoue sur un objet déjà présent : rejouer une
    passe doit être anodin, pas une erreur à diagnostiquer.
    """
    response = client.post(
        f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{object_path}",
        content=payload,
        headers={
            # Les clés `sb_secret_…` ne sont pas des JWT : Storage refuse de les
            # analyser comme tel et répond « Invalid Compact JWS ». Elles se
            # présentent en `apikey` ; l'en-tête `Authorization` reste envoyé
            # pour les déploiements servant encore l'ancien format.
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        timeout=timeout,
    )

    if response.status_code >= 300:
        # Le corps porte le motif — « Bucket not found », « Invalid Compact
        # JWS ». L'URL porte le compartiment et le chemin, jamais de secret :
        # la clé voyage en en-tête.
        raise StorageError(f"Dépôt refusé ({response.status_code}) : {response.text[:200]}")

    checksum = hashlib.sha256(payload).hexdigest()
    logger.info("storage.uploaded", bucket=bucket, object_path=object_path, bytes=len(payload))
    return checksum


__all__ = [
    "BUCKET_COLD",
    "BUCKET_DERIVED",
    "BUCKET_RAW",
    "StorageError",
    "upload_object",
]
