<#
.SYNOPSIS
  Retire toutes les tâches planifiées MapFeux.

.DESCRIPTION
  Le geste inverse de `register-tasks.ps1`. Rien d'autre n'est touché : ni
  les journaux, ni la base, ni les workflows GitHub — qui gardent leur
  déclenchement manuel (`workflow_dispatch`) et peuvent reprendre la main
  le temps d'une panne du poste.

  Depuis le passage au VPS (7 octobre 2026), le poste ne garde qu'une tâche,
  les préfectures : le retrait des six autres, une fois la cadence du VPS
  mesurée sur sept jours, est `-Except Prefectures`. Sans filtre, tout part,
  préfectures comprises — ce que ce script faisait avant d'en avoir.

.PARAMETER Only
  Ne retire que les tâches nommées, sans le préfixe `MapFeux-`.

.PARAMETER Except
  Retire toutes les tâches sauf celles nommées, sans le préfixe `MapFeux-`.

.EXAMPLE
  .\unregister-tasks.ps1 -Except Prefectures -WhatIf
  Liste ce qui serait retiré, sans rien retirer.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
  [string[]] $Only,
  [string[]] $Except
)

$tasks = Get-ScheduledTask -TaskPath '\MapFeux\' -ErrorAction SilentlyContinue
if ($null -eq $tasks) {
  Write-Output "Aucune tâche MapFeux à retirer."
  exit 0
}

# Les noms du registre, pas ceux du planificateur : `-Except Prefectures`,
# comme `register-tasks.ps1 -Only Prefectures`.
if ($Only) { $tasks = @($tasks | Where-Object { $Only -contains ($_.TaskName -replace '^MapFeux-', '') }) }
if ($Except) { $tasks = @($tasks | Where-Object { $Except -notcontains ($_.TaskName -replace '^MapFeux-', '') }) }
if ($tasks.Count -eq 0) {
  Write-Output "Aucune tâche MapFeux ne correspond au filtre."
  exit 0
}

foreach ($t in $tasks) {
  if ($PSCmdlet.ShouldProcess($t.TaskName, 'retirer')) {
    Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -Confirm:$false
    Write-Output ("retirée : {0}" -f $t.TaskName)
  }
}
