' Lanceur a console masquee pour les taches planifiees MapFeux.
'
' Sans elevation, une tache planifiee tourne sous le compte connecte et garde
' une console dans la session du bureau : une fenetre qui s'ouvre toutes les
' cinq minutes, et un Ctrl-C possible dans une passe en cours (constate le
' 6 aout 2026). `WshShell.Run` avec le style 0 masque la fenetre ; le troisieme
' argument a True attend la fin du travail et rend son code de sortie, pour
' que le planificateur enregistre le vrai resultat et la vraie duree.
'
' Ce fichier reste en ASCII : wscript lit le VBS en ANSI, un accent y serait
' deforme.
'
' Usage : wscript.exe launch.vbs <NomDeTache>

Option Explicit

Dim shell, fso, here, task, command, rc

If WScript.Arguments.Count < 1 Then
  WScript.Quit 2
End If

task = WScript.Arguments(0)

Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)

command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass" _
  & " -File """ & here & "\run-task.ps1"" -Task " & task

Set shell = CreateObject("WScript.Shell")
rc = shell.Run(command, 0, True)

WScript.Quit rc
