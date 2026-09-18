FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    TZ=Europe/Paris

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY meteo_rouen_meshtastic.py scheduler.py ./

# Par défaut : lance le scheduler qui publie la météo chaque jour à 8h
# (heure de Paris). Pour un test ponctuel, surchargez la commande, par ex.:
#   docker compose run --rm meteo-meshtastic python meteo_rouen_meshtastic.py --dry-run
CMD ["python", "scheduler.py"]
