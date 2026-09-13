<#
.SYNOPSIS
  Retire toutes les tâches planifiées MapFeux.

.DESCRIPTION
  Le geste inverse de `register-tasks.ps1`. Rien d'autre n'est touché : ni
  les journaux, ni la base, ni les workflows GitHub — qui gardent leur
  déclenchement manuel (`workflow_dispatch`) et peuvent reprendre la main
  le temps d'une panne du poste.
#>
[CmdletBinding()]
param()

$tasks = Get-ScheduledTask -TaskPath '\MapFeux\' -ErrorAction SilentlyContinue
if ($null -eq $tasks) {
  Write-Output "Aucune tâche MapFeux à retirer."
  exit 0
}

foreach ($t in $tasks) {
  Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -Confirm:$false
  Write-Output ("retirée : {0}" -f $t.TaskName)
}
