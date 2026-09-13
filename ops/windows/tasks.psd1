@{
  # Le registre des tâches planifiées — une seule définition, lue par
  # `register-tasks.ps1` (les déclencheurs) et par `run-task.ps1` (les
  # scripts). Deux listes divergeraient à la première retouche.
  #
  # Référence : stratégie §8.1, tranché de nouveau le 13 septembre 2026.
  #
  # Les cadences sont celles que les workflows GitHub Actions déclaraient
  # et ne tenaient pas — mesuré sur sept jours, seul le cron quotidien
  # tournait comme déclaré, tout le sous-quotidien était ramené à une passe
  # toutes les trois à cinq heures. Ici l'heure est **locale** (Europe/Paris)
  # : les tâches quotidiennes sont posées à l'équivalent d'été de leur heure
  # UTC, pour qu'elles ne partent jamais **avant** la publication qu'elles
  # attendent — en hiver elles partent une heure plus tard, ce qui est sans
  # conséquence sur un intervalle de vingt-quatre heures.
  #
  # `TimeLimitMinutes` : au-delà, le planificateur tue le processus. Un
  # processus tué n'exécute aucun `finally` ; le verrou d'exclusion est un
  # verrou de session PostgreSQL et tombe avec la connexion, la file en base
  # reprend la tâche à la passe suivante. Les limites sont larges — le but
  # est d'attraper un blocage, pas de presser une passe lente.
  Tasks = @(
    @{
      Name = 'Ingestion'
      Description = 'FIRMS : import, regroupement, instantanés (run-ingestion.py)'
      Scripts = @('scripts/run-ingestion.py')
      Every = 10
      TimeLimitMinutes = 30
    }
    @{
      Name = 'Radar'
      Description = 'Mosaïque lame d''eau vers la timeline (import-radar.py)'
      Scripts = @('scripts/import-radar.py')
      Every = 5
      TimeLimitMinutes = 10
    }
    @{
      Name = 'Prefectures'
      Description = 'Pages d''actualités préfectorales vers les citations (import-prefectures.py)'
      Scripts = @('scripts/import-prefectures.py')
      Every = 15
      TimeLimitMinutes = 10
    }
    @{
      Name = 'Vigilance'
      Description = 'Dernier bulletin Météo-France (import-vigilance.py)'
      Scripts = @('scripts/import-vigilance.py')
      Every = 60
      Minute = 20
      TimeLimitMinutes = 10
    }
    @{
      Name = 'Massifs'
      Description = 'Niveaux d''accès aux massifs vers le registre (import-massifs.py)'
      Scripts = @('scripts/import-massifs.py')
      Every = 180
      Minute = 20
      TimeLimitMinutes = 15
    }
    @{
      Name = 'Cams'
      Description = 'PM2,5 et PM10 : import puis dérivation COG et tuiles (§19.1)'
      Scripts = @('scripts/import-cams.py', 'scripts/build-cams-rasters.py')
      Daily = '10:45'
      TimeLimitMinutes = 90
    }
    @{
      Name = 'AromeArchive'
      Description = 'Extraction FWI et dépôt en stockage froid (archive-arome.py)'
      Scripts = @('scripts/archive-arome.py')
      Daily = '12:45'
      TimeLimitMinutes = 60
    }
  )
}
