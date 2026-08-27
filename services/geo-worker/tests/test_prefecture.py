"""Tests de la capture préfectorale — ADR-026, cahier §20.4.

Le fragment nominal est **copié de la page réelle du Var** (26 août 2026) :
cartes DSFR, rubriques sans date, publication datée avec son image. Les cas
de rejet sont synthétiques — chacun vérifie qu'une anomalie est comptée,
jamais silencieuse : republier du bruit sous le nom d'une préfecture serait
pire qu'un retard.
"""

from __future__ import annotations

from datetime import date

from geo_worker.providers.prefecture import parse_actualites

BASE_URL = "https://www.var.gouv.fr/Actualites"

#: Fragments réels de la page du 26 août : une carte de rubrique (sans
#: date, elle est de la navigation) et deux publications datées.
REAL_PAGE = """
<html><body>
<div class="fr-col-12 fr-col-md-4 fr-col-lg-3">
  <div id=474a788d3b4a2c2ca654314399b351fc class="fr-card fr-card--grey fr-enlarge-link">
    <div class="fr-card__body">
      <div class="fr-card__content">
        <h2 class="fr-card__title">
          <a href="/Actualites/Reseaux-sociaux">
            Réseaux sociaux
          </a>
        </h2>
      </div>
    </div>
  </div>
</div>
<div class="fr-col-12">
  <div class="fr-card fr-card--horizontal fr-card--sm fr-enlarge-link fr-mb-3w" id=32feaf5aa7726c41da2f9459024f7a26>
    <div class="fr-card__body">
      <div class="fr-card__content">
        <h2 class="fr-card__title">
          <a class="fr-card__link" href="/Actualites/Deminage-Sainte-Maxime">
            Déminage Sainte-Maxime
          </a>
        </h2>
        <div class="fr-card__end">
          <p class="fr-card__detail">Publié le 20/08/2026</p>
        </div>
      </div>
    </div>
    <div class="fr-card__header">
      <div class="fr-card__img">
        <img class="fr-responsive-img" src="/var/ide_site/storage/images/actualites/deminage-sainte-maxime/312165-1-fre-FR/Deminage-Sainte-Maxime_listitem.jpg" alt="" />
      </div>
    </div>
  </div>
</div>
<div class="fr-col-12">
  <div class="fr-card fr-card--horizontal fr-card--sm fr-enlarge-link fr-mb-3w" id=19063aecef28a98ce4a551666418fdb2>
    <div class="fr-card__body">
      <div class="fr-card__content">
        <h2 class="fr-card__title">
          <a class="fr-card__link" href="/Actualites/Mesures-d-interdictions">
            Mesures d'interdictions
          </a>
        </h2>
        <div class="fr-card__end">
          <p class="fr-card__detail">Publié le 05/08/2026</p>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>
"""


class TestParseActualites:
    def test_les_publications_datees_seules(self) -> None:
        items, rejections = parse_actualites(REAL_PAGE, base_url=BASE_URL)
        assert rejections == []
        assert [item.title for item in items] == [
            "Déminage Sainte-Maxime",
            "Mesures d'interdictions",
        ]
        assert items[0].url == "https://www.var.gouv.fr/Actualites/Deminage-Sainte-Maxime"
        assert items[0].published_on == date(2026, 8, 20)
        assert items[1].published_on == date(2026, 8, 5)

    def test_le_titre_est_verbatim_blancs_replies(self) -> None:
        items, _ = parse_actualites(REAL_PAGE, base_url=BASE_URL)
        # Le HTML entoure le titre de retours à la ligne : seuls les blancs
        # de mise en page se replient, pas un mot ne change.
        assert items[0].title == "Déminage Sainte-Maxime"

    def test_doublon_d_url_capte_une_fois(self) -> None:
        items, rejections = parse_actualites(REAL_PAGE + REAL_PAGE, base_url=BASE_URL)
        assert len(items) == 2
        assert rejections == []

    def test_lien_hors_domaine_rejete_et_compte(self) -> None:
        page = """
        <div class="fr-card"><div class="fr-card__content">
          <h2 class="fr-card__title"><a href="https://autre-site.fr/page">Ailleurs</a></h2>
          <p class="fr-card__detail">Publié le 01/08/2026</p>
        </div></div>
        """
        items, rejections = parse_actualites(page, base_url=BASE_URL)
        assert items == []
        assert any("hors du domaine" in reason for reason in rejections)

    def test_date_invalide_rejetee(self) -> None:
        page = """
        <div class="fr-card"><div class="fr-card__content">
          <h2 class="fr-card__title"><a href="/Actualites/X">X</a></h2>
          <p class="fr-card__detail">Publié le 31/02/2026</p>
        </div></div>
        """
        items, rejections = parse_actualites(page, base_url=BASE_URL)
        assert items == []
        assert any("date invalide" in reason for reason in rejections)

    def test_carte_datee_sans_lien_rejetee(self) -> None:
        page = """
        <div class="fr-card"><div class="fr-card__content">
          <h2 class="fr-card__title">Sans lien</h2>
          <p class="fr-card__detail">Publié le 01/08/2026</p>
        </div></div>
        """
        items, rejections = parse_actualites(page, base_url=BASE_URL)
        assert items == []
        assert any("sans lien" in reason for reason in rejections)

    def test_detail_sans_date_rejete(self) -> None:
        page = """
        <div class="fr-card"><div class="fr-card__content">
          <h2 class="fr-card__title"><a href="/Actualites/X">X</a></h2>
          <p class="fr-card__detail">Mis à jour récemment</p>
        </div></div>
        """
        items, rejections = parse_actualites(page, base_url=BASE_URL)
        assert items == []
        assert any("illisible" in reason for reason in rejections)

    def test_page_vide_rend_vide(self) -> None:
        items, rejections = parse_actualites("<html><body></body></html>", base_url=BASE_URL)
        assert items == []
        assert rejections == []
