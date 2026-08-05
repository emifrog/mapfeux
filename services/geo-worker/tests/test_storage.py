"""Dépôt d'objets dans Supabase Storage — cahier §12.4, §14.2 et §16.1.

Ce module a été extrait parce qu'une seconde implémentation allait naître pour
l'archivage du brut FIRMS. La première portait déjà une correction non
évidente — les clés `sb_secret_…` ne sont pas des JWT et se présentent en
`apikey` — que la copie aurait perdue.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest

from geo_worker.storage import BUCKET_COLD, BUCKET_RAW, StorageError, upload_object

SECRET = "sb_secret_valeur_qui_ne_doit_jamais_paraitre"


def client_repondant(status: int, body: str = "") -> tuple[httpx.Client, list[httpx.Request]]:
    """Client dont chaque requête est retenue, sans réseau."""
    recues: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        recues.append(request)
        return httpx.Response(status, text=body)

    return httpx.Client(transport=httpx.MockTransport(transport)), recues


class TestUploadObject:
    def test_depose_a_l_adresse_attendue(self) -> None:
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="firms/2026/08/05/20260805T210000Z_VIIRS_NOAA20_NRT.csv",
            payload=b"latitude,longitude\n43.5,6.2\n",
        )
        assert str(recues[0].url) == (
            "https://projet.supabase.co/storage/v1/object/raw/"
            "firms/2026/08/05/20260805T210000Z_VIIRS_NOAA20_NRT.csv"
        )

    def test_rend_l_empreinte_de_ce_qui_a_ete_envoye(self) -> None:
        # L'empreinte est consignée dans l'`import_run` : elle doit porter sur
        # les octets déposés, non sur une valeur calculée en amont qui pourrait
        # avoir divergé.
        payload = b"latitude,longitude\n43.5,6.2\n"
        client, _ = client_repondant(200)
        checksum = upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="x.csv",
            payload=payload,
        )
        assert checksum == hashlib.sha256(payload).hexdigest()

    def test_la_cle_voyage_en_entete_apikey(self) -> None:
        # Régression : Storage refuse d'analyser une clé `sb_secret_…` comme un
        # JWT et répond « Invalid Compact JWS » si elle n'arrive que par
        # `Authorization`.
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_COLD,
            object_path="x.nc",
            payload=b"",
        )
        assert recues[0].headers["apikey"] == SECRET

    def test_la_cle_n_apparait_jamais_dans_l_url(self) -> None:
        # L'URL atterrit dans les journaux des intermédiaires ; la clé n'a rien
        # à y faire (§22.2).
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="x.csv",
            payload=b"",
        )
        assert SECRET not in str(recues[0].url)

    def test_ecrase_une_version_anterieure(self) -> None:
        # Rejouer une passe doit être anodin. Sans `x-upsert`, un second passage
        # dans la même seconde échouerait sur un objet déjà présent.
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="x.csv",
            payload=b"",
        )
        assert recues[0].headers["x-upsert"] == "true"

    def test_un_refus_porte_le_motif(self) -> None:
        # « Bucket not found » est le message qui a fait perdre une soirée sur
        # AROME : il doit remonter tel quel.
        client, _ = client_repondant(400, '{"error":"Bucket not found"}')
        with pytest.raises(StorageError, match="Bucket not found"):
            upload_object(
                client,
                supabase_url="https://projet.supabase.co",
                secret_key=SECRET,
                bucket="absent",
                object_path="x.csv",
                payload=b"",
            )

    def test_un_refus_ne_divulgue_pas_la_cle(self) -> None:
        client, _ = client_repondant(401, "unauthorized")
        with pytest.raises(StorageError) as info:
            upload_object(
                client,
                supabase_url="https://projet.supabase.co",
                secret_key=SECRET,
                bucket=BUCKET_RAW,
                object_path="x.csv",
                payload=b"",
            )
        assert SECRET not in str(info.value)

    def test_le_type_de_contenu_est_transmis(self) -> None:
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="x.csv",
            payload=b"",
            content_type="text/csv; charset=utf-8",
        )
        assert recues[0].headers["content-type"] == "text/csv; charset=utf-8"

    def test_l_url_du_projet_tolere_une_barre_finale(self) -> None:
        client, recues = client_repondant(200)
        upload_object(
            client,
            supabase_url="https://projet.supabase.co/",
            secret_key=SECRET,
            bucket=BUCKET_RAW,
            object_path="x.csv",
            payload=b"",
        )
        assert "//storage" not in str(recues[0].url).replace("https://", "")

    @pytest.mark.parametrize("status", [300, 404, 500])
    def test_tout_statut_de_trois_cents_ou_plus_est_un_echec(self, status: int) -> None:
        client, _ = client_repondant(status, "refus")
        with pytest.raises(StorageError):
            upload_object(
                client,
                supabase_url="https://projet.supabase.co",
                secret_key=SECRET,
                bucket=BUCKET_RAW,
                object_path="x.csv",
                payload=b"",
            )


class TestNomsDeCompartiments:
    def test_les_trois_compartiments_de_la_migration(self) -> None:
        # Les constantes doivent correspondre aux identifiants créés par
        # `20260805190000_storage_buckets.sql`, faute de quoi le dépôt viserait
        # un compartiment inexistant.
        assert (BUCKET_RAW, BUCKET_COLD) == ("raw", "cold")

    def test_le_defaut_du_module_ne_vise_jamais_le_froid(self) -> None:
        # `cold` n'est jamais purgé : y déverser du brut quotidien par défaut
        # ferait grossir sans fin une archive censée rester choisie.
        signature: dict[str, Any] = upload_object.__kwdefaults__ or {}
        assert "bucket" not in signature
