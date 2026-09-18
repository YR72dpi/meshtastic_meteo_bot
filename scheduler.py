#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scheduler.py

Boucle de planification qui exécute meteo_rouen_meshtastic.py tous les jours
à une heure fixe, exprimée en heure de Paris (gère automatiquement le
passage heure d'été / heure d'hiver grâce à zoneinfo).

Variables d'environnement optionnelles :
    SCHEDULE_HOUR   Heure d'exécution quotidienne (défaut: 8)
    SCHEDULE_MINUTE Minute d'exécution quotidienne (défaut: 0)
    RUN_ON_STARTUP  Si "true", exécute aussi une fois immédiatement au
                    démarrage du conteneur (pratique pour vérifier que tout
                    fonctionne). Défaut: false.
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meteo_rouen_meshtastic.py")

RUN_HOUR = int(os.environ.get("SCHEDULE_HOUR", "8"))
RUN_MINUTE = int(os.environ.get("SCHEDULE_MINUTE", "0"))
RUN_ON_STARTUP = os.environ.get("RUN_ON_STARTUP", "false").strip().lower() in ("1", "true", "yes")


def next_run_time(now: datetime) -> datetime:
    target = now.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def run_job():
    now = datetime.now(PARIS_TZ)
    print(f"[{now.isoformat()}] Exécution de la publication météo...", flush=True)
    result = subprocess.run([sys.executable, SCRIPT_PATH])
    if result.returncode != 0:
        print(
            f"[{now.isoformat()}] Erreur : le script a retourné le code {result.returncode}",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(f"[{now.isoformat()}] Publication terminée avec succès.", flush=True)


def main():
    print(
        f"Scheduler météo Meshtastic démarré. Envoi quotidien à "
        f"{RUN_HOUR:02d}:{RUN_MINUTE:02d} (heure de Paris).",
        flush=True,
    )

    if RUN_ON_STARTUP:
        print("RUN_ON_STARTUP=true : exécution immédiate au démarrage.", flush=True)
        run_job()

    while True:
        now = datetime.now(PARIS_TZ)
        target = next_run_time(now)
        sleep_seconds = (target - now).total_seconds()
        print(
            f"Prochaine exécution prévue : {target.isoformat()} "
            f"(dans {sleep_seconds / 3600:.1f}h)",
            flush=True,
        )
        time.sleep(max(sleep_seconds, 1))
        run_job()
        # Petite pause de sécurité pour éviter un double déclenchement
        # si la boucle recalcule trop vite la même minute cible.
        time.sleep(60)


if __name__ == "__main__":
    main()
