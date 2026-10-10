# Ingress Checkpoint Bot

🇫🇷 [Version française](README.fr.md)

A lightweight, asynchronous Telegram bot that gives Ingress **checkpoint** and **septicycle** times in French local time.

## Features

- Next checkpoint with countdown; checkpoints for today, tomorrow or any given date
- Next checkpoints at a given hour (`/cp 14H`)
- Current and next septicycle, septicycle `yyyy.nn`, full list for a year
- Daylight saving time handled (`Europe/Paris`, configurable with `BOT_TZ`)
- Everything is computed locally; nothing about users is written to disk
- Optional access control through [res.blue](https://res.blue) (OneRing): only agents approved on 1R can use the commands

## Commands

| Command | Effect |
|---|---|
| `/today` | Today's checkpoints |
| `/next` or `/cp` | Next checkpoint |
| `/tomorrow` | Tomorrow's checkpoints |
| `/cp yyyy-mm-dd` | Checkpoints for the given day |
| `/cp xxH` | Next checkpoints at hour xx |
| `/cycle`, `/sp`, `/septicycle` | Next septicycle |
| `/sp yyyy.nn` | Septicycle nn of year yyyy |
| `/sp yyyy` | Start and end of every septicycle in year yyyy |
| `/help`, `/tos` | Help, terms of service |

## Requirements

- Python 3.10+ (3.11 in the Docker image)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))

## Installation

```bash
git clone https://github.com/alithiel31/ingress-cp-bot.git
cd ingress-cp-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

```env
TELEGRAM_TOKEN=your_botfather_token
BOT_TZ=Europe/Paris
```

`.env` is ignored by Git: never commit it.

### res.blue authentication (optional)

Set `ONERING_APIKEY` in `.env` (API tab of your OneRing profile; the key owner needs a score of at least 5).
The bot then checks each user's Telegram ID with `GET /api/v1/agent-info?telegramid=…` and only serves
agents **approved on 1R**; `/start`, `/help` and `/tos` stay public. Without the key, the bot is public.
Results are cached in memory (1 h approved, 5 min refused) to stay under the 100 requests/hour rate limit,
and the Telegram ID is sent to res.blue. If res.blue is unreachable, access is denied (fail closed).

## Run

```bash
python main.py
```

### With Docker

```bash
docker compose up -d --build
docker compose logs -f
```

The image runs as a non-root user. The bot writes a *heartbeat* file every 30 s in `/app/data`
(`bot_data` volume); the Docker `HEALTHCHECK` marks the container `unhealthy` if it is older than 2 minutes.

> Run a single instance per token: two bots polling with the same token get a `409 Conflict` from Telegram.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions (`.github/workflows/ci.yml`) runs the tests, then builds the Docker image.

## How it works

- Checkpoint: one every 5 h (multiples of 5 h of the Unix timestamp, UTC).
- Septicycle: 35 checkpoints = 175 h (multiples of 175 h of the Unix timestamp).
- `yyyy.nn` numbering: the n-th septicycle whose start falls in year `yyyy` (local time), counting from 1.
  This is a convention of this bot; adapt `cycle_label()` in `ingress.py` if you prefer another one.

## Layout

- `main.py`: Telegram wiring (python-telegram-bot) and heartbeat
- `commands.py`: command → reply text
- `ingress.py`: pure calculations, no dependency
- `auth.py`: optional res.blue (OneRing) authentication with in-memory cache
- `tests/`: unit tests

## Privacy

See [PRIVACY.md](PRIVACY.md).

## License

[MIT](LICENSE)

## Disclaimer

Not affiliated with Niantic. Ingress is a trademark of Niantic, Inc.
