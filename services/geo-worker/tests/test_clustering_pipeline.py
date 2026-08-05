"""Tests du plafond de passe du regroupement — cahier §17.2, jalon J2.

Le regroupement traite les détections orphelines par passes bornées, pour que
la tâche périodique garde une transaction de taille prévisible. Le plafond
n'est pas un défaut ; son **silence** en était un. Une version antérieure le
fixait à 5 000 sans moyen de le lever ni de savoir qu'il avait mordu : sur un
corpus de plus de trois cent mille détections, le banc de calibration en aurait
regroupé un et demi pour cent — la tête, l'ordre étant chronologique — et
publié ces chiffres sous le nom du corpus entier.

Ces tests fixent les deux propriétés qui l'empêchent de redevenir silencieux :
le plafond se lève, et une passe qui l'atteint le dit.
"""

from __future__ import annotations

from typing import Any

from geo_worker.pipelines.clustering import (
    ClusteringResult,
    _pending_detections,
    cluster_detections,
    pass_was_capped,
    pending_detection_count,
)


class FauxCurseur:
    """Curseur minimal : retient la requête et ses paramètres, sert des lignes.

    Volontairement ignorant du SQL. Ce qu'on vérifie ici n'est pas le sens de la
    requête — la base s'en charge — mais la valeur transmise pour le plafond.
    """

    def __init__(self, lignes: list[Any]) -> None:
        self.lignes = lignes
        self.requetes: list[tuple[str, Any]] = []

    def __enter__(self) -> FauxCurseur:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.requetes.append((sql, params))

    def fetchall(self) -> list[Any]:
        return self.lignes

    def fetchone(self) -> Any:
        return self.lignes[0] if self.lignes else None


class FausseConnexion:
    def __init__(self, lignes: list[Any] | None = None) -> None:
        self.curseur = FauxCurseur(lignes or [])

    def cursor(self, **_: object) -> FauxCurseur:
        return self.curseur


class TestPlafondDePasse:
    def test_le_plafond_est_transmis_tel_quel(self) -> None:
        conn = FausseConnexion()
        _pending_detections(conn, 250)  # type: ignore[arg-type]
        _, params = conn.curseur.requetes[0]
        assert params == {"limit": 250}

    def test_le_plafond_leve_passe_null_a_la_base(self) -> None:
        # `limit null` vaut « aucune borne » en PostgreSQL. Traduire None par une
        # valeur de repli — un `limit or 5_000`, la faute d'origine — remettrait
        # le plafond en place sans que personne le voie.
        conn = FausseConnexion()
        _pending_detections(conn, None)  # type: ignore[arg-type]
        _, params = conn.curseur.requetes[0]
        assert params == {"limit": None}

    def test_la_requete_ne_se_branche_pas_sur_deux_textes(self) -> None:
        borne = FausseConnexion()
        _pending_detections(borne, 250)  # type: ignore[arg-type]
        sans_borne = FausseConnexion()
        _pending_detections(sans_borne, None)  # type: ignore[arg-type]
        assert borne.curseur.requetes[0][0] == sans_borne.curseur.requetes[0][0]


class TestDrapeauDeTroncature:
    def test_une_passe_qui_remplit_son_plafond_le_signale(self) -> None:
        # Le plafond mord dès que la passe ramène autant de lignes qu'il en
        # autorise : on ne peut pas distinguer « il en restait exactement autant »
        # de « il en reste davantage » sans une requête de plus.
        assert pass_was_capped(5_000, 5_000) is True
        assert pass_was_capped(5_001, 5_000) is True

    def test_une_passe_incomplete_a_vide_la_file(self) -> None:
        assert pass_was_capped(4_999, 5_000) is False
        assert pass_was_capped(0, 5_000) is False

    def test_le_plafond_leve_ne_tronque_jamais(self) -> None:
        # Le cas qui compte pour le banc : sans borne, aucune répétition n'est
        # due, et surtout aucune mesure ne peut porter sur une tranche.
        assert pass_was_capped(0, None) is False
        assert pass_was_capped(337_757, None) is False

    def test_le_drapeau_remonte_dans_le_resultat(self) -> None:
        conn = FausseConnexion([])
        assert cluster_detections(conn, limit=5_000).truncated is False  # type: ignore[arg-type]
        assert cluster_detections(conn, limit=None).truncated is False  # type: ignore[arg-type]

    def test_le_defaut_reste_borne(self) -> None:
        # Le comportement par défaut ne change pas : c'est celui de la tâche
        # périodique, et une transaction non bornée n'y a pas sa place.
        conn = FausseConnexion()
        _pending_detections(conn, 5_000)  # type: ignore[arg-type]
        assert conn.curseur.requetes[0][1] == {"limit": 5_000}


class TestFileRestante:
    def test_compte_les_orphelines(self) -> None:
        conn = FausseConnexion([(42,)])
        assert pending_detection_count(conn) == 42  # type: ignore[arg-type]

    def test_une_base_vide_ne_laisse_rien(self) -> None:
        conn = FausseConnexion([])
        assert pending_detection_count(conn) == 0  # type: ignore[arg-type]


class TestCumulDesPasses:
    def test_les_passes_s_additionnent(self) -> None:
        # `run-ingestion.py` répète les passes bornées et cumule dans un même
        # résultat : le total doit rester juste, y compris les événements
        # touchés, qui commandent la reconstruction des snapshots.
        total = ClusteringResult()
        for created, attached, touched in ((2, 1, "a"), (0, 3, "b"), (1, 0, "a")):
            total.created += created
            total.attached += attached
            total.touched_events.add(touched)
        assert total.created == 3
        assert total.attached == 4
        assert total.processed == 7
        assert total.touched_events == {"a", "b"}
