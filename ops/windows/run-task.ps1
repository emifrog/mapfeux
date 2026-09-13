<#
.SYNOPSIS
  Exécute une tâche MapFeux du registre `ops/tasks.json`, journal à l'appui.

.DESCRIPTION
  Point d'entrée unique des tâches planifiées Windows (stratégie §8.1).
  Chaque script tourne dans l'environnement micromamba `mapfeux-geo`, depuis
  la racine du dépôt, avec sortie et erreurs ajoutées à `logs/<tâche>.log`.

  Python n'est jamais appelé directement : `python.exe` seul plante au
  chargement de ses DLL sur ce poste, `micromamba run` est la voie qui
  marche (constaté en août). Les scripts lisent eux-mêmes
  `services/geo-worker/.env` par un chemin absolu depuis leur propre
  emplacement — le répertoire courant ne leur importe pas, on le pose quand
  même pour les artefacts relatifs.

  Le code de sortie est celui du dernier script en échec ; une tâche à
  plusieurs scripts (CAMS : import puis dérivation) s'arrête au premier
  échec, comme le workflow qu'elle remplace.

.PARAMETER Task
  Le nom d'une entrée de `ops/tasks.json` (Ingestion, Radar, Prefectures, …).
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string] $Task
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here '..\..')).Path
# Le registre est commun aux deux déclencheurs — ce planificateur et les
# minuteries systemd du VPS (ops/vps) : une seule liste de cadences.
$registry = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'ops/tasks.json') | ConvertFrom-Json

$entry = $registry.tasks | Where-Object { $_.name -eq $Task }
if ($null -eq $entry) {
  Write-Error "Tâche inconnue : $Task. Voir ops/tasks.json."
  exit 2
}

# --- Journal ---------------------------------------------------------------
# Un fichier par tâche, en ajout, borné à 2 Mo : au-delà, l'ancien devient
# `.1` et un neuf commence. Deux générations suffisent pour lire ce qui s'est
# passé la nuit dernière ; la trace durable des passes est en base,
# `ingest.import_runs`.
$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("{0}.log" -f $Task.ToLowerInvariant())
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 2MB)) {
  Move-Item -Path $log -Destination ($log + '.1') -Force
}

function Write-Log([string] $line) {
  $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
  Add-Content -Path $log -Value ("[{0}] {1}" -f $stamp, $line) -Encoding UTF8
}

$micromamba = Join-Path $env:USERPROFILE 'micromamba\micromamba.exe'
if (-not (Test-Path $micromamba)) {
  Write-Log "micromamba introuvable : $micromamba"
  exit 3
}

# Python écrit en UTF-8 ; PowerShell 5.1 relit la sortie d'un exécutable
# natif dans la page de code de la console (850 ici), et « mosaïque »
# devenait « mosa├»que » dans le journal — constaté à la première passe.
# Les deux bouts sont alignés : python forcé en UTF-8, la console lue en
# UTF-8.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Exécution --------------------------------------------------------------
Set-Location $root
Write-Log ("=== {0} : début ===" -f $Task)
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$exit = 0

foreach ($script in $entry.scripts) {
  Write-Log ("> {0}" -f $script)
  # `2>&1` sur un exécutable natif : en PowerShell 5.1 chaque ligne d'erreur
  # devient un ErrorRecord, ce qui ferait de `$?` un faux. On passe par cmd
  # pour fusionner les flux avant PowerShell, et on lit le code de sortie
  # de python, pas celui de l'enveloppe.
  $cmd = ('"{0}" run -n mapfeux-geo python "{1}" 2>&1' -f $micromamba, (Join-Path $root $script))
  $output = & cmd.exe /d /c $cmd
  $code = $LASTEXITCODE
  foreach ($line in $output) { Write-Log ("  " + $line) }
  Write-Log ("< {0} : code {1}" -f $script, $code)
  if ($code -ne 0) {
    $exit = $code
    break
  }
}

$sw.Stop()
Write-Log ("=== {0} : fin, code {1}, {2:n0} s ===" -f $Task, $exit, $sw.Elapsed.TotalSeconds)
exit $exit
