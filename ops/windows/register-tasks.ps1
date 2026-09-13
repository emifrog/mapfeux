<#
.SYNOPSIS
  Enregistre — ou ré-enregistre — les tâches planifiées MapFeux.

.DESCRIPTION
  Le déclencheur de l'ingestion (stratégie §8.1, tranché de nouveau le
  13 septembre 2026, transitoire depuis le passage au VPS du 13, même jour). Lit
  `ops/tasks.json` — le registre commun aux deux déclencheurs —, retire les
  tâches MapFeux existantes et les recrée : rejouable à volonté, une
  retouche du registre se pose en relançant ce script.

  Les heures du registre sont en UTC ; elles sont converties en heure locale
  à l'enregistrement. À rejouer aux changements d'heure, sans quoi les
  tâches quotidiennes glissent d'une heure.

  Ce qui a été sondé avant d'écrire, sur ce poste et sans élévation :

  - l'ouverture de session S4U — « exécuter que l'utilisateur soit connecté
    ou non », sans mot de passe stocké — est **refusée** ;
  - l'ouverture interactive est acceptée et s'exécute (résultat 0).

  Les tâches tournent donc sous la session ouverte : la machine doit rester
  allumée et la session connectée — **verrouillée suffit**, déconnectée
  non. C'est la contrepartie de ne pas donner de mot de passe au
  planificateur, et c'est assumé. Une session interactive garde une console
  sur le bureau ; `launch.vbs` la masque.

  Le mot de passe de l'utilisateur n'est demandé nulle part ici, et ne
  doit pas l'être.

.PARAMETER Only
  N'enregistre que les tâches nommées, sans toucher aux autres.
#>
[CmdletBinding()]
param(
  [string[]] $Only
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here '../..')).Path
$registry = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'ops/tasks.json') | ConvertFrom-Json
$launcher = Join-Path $here 'launch.vbs'
$path = '\MapFeux\'

$entries = $registry.tasks
if ($Only) { $entries = $entries | Where-Object { $Only -contains $_.name } }

# Principal : l'utilisateur courant, interactif, sans élévation (voir plus
# haut pour ce qui a été sondé).
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

foreach ($entry in $entries) {
  $name = 'MapFeux-' + $entry.name
  $schedule = $entry.schedule

  # --- Déclencheur -----------------------------------------------------------
  if ($schedule.kind -eq 'daily') {
    # `at_utc` → heure locale du jour ; seule l'heure est retenue.
    $parts = $schedule.at_utc.Split(':')
    $utc = [DateTime]::SpecifyKind((Get-Date).Date.AddHours([int]$parts[0]).AddMinutes([int]$parts[1]), 'Utc')
    $trigger = New-ScheduledTaskTrigger -Daily -At $utc.ToLocalTime().ToString('HH:mm')
  }
  else {
    # Répétition à intervalle fixe, sans fin. Le point de départ est calé sur
    # la prochaine minute demandée (`Minute`, sinon tout de suite) pour
    # retrouver les mêmes instants que le cron remplacé — Vigilance à :20,
    # Massifs à :20 toutes les trois heures.
    $every = [int]$schedule.minutes
    $start = Get-Date
    if ($null -ne $schedule.PSObject.Properties['minute']) {
      $start = $start.Date.AddHours($start.Hour).AddMinutes([int]$schedule.minute)
      if ($start -le (Get-Date)) { $start = $start.AddHours(1) }
      if ($every -ge 60) {
        # Aligner sur un multiple de la période depuis minuit **UTC**, comme
        # `*/3` en cron : le registre est en UTC.
        $period = [int]($every / 60)
        while (($start.ToUniversalTime().Hour % $period) -ne 0) { $start = $start.AddHours(1) }
      }
    }
    else {
      $start = $start.AddMinutes(1)
    }
    $trigger = New-ScheduledTaskTrigger -Once -At $start `
      -RepetitionInterval (New-TimeSpan -Minutes $every)
  }

  # --- Réglages --------------------------------------------------------------
  # IgnoreNew : une passe encore en cours n'est pas doublée — le verrou
  # d'exclusion en base est la seconde ligne, celle-ci évite d'y arriver.
  # StartWhenAvailable : une passe manquée (veille, redémarrage) part dès que
  # possible plutôt que d'attendre la suivante.
  $settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes ([int]$entry.time_limit_min)) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

  $action = New-ScheduledTaskAction -Execute 'wscript.exe' `
    -Argument ('"{0}" {1}' -f $launcher, $entry.name)

  $existing = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
  if ($null -ne $existing) {
    Unregister-ScheduledTask -TaskName $name -TaskPath $path -Confirm:$false
  }

  Register-ScheduledTask -TaskName $name -TaskPath $path `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description $entry.description | Out-Null

  $info = Get-ScheduledTaskInfo -TaskName $name -TaskPath $path
  Write-Output ("{0,-22} prochaine {1:yyyy-MM-dd HH:mm}  {2}" -f $name, $info.NextRunTime, $entry.description)
}
