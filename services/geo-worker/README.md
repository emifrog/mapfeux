# Worker géospatial MapFeux

Ingestion des sources externes, calculs géospatiaux et production des données
dérivées. Cahier §10.2 et §16.

## Pourquoi micromamba et pas un venv

`pip install` suffit pour rasterio, pyproj, shapely et geopandas : leurs roues
embarquent GDAL. En revanche **ecCodes**, nécessaire à la lecture des GRIB2
AROME, n'a pas de roue PyPI fiable sur Windows. conda-forge fournit des binaires
win-64 pour ecCodes, GDAL et cfgrib.

C'est la raison pour laquelle le cahier prévoyait une image Docker. Sans Docker,
conda-forge est le seul substitut réaliste — voir
[ADR-014](../../docs/adr/014-environnement-sans-docker.md).

## Installation

### 1. micromamba

Le binaire suffit : ni installateur, ni droits administrateur.

```powershell
# Windows
$root = "$env:USERPROFILE\micromamba"
New-Item -ItemType Directory -Force -Path $root | Out-Null
Invoke-WebRequest -UseBasicParsing `
  -Uri 'https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64.exe' `
  -OutFile "$root\micromamba.exe"
$env:MAMBA_ROOT_PREFIX = $root
```

```bash
# macOS / Linux
curl -Ls https://micro.mamba.pm/install.sh | bash
```

Sous Windows, le script d'installation officiel pose des questions interactives.
Télécharger l'exécutable directement évite ce détour et se scripte en CI.

### 2. Environnement

```bash
micromamba create -f environment.yml -y
```

La résolution prend quelques secondes, le téléchargement plusieurs minutes la
première fois : la pile GDAL et ecCodes pèse lourd.

### 3. Configuration

```bash
cp ../../.env.example .env    # ne conserver que la section Worker
```

Un connecteur sans clé est déclaré **indisponible** et non silencieusement
inactif : `/readiness` le signale, et la page publique `/statut` doit le
refléter.

## Utilisation

`micromamba run -n mapfeux-geo <commande>` exécute sans activer le shell, donc
sans `micromamba shell init`. C'est la forme utilisée en CI.

```bash
# Service HTTP interne (supervision, déclenchement manuel)
micromamba run -n mapfeux-geo uvicorn geo_worker.api:create_app --factory --reload --port 8000

# Qualité — bloquants en CI
micromamba run -n mapfeux-geo ruff check .
micromamba run -n mapfeux-geo ruff format --check .
micromamba run -n mapfeux-geo mypy src
micromamba run -n mapfeux-geo pytest
```

Les tests s'exécutent sans installation préalable du paquet : `pythonpath` est
renseigné dans `pyproject.toml`. Pour lancer le service en revanche, installer
le paquet en mode éditable avec `pip install -e .` ou renseigner `PYTHONPATH=src`.

`/health` et `/readiness` ne sont pas des endpoints publics : ce service ne doit
jamais être exposé directement sur Internet.

## Organisation

```text
src/geo_worker/
├── config.py             variables d'environnement validées
├── logging.py            JSON structuré, expurgation des données sensibles
├── api.py                service HTTP interne
├── providers/
│   ├── base.py           interfaces génériques (cahier §30.1)
│   ├── models.py         modèles normalisés
│   └── firms.py          connecteur NASA FIRMS
└── pipelines/
    └── import_run.py     cycle de vie d'un import (cahier §16.1)
```

## Règles

- **Toutes les heures sont en UTC.** La règle ruff `DTZ` interdit les dates
  naïves ; la conversion vers le fuseau du territoire appartient à l'interface.
- **Aucun secret, payload brut ou coordonnée d'utilisateur dans les journaux.**
  Le processeur `redact_sensitive` en est le garde-fou mécanique.
- **Une ligne fournisseur invalide est rejetée et comptée**, elle n'interrompt
  jamais l'import entier.
- **Un traitement automatique n'écrit jamais un statut officiel.** La règle est
  appliquée à la fois par le domaine TypeScript et par les contraintes de
  `fire.events`.
