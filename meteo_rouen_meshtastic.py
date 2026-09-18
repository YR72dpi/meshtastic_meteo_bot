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
    python meteo_rouen_meshtastic.py --style card

Le script cherche automatiquement l'index du canal nommé "meteo" configuré
sur le node. Si aucun canal de ce nom n'est trouvé, on peut forcer l'index
avec --channel-index (ou --channel-name pour un autre nom).

Avant l'envoi, un ping ICMP est tenté vers le node pour le "réveiller"
(certains nodes coupent leur WiFi en veille). Ce ping n'est jamais bloquant :
si le node filtre l'ICMP, le script continue quand même.
"""

import argparse
import contextlib
import os
import platform
import subprocess
import sys
import threading
import time
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

# Délai (s) laissé après sendText() avant de fermer la connexion, pour laisser
# le temps au message d'être réellement transmis (voir _install_quiet_thread_excepthook).
SEND_SETTLE_SECONDS = float(os.environ.get("SEND_SETTLE_SECONDS", 2))

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
# Sous-ensemble neige (utilisé uniquement pour choisir l'emoji le plus parlant)
SNOW_CODES = {71, 73, 75, 77, 85, 86}


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


def weather_icon(weathercode: int) -> str:
    """Retourne un emoji représentatif du code météo WMO (pour un rendu plus UI/UX)."""
    if weathercode in THUNDERSTORM_CODES:
        return "⛈️"
    if weathercode in SNOW_CODES:
        return "❄️"
    if weathercode in RAIN_CODES:
        return "🌧️"
    if weathercode in (45, 48):
        return "🌫️"
    if weathercode == 3:
        return "☁️"
    if weathercode == 2:
        return "⛅"
    return "☀️"  # 0 (ciel dégagé), 1 (plutôt dégagé) ou code inconnu


def build_message_compact(ville: str, w: dict) -> str:
    """Proposition 1 : une seule ligne, dense mais scannable en un coup d'œil."""
    date_str = datetime.strptime(w["date"], "%Y-%m-%d").strftime("%d/%m")
    icon = weather_icon(w["weathercode"])
    condition = WMO_CODES.get(w["weathercode"], "Conditions variables")
    pluie = libelle_pluie_orage(w["weathercode"], w["proba_precip"])
    soleil = niveau_ensoleillement(w["nuages"], w["ensoleillement_s"])

    return (
        f"{icon} {ville} {date_str} : {condition} | "
        f"🌡️ {w['temp_min']:.0f}-{w['temp_max']:.0f}°C  💧 {w['humidite']:.0f}% | "
        f"🌧️ {pluie} | ☀️ {soleil}"
    )


def build_message_card(ville: str, w: dict) -> str:
    """Proposition 2 : mini "carte" multi-lignes, plus aérée façon dashboard."""
    date_str = datetime.strptime(w["date"], "%Y-%m-%d").strftime("%d/%m")
    icon = weather_icon(w["weathercode"])
    condition = WMO_CODES.get(w["weathercode"], "Conditions variables")
    pluie = libelle_pluie_orage(w["weathercode"], w["proba_precip"])
    soleil = niveau_ensoleillement(w["nuages"], w["ensoleillement_s"])

    return (
        f"{icon} Météo {ville} — {date_str} ({condition})\n"
        f"🌡️ {w['temp_min']:.0f}°C → {w['temp_max']:.0f}°C   💧 {w['humidite']:.0f}%\n"
        f"🌧️ {pluie}\n"
        f"☀️ {soleil}"
    )


# "compact" (défaut) : une ligne dense, économe en octets LoRa.
# "card" : mini tableau de bord multi-lignes, plus lisible sur l'écran du node.
MESSAGE_STYLES = {
    "compact": build_message_compact,
    "card": build_message_card,
}


def build_message(style: str, ville: str, w: dict) -> str:
    builder = MESSAGE_STYLES.get(style, build_message_compact)
    return builder(ville, w)


def ping_node(host: str, timeout_s: int = 2) -> bool:
    """Envoie un ping ICMP au node pour le "réveiller" (sortie de veille WiFi)
    avant d'ouvrir la connexion TCP. Ne bloque jamais le script : si le ping
    échoue (ICMP filtré, pas de droits suffisants, etc.) on continue quand
    même la tentative de connexion TCP."""
    is_windows = platform.system().lower() == "windows"
    cmd = (
        ["ping", "-n", "1", "-w", str(timeout_s * 1000), host]
        if is_windows
        else ["ping", "-c", "1", "-W", str(timeout_s), host]
    )
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s + 3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _install_quiet_thread_excepthook():
    """Si le node coupe la connexion TCP juste après l'envoi (ex: veille
    WiFi), un thread interne de la lib meshtastic peut tenter un heartbeat
    sur un socket déjà fermé et lever un BrokenPipeError dans un thread que
    l'on ne contrôle pas. C'est inoffensif (le message a déjà été envoyé) :
    on remplace le traceback complet par une simple ligne d'info."""
    default_hook = threading.excepthook

    def hook(args):
        if issubclass(args.exc_type, (BrokenPipeError, ConnectionResetError, OSError)):
            print(
                f"(info) Connexion TCP interrompue par le node après l'envoi, ignoré : {args.exc_value}",
                file=sys.stderr,
            )
            return
        default_hook(args)

    threading.excepthook = hook


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
        "--style",
        choices=list(MESSAGE_STYLES.keys()),
        default=os.environ.get("MESSAGE_STYLE", "compact"),
        help="Format du message : 'compact' (une ligne) ou 'card' (mini tableau de bord "
        "multi-lignes). Défaut: compact, ou MESSAGE_STYLE dans .env.",
    )
    parser.add_argument(
        "--no-ping",
        dest="ping",
        action="store_false",
        default=os.environ.get("PING_BEFORE_SEND", "true").strip().lower() not in ("0", "false", "no"),
        help="Désactive le ping ICMP de réveil du node avant la connexion TCP "
        "(ou PING_BEFORE_SEND=false dans .env).",
    )
    parser.add_argument(
        "--ping-timeout",
        type=int,
        default=int(os.environ.get("PING_TIMEOUT_S", 2)),
        help="Délai d'attente du ping en secondes (défaut: 2, ou PING_TIMEOUT_S dans .env).",
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
    message = build_message(args.style, args.ville, weather)

    print("Message généré :")
    print(f"  {message}  ({len(message.encode('utf-8'))} octets)")

    if args.dry_run:
        print("Mode --dry-run : le message n'a pas été envoyé.")
        return

    _install_quiet_thread_excepthook()

    if args.ping:
        print(f"Ping de {args.host} pour réveiller le node ...")
        if ping_node(args.host, timeout_s=args.ping_timeout):
            print("  -> Node accessible (ping OK).")
        else:
            print(
                "  -> Pas de réponse au ping (ICMP peut-être filtré), on continue quand même.",
                file=sys.stderr,
            )
        time.sleep(1)  # laisse le temps au node de sortir de veille avant d'ouvrir le TCP

    print(f"Connexion TCP au node Meshtastic {args.host}:{args.port} ...")
    iface = meshtastic.tcp_interface.TCPInterface(hostname=args.host, portNumber=args.port)
    try:
        channel_index = find_channel_index(iface, args.channel_name, args.channel_index)
        print(f"Envoi sur le canal '{args.channel_name}' (index {channel_index}) ...")
        iface.sendText(message, channelIndex=channel_index)
        print("Message envoyé avec succès.")
        # sendText() ne fait que mettre le message en file d'attente : l'envoi
        # réel est asynchrone. On laisse un court délai avant de fermer pour
        # éviter de couper la connexion en pleine transmission.
        time.sleep(SEND_SETTLE_SECONDS)
    finally:
        with contextlib.suppress(Exception):
            iface.close()


if __name__ == "__main__":
    main()
