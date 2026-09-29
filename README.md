# 🌦️ Meshtastic Weather Bot

Publishes the **daily weather forecast** to a Meshtastic channel:
temperature, humidity, rain/thunderstorm probability, and sunshine duration.
The bot connects to your node via **TCP**, wakes it up if needed, then
publishes a formatted message to the `meteo` channel.

By default, it is configured for **Rouen**, but it can be used with any city.

```text
🌧️ Rouen Weather — 18/09 (Light showers)
🌡️ 12°C → 20°C   💧 77%
🌧️ Rain possible (5%)
☀️ Strong (7.5h)
```

## ✨ Features

* 🌡️ **Full daily forecast** (min/max temperature, humidity, rain/thunderstorm probability, sunshine duration) via the free [Open-Meteo](https://open-meteo.com/) API (no API key required).
* 📡 **TCP connection** to a Meshtastic node, publishing to the `meteo` channel (automatically resolves the channel index by name).
* 📶 **ICMP wake-up ping** before connecting via TCP (useful when the node's Wi-Fi is sleeping); never blocks the bot, even when ICMP is filtered.
* 🎨 **Multi-line dashboard-style message**, with a weather emoji representing the day's conditions (⛈️❄️🌧️🌫️☁️⛅☀️).
* 🛡️ **Robust connection shutdown**: nodes that close the TCP connection immediately after receiving the message (e.g. Wi-Fi sleep) no longer produce noisy tracebacks.
* 🔁 **Resilient to temporary failures**: automatically retries with exponential backoff when the weather API returns a temporary error (503, timeout, etc.). If publication still fails, the scheduler retries the daily job several times at spaced intervals instead of waiting until the next day.
* ⏰ **Automatic daily delivery at 8:00 AM Paris time**, including automatic daylight saving time handling, using a Docker container.
* 🔧 **Fully configurable** through a `.env` file (node IP, city, coordinates, delivery time, etc.).
* 🧪 `--dry-run` mode to preview the message without sending anything.

## 🎨 Message Format

The bot publishes a small multi-line "card" in a dashboard-like format, designed to be clean and easy to read:

```text
🌧️ Rouen Weather — 18/09 (Light showers)
🌡️ 12°C → 20°C   💧 77%
🌧️ Rain possible (5%)
☀️ Strong (7.5h)
```

## 🚀 Quick Start

### 1. Configuration

```bash
cp .env.example .env
```

Edit `.env` and provide at least your node's IP address:

```dotenv
MESHTASTIC_HOST=192.168.1.50
```

See [.env.example](.env.example) for all available options
(port, channel name, city/coordinates, wake-up ping, daily delivery time,
etc.).

### 2. Run with Docker

A [Makefile](Makefile) provides convenient shortcuts:

```bash
make up      # build + start the scheduler (daily delivery at 8 AM)
make logs    # follow logs in real time
make down    # stop the container
```

### 3. Test Manually

```bash
make test    # preview the message (--dry-run, nothing is sent)
make send    # immediately send the message to the channel
```

After modifying the code or `.env`:

```bash
make update  # rebuild the image and recreate the container
```

➡️ Run `make help` to see the complete list of commands
(`build`, `up`, `down`, `restart`, `update`, `logs`, `ps`, `test`, `send`, `sh`, `clean`).

## 🐍 Running Without Docker

```bash
pip install -r requirements.txt
python meteo_rouen_meshtastic.py --dry-run
python meteo_rouen_meshtastic.py
```

Options can also be passed directly through the command line
(overriding values from `.env`):

```bash
python meteo_rouen_meshtastic.py --host 192.168.1.50 --ville "Paris" --lat 48.8566 --lon 2.3522
python meteo_rouen_meshtastic.py --no-ping          # disable the wake-up ping
```

## 📁 Project Structure

| File                                                   | Purpose                                                                               |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| [meteo_rouen_meshtastic.py](meteo_rouen_meshtastic.py) | Main script: fetches weather data, wakes the node (ping), and publishes to Meshtastic |
| [scheduler.py](scheduler.py)                           | Daily scheduling loop (8 AM, Paris time)                                              |
| [Dockerfile](Dockerfile)                               | Container image (Python + `iputils-ping` for the wake-up ping)                        |
| [docker-compose.yml](docker-compose.yml)               | Container orchestration                                                               |
| [Makefile](Makefile)                                   | `make build/up/down/test/send/update/...` shortcuts                                   |
| [requirements.txt](requirements.txt)                   | Python dependencies                                                                   |
| [.env.example](.env.example)                           | Configuration template to copy to `.env`                                              |

## ⚙️ Environment Variables

| Variable                            | Default          | Description                                                          |
| ----------------------------------- | ---------------- | -------------------------------------------------------------------- |
| `MESHTASTIC_HOST`                   | *(required)*     | IP address or hostname of the Meshtastic node                        |
| `MESHTASTIC_PORT`                   | `4403`           | Meshtastic TCP API port                                              |
| `MESHTASTIC_CHANNEL_NAME`           | `meteo`          | Target channel name                                                  |
| `MESHTASTIC_CHANNEL_INDEX`          | —                | Force the channel index if the name cannot be resolved               |
| `METEO_VILLE`                       | `Rouen`          | City name displayed in the message                                   |
| `METEO_LAT` / `METEO_LON`           | 49.4432 / 1.0999 | GPS coordinates used for the forecast                                |
| `PING_BEFORE_SEND`                  | `true`           | Send an ICMP wake-up ping before connecting via TCP                  |
| `PING_TIMEOUT_S`                    | `2`              | Ping timeout in seconds                                              |
| `SEND_SETTLE_SECONDS`               | `2`              | Delay after sending before closing the TCP connection                |
| `WEATHER_RETRY_ATTEMPTS`            | `5`              | Number of attempts when the weather API encounters a transient error |
| `WEATHER_RETRY_BASE_DELAY_S`        | `2`              | Base delay (seconds) for exponential backoff between attempts        |
| `SCHEDULE_HOUR` / `SCHEDULE_MINUTE` | `8` / `0`        | Daily delivery time (Paris time)                                     |
| `RUN_ON_STARTUP`                    | `false`          | Also send a message immediately when the container starts            |
| `JOB_RETRY_ATTEMPTS`                | `3`              | Number of attempts for the daily publication if it fails             |
| `JOB_RETRY_DELAY_S`                 | `600`            | Delay (seconds) between daily publication attempts                   |

## 📝 License

Personal project, no specific license — adapt it to your needs.
