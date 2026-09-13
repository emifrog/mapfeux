<#
.SYNOPSIS
  État des tâches planifiées MapFeux : dernière passe, résultat, prochaine.

.DESCRIPTION
  Ce que le planificateur sait — pas ce que la base sait. La trace durable
  d'une passe est `ingest.import_runs` ; ici on lit le déclencheur lui-même,
  pour distinguer « la tâche n'est pas partie » de « la tâche est partie et
  n'a rien trouvé ». Un `LastTaskResult` non nul est un code de sortie
  python ou un code du planificateur (0x41301 : en cours ; 0x41303 : jamais
  exécutée).
#>
[CmdletBinding()]
param()

$tasks = Get-ScheduledTask -TaskPath '\MapFeux\' -ErrorAction SilentlyContinue
if ($null -eq $tasks) {
  Write-Output "Aucune tâche MapFeux enregistrée. Lancer register-tasks.ps1."
  exit 1
}

$rows = foreach ($t in $tasks) {
  $i = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath
  $result = if ($i.LastTaskResult -eq 0) { 'ok' } else { ('0x{0:X}' -f $i.LastTaskResult) }
  [PSCustomObject]@{
    Tache = $t.TaskName
    Etat = $t.State
    Derniere = $i.LastRunTime
    Resultat = $result
    Prochaine = $i.NextRunTime
  }
}

$rows | Sort-Object Tache | Format-Table -AutoSize
