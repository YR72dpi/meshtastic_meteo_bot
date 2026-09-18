#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meteo_rouen_meshtastic.py

Se connecte en TCP à un node Meshtastic et publie sur le canal "meteo"
les prévisions météo du jour pour Rouen : température, hygrométrie,
risque de pluie/orage et niveau d'ensoleillement.

Dépendances :
    pip install meshtastic requests python-dotenv

Configuration :
    Copiez ".env.example" en ".env" et renseignez au minimum MESHTASTIC_HOST
    (l'IP ou le hostname de votre node Meshtastic). Toutes les variables du
    .env peuvent être surchargées ponctuellement via les arguments CLI.

Utilisation :
    python meteo_rouen_meshtastic.py
    python meteo_rouen_meshtastic.py --host 192.168.1.50
    python meteo_rouen_meshtastic.py --channel-index 2
    python meteo_rouen_meshtastic.py --ville "Paris" --lat 48.8566 --lon 2.3522

Le script cherche automatiquement l'index du canal nommé "meteo" configuré
sur le node. Si aucun canal de ce nom n'est trouvé, on peut forcer l'index
avec --channel-index (ou --channel-name pour un autre nom).
"""

import argparse
import os
import sys
from datetime import datetime

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    print("Le paquet 'python-dotenv' est requis : pip install python-dotenv", file=sys.stderr)
    sys.exit(1)

try:
    import meshtastic
    import meshtastic.tcp_interface
except ImportError:
    print("Le paquet 'meshtastic' est requis : pip install meshtastic", file=sys.stderr)
    sys.exit(1)

# Charge les variables du fichier .env (situé à côté de ce script) dans os.environ
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# Coordonnées par défaut : Rouen, France
DEFAULT_LAT = 49.4405
DEFAULT_LON = 1.0943
DEFAULT_VILLE = "Rouen"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Table de correspondance (simplifiée) des codes météo WMO utilisés par Open-Meteo
WMO_CODES = {
    0: "Ciel dégagé",
    1: "Plutôt dégagé",
    2: "Partiellement nuageux",
    3: "Couvert",
    45: "Brouillard",
    48: "Brouillard givrant",
    51: "Bruine légère",
    53: "Bruine modérée",
    55: "Bruine dense",
    56: "Bruine verglaçante légère",
    57: "Bruine verglaçante dense",
    61: "Pluie légère",
    63: "Pluie modérée",
    65: "Pluie forte",
    66: "Pluie verglaçante légère",
    67: "Pluie verglaçante forte",
    71: "Neige légère",
    73: "Neige modérée",
    75: "Neige forte",
    77: "Grains de neige",
    80: "Averses légères",
    81: "Averses modérées",
    82: "Averses violentes",
    85: "Averses de neige légères",
    86: "Averses de neige fortes",
    95: "Orage",
    96: "Orage avec grêle légère",
    99: "Orage avec grêle forte",
}

# Codes considérés comme "orageux"
THUNDERSTORM_CODES = {95, 96, 99}
# Codes impliquant de la pluie/averses/bruine/neige (donc précipitations probables)
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86}


def fetch_weather(lat: float, lon: float) -> dict:
    """Récupère les prévisions du jour depuis Open-Meteo (API gratuite, sans clé)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weathercode",
                "cloudcover_mean",
                "sunshine_duration",
                "relative_humidity_2m_mean",
            ]
        ),
        "timezone": "Europe/Paris",
        "forecast_days": 1,
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    daily = data["daily"]
    return {
        "date": daily["time"][0],
        "temp_min": daily["temperature_2m_min"][0],
        "temp_max": daily["temperature_2m_max"][0],
        "humidite": daily["relative_humidity_2m_mean"][0],
        "proba_precip": daily["precipitation_probability_max"][0],
        "weathercode": daily["weathercode"][0],
        "nuages": daily["cloudcover_mean"][0],
        "ensoleillement_s": daily["sunshine_duration"][0],
    }


def niveau_ensoleillement(nuages: float, duree_ensoleillement_s: float) -> str:
    """Convertit couverture nuageuse (%) et durée d'ensoleillement (s) en un libellé simple."""
    heures = duree_ensoleillement_s / 3600.0
    if nuages < 25 or heures >= 7:
        return f"Fort ({heures:.1f}h)"
    if nuages < 60 or heures >= 3:
        return f"Modéré ({heures:.1f}h)"
    return f"Faible ({heures:.1f}h)"


def libelle_pluie_orage(weathercode: int, proba_precip: float) -> str:
    """Résume le risque de pluie/orage à partir du code météo WMO et de la proba de précipitations."""
    if weathercode in THUNDERSTORM_CODES:
        return f"Orage possible ({proba_precip:.0f}%)"
    if weathercode in RAIN_CODES or proba_precip >= 40:
        return f"Pluie possible ({proba_precip:.0f}%)"
    return f"Pas de pluie prévue ({proba_precip:.0f}%)"


def build_message(ville: str, w: dict) -> str:
    date_str = datetime.strptime(w["date"], "%Y-%m-%d").strftime("%d/%m")
    condition = WMO_CODES.get(w["weathercode"], "Conditions variables")
    pluie = libelle_pluie_orage(w["weathercode"], w["proba_precip"])
    soleil = niveau_ensoleillement(w["nuages"], w["ensoleillement_s"])

    msg = (
        f"Meteo {ville} {date_str}: {condition}. "
        f"T {w['temp_min']:.0f}-{w['temp_max']:.0f}C | "
        f"Hygro {w['humidite']:.0f}% | "
        f"{pluie} | "
        f"Soleil: {soleil}"
    )
    return msg


def find_channel_index(iface: "meshtastic.tcp_interface.TCPInterface", channel_name: str, fallback_index):
    """Cherche l'index du canal nommé `channel_name` sur le node local."""
    node = iface.getNode("^local")
    channel = node.getChannelByName(channel_name)
    if channel is not None:
        return channel.index

    if fallback_index is not None:
        print(
            f"Attention : aucun canal nommé '{channel_name}' trouvé, "
            f"utilisation de l'index fourni --channel-index {fallback_index}.",
            file=sys.stderr,
        )
        return fallback_index

    noms = [c.settings.name for c in (node.channels or []) if c.settings and c.settings.name]
    raise SystemExit(
        f"Impossible de trouver un canal nommé '{channel_name}' sur ce node. "
        f"Canaux disponibles : {noms or 'aucun nom configuré'}. "
        f"Utilisez --channel-index pour forcer l'index manuellement."
    )


def main():
    env_channel_index = os.environ.get("MESHTASTIC_CHANNEL_INDEX")

    parser = argparse.ArgumentParser(
        description="Publie la météo du jour de Rouen sur le canal Meshtastic 'meteo' via TCP."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MESHTASTIC_HOST"),
        help="Adresse IP ou hostname du node Meshtastic (TCP). Peut être défini via MESHTASTIC_HOST dans .env.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MESHTASTIC_PORT", 4403)),
        help="Port TCP de l'API Meshtastic (défaut: 4403, ou MESHTASTIC_PORT dans .env).",
    )
    parser.add_argument(
        "--ville",
        default=os.environ.get("METEO_VILLE", DEFAULT_VILLE),
        help="Nom de la ville affiché dans le message (ou METEO_VILLE dans .env).",
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=float(os.environ.get("METEO_LAT", DEFAULT_LAT)),
        help="Latitude (défaut: Rouen, ou METEO_LAT dans .env).",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=float(os.environ.get("METEO_LON", DEFAULT_LON)),
        help="Longitude (défaut: Rouen, ou METEO_LON dans .env).",
    )
    parser.add_argument(
        "--channel-name",
        default=os.environ.get("MESHTASTIC_CHANNEL_NAME", "meteo"),
        help="Nom du canal Meshtastic cible (défaut: meteo, ou MESHTASTIC_CHANNEL_NAME dans .env).",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=int(env_channel_index) if env_channel_index else None,
        help="Index de canal à utiliser si le nom ne peut pas être résolu automatiquement "
        "(ou MESHTASTIC_CHANNEL_INDEX dans .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le message sans se connecter au node ni l'envoyer.",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.host:
        parser.error(
            "Aucune adresse de node fournie. Renseignez MESHTASTIC_HOST dans le fichier .env "
            "(voir .env.example) ou passez --host <ip>."
        )

    print("Récupération des prévisions météo pour", args.ville, "...")
    weather = fetch_weather(args.lat, args.lon)
    message = build_message(args.ville, weather)

    print("Message généré :")
    print(f"  {message}  ({len(message)} caractères)")

    if args.dry_run:
        print("Mode --dry-run : le message n'a pas été envoyé.")
        return

    print(f"Connexion TCP au node Meshtastic {args.host}:{args.port} ...")
    iface = meshtastic.tcp_interface.TCPInterface(hostname=args.host, portNumber=args.port)
    try:
        channel_index = find_channel_index(iface, args.channel_name, args.channel_index)
        print(f"Envoi sur le canal '{args.channel_name}' (index {channel_index}) ...")
        iface.sendText(message, channelIndex=channel_index)
        print("Message envoyé avec succès.")
    finally:
        iface.close()


if __name__ == "__main__":
    main()
