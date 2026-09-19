# 🌦️ Meshtastic Météo Bot

Publie chaque jour la **prévision météo du jour** sur un canal Meshtastic :
température, hygrométrie, risque de pluie/orage et niveau d'ensoleillement.
Le bot se connecte en **TCP** à votre node, le réveille au besoin, puis
diffuse un message soigné sur le canal `meteo`.

Par défaut configuré pour **Rouen**, mais utilisable pour n'importe quelle ville.

```
🌧️ Météo Rouen — 18/09 (Averses légères)
🌡️ 12°C → 20°C   💧 77%
🌧️ Pluie possible (5%)
☀️ Fort (7.5h)
```

## ✨ Fonctionnalités

- 🌡️ **Prévision complète du jour** (min/max, hygrométrie, probabilité de
  pluie/orage, ensoleillement) via l'API gratuite [Open-Meteo](https://open-meteo.com/)
  (aucune clé requise).
- 📡 Connexion **TCP** à un node Meshtastic, publication sur le canal `meteo`
  (résolution automatique de l'index du canal par son nom).
- 📶 **Ping ICMP de réveil** du node avant la connexion TCP (utile si le node
  est en veille WiFi) ; jamais bloquant, même si l'ICMP est filtré.
- 🎨 Deux formats de message au choix (voir ci-dessous), avec emoji
  représentatif de la météo du jour (⛈️❄️🌧️🌫️☁️⛅☀️).
- 🛡️ Fermeture robuste de la connexion : les node qui coupent le TCP juste
  après réception (veille WiFi) ne génèrent plus de traceback bruyant.
- 🔁 **Résilient aux pannes transitoires** : réessaie automatiquement (backoff
  exponentiel) si l'API météo répond une erreur temporaire (503, timeout...),
  et le scheduler relance la publication du jour plusieurs fois espacées si
  elle échoue malgré tout, plutôt que d'attendre le lendemain.
- ⏰ Envoi **automatique chaque jour à 8h00, heure de Paris** (gère le
  passage heure d'été/hiver), via un conteneur Docker.
- 🔧 Entièrement configurable via un fichier `.env` (IP du node, ville,
  coordonnées, style de message, heure d'envoi...).
- 🧪 Mode `--dry-run` pour prévisualiser le message sans rien envoyer.

## 🎨 Formats de message

**`card`** — mini tableau de bord multi-lignes, aéré et lisible :

```
🌧️ Météo Rouen — 18/09 (Averses légères)
🌡️ 12°C → 20°C   💧 77%
🌧️ Pluie possible (5%)
☀️ Fort (7.5h)
```

**`compact`** (défaut historique) — une seule ligne, dense mais scannable :

```
🌧️ Rouen 18/09 : Averses légères | 🌡️ 12-20°C  💧 77% | 🌧️ Pluie possible (5%) | ☀️ Fort (7.5h)
```

Choix via `--style card` / `--style compact` en ligne de commande, ou
`MESSAGE_STYLE=card` dans `.env`.

## 🚀 Démarrage rapide

### 1. Configuration

```bash
cp .env.example .env
```

Éditez `.env` et renseignez au minimum l'IP de votre node :

```dotenv
MESHTASTIC_HOST=192.168.1.50
```

Voir [.env.example](.env.example) pour toutes les options disponibles
(port, nom du canal, ville/coordonnées, style de message, ping de réveil,
heure d'envoi quotidien...).

### 2. Lancer avec Docker

Un [Makefile](Makefile) fournit des raccourcis pratiques :

```bash
make up      # build + démarre le scheduler (envoi quotidien à 8h)
make logs    # suit les logs en direct
make down    # arrête le conteneur
```

### 3. Tester manuellement

```bash
make test    # prévisualise le message (--dry-run, aucun envoi)
make send    # envoie le message immédiatement sur le canal
```

Après une modification du code ou du `.env` :

```bash
make update  # reconstruit l'image et recrée le conteneur
```

➡️ Voir `make help` pour la liste complète des commandes (`build`, `up`,
`down`, `restart`, `update`, `logs`, `ps`, `test`, `send`, `sh`, `clean`).

## 🐍 Utilisation sans Docker

```bash
pip install -r requirements.txt
python meteo_rouen_meshtastic.py --dry-run
python meteo_rouen_meshtastic.py
```

Les options peuvent aussi être passées en ligne de commande (elles
surchargent le `.env`) :

```bash
python meteo_rouen_meshtastic.py --host 192.168.1.50 --ville "Paris" --lat 48.8566 --lon 2.3522 --style card
python meteo_rouen_meshtastic.py --no-ping          # désactive le ping de réveil
```

## 📁 Structure du projet

| Fichier | Rôle |
|---|---|
| [meteo_rouen_meshtastic.py](meteo_rouen_meshtastic.py) | Script principal : récupère la météo, réveille le node (ping) et publie sur Meshtastic |
| [scheduler.py](scheduler.py) | Boucle de planification quotidienne (8h, heure de Paris) |
| [Dockerfile](Dockerfile) | Image du conteneur (Python + `iputils-ping` pour le ping de réveil) |
| [docker-compose.yml](docker-compose.yml) | Orchestration du conteneur |
| [Makefile](Makefile) | Raccourcis `make build/up/down/test/send/update/...` |
| [requirements.txt](requirements.txt) | Dépendances Python |
| [.env.example](.env.example) | Modèle de configuration à copier en `.env` |

## ⚙️ Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `MESHTASTIC_HOST` | *(obligatoire)* | IP ou hostname du node Meshtastic |
| `MESHTASTIC_PORT` | `4403` | Port TCP de l'API Meshtastic |
| `MESHTASTIC_CHANNEL_NAME` | `meteo` | Nom du canal cible |
| `MESHTASTIC_CHANNEL_INDEX` | — | Force l'index de canal si le nom n'est pas résolu |
| `METEO_VILLE` | `Rouen` | Nom affiché dans le message |
| `METEO_LAT` / `METEO_LON` | 49.4432 / 1.0999 | Coordonnées GPS utilisées pour la prévision |
| `MESSAGE_STYLE` | `compact` | Format du message : `compact` (1 ligne) ou `card` (multi-lignes) |
| `PING_BEFORE_SEND` | `true` | Ping ICMP de réveil du node avant la connexion TCP |
| `PING_TIMEOUT_S` | `2` | Délai d'attente du ping (secondes) |
| `SEND_SETTLE_SECONDS` | `2` | Délai après l'envoi avant de fermer la connexion TCP |
| `WEATHER_RETRY_ATTEMPTS` | `5` | Nombre de tentatives sur erreur transitoire de l'API météo |
| `WEATHER_RETRY_BASE_DELAY_S` | `2` | Délai de base (s) du backoff exponentiel entre tentatives |
| `SCHEDULE_HOUR` / `SCHEDULE_MINUTE` | `8` / `0` | Heure d'envoi quotidien (heure de Paris) |
| `RUN_ON_STARTUP` | `false` | Envoie aussi un message immédiatement au démarrage du conteneur |
| `JOB_RETRY_ATTEMPTS` | `3` | Nombre de tentatives de la publication quotidienne en cas d'échec |
| `JOB_RETRY_DELAY_S` | `600` | Délai (s) entre deux tentatives de publication quotidienne |

## 📝 Licence

Projet personnel, sans licence spécifique — à adapter selon vos besoins.
