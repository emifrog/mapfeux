"""Règles de fusion du corpus d'archives NASA FIRMS.

Référence : cahier §16.7 et §24.8 ; stratégie §3.4.

Le corpus de calibration est constitué à la main, depuis les téléchargements
d'Archive Download FIRMS. Chaque téléchargement livre, par produit, un fichier
`fire_archive_*.csv` — le corpus retraité scientifiquement — et un fichier
`fire_nrt_*.csv` — la queue temps réel, non retraitée, qui couvre la période
que le retraitement n'a pas encore atteinte.

Les règles sont ici plutôt que dans l'outil qui les applique, pour qu'elles
soient éprouvables sans fichier ni base. R4 en particulier n'écarte aujourd'hui
aucune ligne — la passation entre les deux corpus est nette sur ce
téléchargement — et une règle qui ne s'exécute jamais n'est pas une règle
vérifiée : elle s'exécutera pour la première fois le jour d'un second
téléchargement, sur des données qu'on ne pourra plus comparer.

Règles :

- **R1** — chaque ligne porte son fichier d'origine et son corpus.
- **R2** — `instrument` est normalisé à ``VIIRS`` ; les fichiers S-NPP portent
  ``SNPP``, ce qui désignerait à tort un instrument distinct.
- **R3** — `detected_at` est reconstruit en UTC depuis `acq_date` et `acq_time`,
  que FIRMS écrit sans zéro initial : ``58`` vaut 00 h 58 et non 58 h 00.
- **R4** — le retraitement fait foi. Pour un satellite donné, une ligne NRT dont
  l'horodatage tombe dans la couverture standard est écartée.
- **R5** — doublons exacts sur (satellite, horodatage, position) supprimés, le
  standard l'emportant.
- **R6** — `type` (0 végétation, 1 volcan, 2 source statique, 3 offshore)
  n'existe **que** dans le corpus standard. Conservé en nullable, avec un
  drapeau dérivé `is_vegetation` à trois états.
- **R7** — aucune ligne n'est filtrée sur le type ni sur la qualité. Le corpus
  est complet ; les filtres appartiennent aux usages en aval, où ils sont
  visibles et discutables.
"""

from __future__ import annotations

import hashlib
from typing import Any, cast

import pandas as pd

#: Rang de priorité entre corpus : le plus petit l'emporte.
#:
#: Une version antérieure triait sur le libellé lui-même, en tirant parti du
#: fait que « standard » suit « nrt » dans l'ordre alphabétique. La priorité
#: reposait donc sur une coïncidence de vocabulaire : un troisième libellé — ou
#: un renommage — l'aurait inversée en silence, et le corpus aurait retenu la
#: donnée non retraitée sans que rien ne le signale.
CORPUS_PRIORITY: dict[str, int] = {"standard": 0, "nrt": 1}

#: Clé naturelle d'une détection. Deux lignes qui s'accordent sur ces quatre
#: colonnes décrivent la même observation.
NATURAL_KEY: tuple[str, ...] = ("satellite", "detected_at", "latitude", "longitude")

#: Colonnes numériques du format FIRMS.
NUMERIC_COLUMNS: tuple[str, ...] = (
    "latitude",
    "longitude",
    "brightness",
    "bright_t31",
    "frp",
    "scan",
    "track",
)

#: Correspondance du champ `type` de FIRMS vers le drapeau végétation.
#: 0 végétation, 1 volcan, 2 source statique, 3 offshore.
VEGETATION_BY_TYPE: dict[int, bool] = {0: True, 1: False, 2: False, 3: False}

STATIC_SOURCE_TYPE = 2


class CorpusError(ValueError):
    """Le corpus lu n'a pas la forme attendue."""


def corpus_of(filename: str) -> str:
    """Corpus d'appartenance d'un fichier FIRMS, d'après son nom (R1).

    FIRMS nomme ``fire_archive_<produit>_<commande>.csv`` le corpus retraité et
    ``fire_nrt_<produit>_<commande>.csv`` la queue temps réel.
    """
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if base.startswith("fire_archive"):
        return "standard"
    if base.startswith("fire_nrt"):
        return "nrt"
    raise CorpusError(
        f"{base} : nom de fichier FIRMS inattendu. Attendu fire_archive_… ou fire_nrt_…"
    )


def normalise(frame: pd.DataFrame) -> pd.DataFrame:
    """Applique R2, R3 et R6 à un corpus déjà étiqueté par R1."""
    missing = {"acq_date", "acq_time", "satellite"} - set(frame.columns)
    if missing:
        raise CorpusError(f"Colonnes FIRMS absentes : {', '.join(sorted(missing))}")
    if "corpus" not in frame.columns:
        raise CorpusError("Le corpus doit être étiqueté (R1) avant normalisation.")

    d = frame.copy()

    # R2 — un seul instrument. Le nom du satellite reste porté par `satellite`.
    d["instrument"] = "VIIRS"

    for column in NUMERIC_COLUMNS:
        if column in d.columns:
            d[column] = pd.to_numeric(d[column], errors="coerce")

    # R3 — FIRMS écrit l'heure sans zéro initial.
    hhmm = d["acq_time"].astype("string").str.zfill(4)
    d["detected_at"] = pd.to_datetime(
        d["acq_date"].astype("string") + " " + hhmm.str[:2] + ":" + hhmm.str[2:],
        utc=True,
        format="%Y-%m-%d %H:%M",
    )

    # R6 — le type est absent du corpus NRT, et le restera : la colonne n'existe
    # pas dans `fire_nrt_*.csv`. Un drapeau à deux états ferait passer
    # « non renseigné » pour « pas de la végétation », c'est-à-dire une
    # affirmation là où il n'y a pas d'observation.
    if "type" not in d.columns:
        d["type"] = pd.NA
    d["type"] = d["type"].astype("Int8")
    d["is_vegetation"] = d["type"].map(VEGETATION_BY_TYPE).astype("boolean")

    d["corpus_rank"] = d["corpus"].map(CORPUS_PRIORITY)
    if d["corpus_rank"].isna().any():
        inconnus = sorted(set(d.loc[d["corpus_rank"].isna(), "corpus"].unique()))
        raise CorpusError(
            f"Corpus sans rang de priorité : {', '.join(inconnus)}. "
            f"Renseigner CORPUS_PRIORITY avant de fusionner."
        )
    d["corpus_rank"] = d["corpus_rank"].astype("Int8")

    return d


def standard_coverage(frame: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """Dernière observation retraitée, par satellite.

    C'est la borne qu'emploie R4. Elle suppose le corpus standard **dense**
    jusqu'à cette borne : un satellite indisponible plusieurs jours au milieu de
    sa période retraitée verrait ses lignes NRT de la panne écartées comme si
    elles faisaient double emploi. FIRMS ne publie pas de calendrier de
    couverture qui permettrait de faire mieux ; la borne est donc rapportée dans
    le compte rendu, pour être vérifiable plutôt que supposée.
    """
    standard = frame[frame["corpus"] == "standard"]
    if standard.empty:
        return {}
    bornes = standard.groupby("satellite")["detected_at"].max()
    return {str(satellite): borne for satellite, borne in bornes.items()}


def drop_superseded_nrt(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """R4 — le retraitement scientifique fait foi sur sa période de couverture.

    La comparaison porte sur l'horodatage, pas sur la journée. Une queue NRT qui
    reprend le jour même où le standard s'arrête apporte des observations que le
    retraitement ne couvre pas encore : les écarter par journée entière perdrait
    de vraies détections, sans rien dédoublonner.

    Un satellite sans corpus standard — c'est le cas de N21, dont FIRMS ne
    publie pas encore l'archive — n'a rien qui puisse primer : toutes ses lignes
    sont conservées.
    """
    bornes = standard_coverage(frame)

    if not bornes:
        # Aucun corpus retraité : rien ne peut primer, et la comparaison n'a pas
        # lieu d'être. Sans cette sortie, `map` sur un dictionnaire vide rend une
        # colonne de flottants, que pandas refuse de comparer à des horodatages —
        # la règle levait une exception au lieu de ne rien faire. Le cas ne peut
        # pas se produire sur le corpus actuel, qui contient du standard ; il se
        # produira le jour d'un téléchargement de produits NRT seuls.
        superseded = pd.Series(False, index=frame.index)
    else:
        limite = frame["satellite"].map(bornes)
        superseded = (frame["corpus"] == "nrt") & limite.notna() & (frame["detected_at"] <= limite)

    stats: dict[str, Any] = {
        "nrt_ecartees_recouvrement_standard": int(superseded.sum()),
        "bornes_standard": {
            satellite: borne.isoformat() for satellite, borne in sorted(bornes.items())
        },
        "satellites_sans_standard": sorted(
            {
                str(s)
                for s in frame.loc[frame["corpus"] == "nrt", "satellite"].unique()
                if str(s) not in bornes
            }
        ),
    }
    return frame[~superseded], stats


def drop_exact_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """R5 — une observation, une ligne ; le corpus le plus fiable l'emporte.

    Le départage est explicite jusqu'au bout : rang de corpus, puis nom du
    fichier d'origine. Sans ce dernier critère, deux téléchargements couvrant la
    même période laisseraient le hasard de l'ordre de lecture désigner le
    gagnant, et le corpus changerait sans qu'aucune donnée n'ait changé.
    """
    ordered = frame.sort_values([*NATURAL_KEY, "corpus_rank", "fichier_source"], kind="stable")
    before = len(ordered)
    deduped = ordered.drop_duplicates(subset=list(NATURAL_KEY), keep="first")
    return deduped, {"doublons_exacts_supprimes": before - len(deduped)}


def canonical_order(frame: pd.DataFrame) -> pd.DataFrame:
    """Ordre total et reproductible, indépendant de l'ordre de lecture.

    Après R5 la clé naturelle est unique : trier dessus donne un ordre total, et
    donc un corpus dont les lignes ne se déplacent que si les données changent.

    Une version antérieure triait sur (horodatage, satellite) seulement. Ces
    deux colonnes ne départagent pas deux pixels acquis à la même minute par le
    même satellite — la situation courante, un passage produisant des milliers
    de pixels par minute. L'ordre de ces lignes suivait alors l'ordre de lecture
    des fichiers, et l'ajout d'un téléchargement les rebattait toutes : un
    fichier entièrement différent pour un corpus inchangé.
    """
    return frame.sort_values(list(NATURAL_KEY), kind="stable").reset_index(drop=True)


def content_fingerprint(frame: pd.DataFrame) -> str:
    """Empreinte du **contenu** du corpus, indépendante du conteneur Parquet.

    Deux écritures Parquet du même tableau ne donnent pas les mêmes octets — la
    mesure le confirme sur ce corpus, à version d'écrivain identique. Hacher le
    fichier ne dirait donc rien : l'empreinte porte sur les valeurs, comme celle
    du partitionnement porte sur l'affectation et non sur les identifiants.

    Le rendu CSV sert de forme canonique. Il est lent et c'est assumé : la
    portabilité entre versions de pandas vaut mieux ici que la vitesse, sur une
    opération qui n'a lieu qu'à la constitution du corpus.
    """
    canonical = canonical_order(frame)
    columns = sorted(c for c in canonical.columns if c != "corpus_rank")
    payload = canonical[columns].to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


def summarise(frame: pd.DataFrame) -> dict[str, Any]:
    """Compte rendu du corpus, destiné au dossier de recette."""
    types = frame["type"].value_counts(dropna=False)
    total = len(frame)
    statiques = int(types.get(STATIC_SOURCE_TYPE, 0))

    par_satellite: dict[str, int] = {}
    for cle, n in frame.groupby(["satellite", "corpus"]).size().items():
        satellite, corpus = cast(tuple[Any, Any], cle)
        par_satellite[f"{satellite}/{corpus}"] = int(n)

    # `absent` plutôt qu'un type numérique de repli : les lignes NRT n'ont pas
    # de type, et leur en prêter un les ferait compter comme observées.
    par_type: dict[str, int] = {}
    for brut, n in types.items():
        valeur = cast(Any, brut)
        par_type["absent" if pd.isna(valeur) else str(int(valeur))] = int(n)

    return {
        "lignes": total,
        "periode_debut": frame["detected_at"].min().isoformat(),
        "periode_fin": frame["detected_at"].max().isoformat(),
        "par_satellite_corpus": par_satellite,
        "par_type": par_type,
        "sources_statiques": statiques,
        "sources_statiques_pct": 0.0 if total == 0 else round(100 * statiques / total, 1),
        "sans_type": int(frame["type"].isna().sum()),
    }


def merge(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fusionne des CSV FIRMS déjà lus, indexés par nom de fichier.

    Les fichiers sont traités dans l'ordre de leur nom, pour que la lecture
    n'introduise pas d'ordre arbitraire avant même le tri.
    """
    if not frames:
        raise CorpusError("Aucun fichier FIRMS à fusionner.")

    labelled: list[pd.DataFrame] = []
    for name in sorted(frames):
        part = frames[name].copy()
        part["fichier_source"] = name
        part["corpus"] = corpus_of(name)
        labelled.append(part)

    d = normalise(pd.concat(labelled, ignore_index=True))
    d, r4 = drop_superseded_nrt(d)
    d, r5 = drop_exact_duplicates(d)
    d = canonical_order(d)

    stats: dict[str, Any] = {**r4, **r5}
    stats["empreinte_contenu"] = content_fingerprint(d)
    stats.update(summarise(d))
    return d.drop(columns=["corpus_rank"]), stats


__all__ = [
    "CORPUS_PRIORITY",
    "NATURAL_KEY",
    "CorpusError",
    "canonical_order",
    "content_fingerprint",
    "corpus_of",
    "drop_exact_duplicates",
    "drop_superseded_nrt",
    "merge",
    "normalise",
    "standard_coverage",
    "summarise",
]
