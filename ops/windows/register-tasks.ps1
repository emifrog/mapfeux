<#
.SYNOPSIS
  Enregistre — ou ré-enregistre — les tâches planifiées MapFeux.

.DESCRIPTION
  Le déclencheur de l'ingestion (stratégie §8.1, tranché de nouveau le
  13 septembre 2026). Lit `tasks.psd1`, retire les tâches MapFeux existantes
  et les recrée : rejouable à volonté, une retouche du registre se pose en
  relançant ce script.

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
$registry = Import-PowerShellDataFile (Join-Path $here 'tasks.psd1')
$launcher = Join-Path $here 'launch.vbs'
$path = '\MapFeux\'

$entries = $registry.Tasks
if ($Only) { $entries = $entries | Where-Object { $Only -contains $_.Name } }

# Principal : l'utilisateur courant, interactif, sans élévation (voir plus
# haut pour ce qui a été sondé).
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

foreach ($entry in $entries) {
  $name = 'MapFeux-' + $entry.Name

  # --- Déclencheur -----------------------------------------------------------
  if ($entry.ContainsKey('Daily')) {
    $trigger = New-ScheduledTaskTrigger -Daily -At $entry.Daily
  }
  else {
    # Répétition à intervalle fixe, sans fin. Le point de départ est calé sur
    # la prochaine minute demandée (`Minute`, sinon tout de suite) pour
    # retrouver les mêmes instants que le cron remplacé — Vigilance à :20,
    # Massifs à :20 toutes les trois heures.
    $start = Get-Date
    if ($entry.ContainsKey('Minute')) {
      $start = $start.Date.AddHours($start.Hour).AddMinutes($entry.Minute)
      if ($start -le (Get-Date)) { $start = $start.AddHours(1) }
      if ($entry.Every -ge 60) {
        # Aligner l'heure sur un multiple de la période depuis minuit, comme
        # `*/3` en cron.
        $period = [int]($entry.Every / 60)
        while (($start.Hour % $period) -ne 0) { $start = $start.AddHours(1) }
      }
    }
    else {
      $start = $start.AddMinutes(1)
    }
    $trigger = New-ScheduledTaskTrigger -Once -At $start `
      -RepetitionInterval (New-TimeSpan -Minutes $entry.Every)
  }

  # --- Réglages --------------------------------------------------------------
  # IgnoreNew : une passe encore en cours n'est pas doublée — le verrou
  # d'exclusion en base est la seconde ligne, celle-ci évite d'y arriver.
  # StartWhenAvailable : une passe manquée (veille, redémarrage) part dès que
  # possible plutôt que d'attendre la suivante.
  $settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $entry.TimeLimitMinutes) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

  $action = New-ScheduledTaskAction -Execute 'wscript.exe' `
    -Argument ('"{0}" {1}' -f $launcher, $entry.Name)

  $existing = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction SilentlyContinue
  if ($null -ne $existing) {
    Unregister-ScheduledTask -TaskName $name -TaskPath $path -Confirm:$false
  }

  Register-ScheduledTask -TaskName $name -TaskPath $path `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description $entry.Description | Out-Null

  $info = Get-ScheduledTaskInfo -TaskName $name -TaskPath $path
  Write-Output ("{0,-22} prochaine {1:yyyy-MM-dd HH:mm}  {2}" -f $name, $info.NextRunTime, $entry.Description)
}
