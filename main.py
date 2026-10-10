"""Bot Telegram : checkpoints et septicycles Ingress (heure de France).

Lancement :  python main.py   (le token est lu dans .env)
"""

import logging
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from auth import OneRingAuth, Verdict
from commands import (
    ALL_COMMANDS,
    DENIED_TEXT,
    PUBLIC_COMMANDS,
    UNAVAILABLE_TEXT,
    handle_command,
    menu_commands,
)

# Charge le fichier .env situé à côté de main.py (sans écraser les variables déjà définies,
# ce qui laisse la priorité à l'environnement fourni par Docker Compose).
load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # évite de logger le token dans les URLs
log = logging.getLogger("ingress-cp-bot")

TZ = ZoneInfo(os.environ.get("BOT_TZ", "Europe/Paris"))
HEARTBEAT_FILE = Path(os.environ.get("HEARTBEAT_FILE", "data/heartbeat"))
HEARTBEAT_INTERVAL_S = 30


async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    # "/cp@MonBot 14H" -> "cp"
    name = message.text.split()[0][1:].split("@")[0].lower()

    auth: OneRingAuth | None = context.bot_data.get("auth")
    if auth is not None and name not in PUBLIC_COMMANDS:
        user = update.effective_user
        verdict = await auth.check(user.id) if user else Verdict.REFUSED
        if verdict is not Verdict.OK:
            await message.reply_text(UNAVAILABLE_TEXT if verdict is Verdict.UNAVAILABLE else DENIED_TEXT)
            return

    reply = handle_command(name, " ".join(context.args or []), tz=TZ, auth_enabled=auth is not None)
    if reply:
        await message.reply_text(reply)


async def heartbeat(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Écrit l'heure courante dans un fichier : le HEALTHCHECK Docker le surveille."""
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.write_text(str(int(time.time())))


async def post_shutdown(app: Application) -> None:
    auth: OneRingAuth | None = app.bot_data.get("auth")
    if auth is not None:
        await auth.aclose()


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand(cmd, desc) for cmd, desc in menu_commands()])


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("TELEGRAM_TOKEN manquant : renseigne-le dans le fichier .env (voir .env.example).")

    app = ApplicationBuilder().token(token).post_init(post_init).post_shutdown(post_shutdown).build()
    auth = OneRingAuth.from_env()
    if auth is None:
        log.info("ONERING_APIKEY absente : authentification res.blue désactivée (bot public).")
    else:
        app.bot_data["auth"] = auth
        log.info("Authentification res.blue activée (agents approuvés sur 1R uniquement).")
    app.add_handler(CommandHandler(ALL_COMMANDS, on_command))

    if app.job_queue is None:
        log.warning("JobQueue indisponible (installer python-telegram-bot[job-queue]) : pas de heartbeat.")
    else:
        app.job_queue.run_repeating(heartbeat, interval=HEARTBEAT_INTERVAL_S, first=0)

    log.info("Bot démarré (fuseau %s).", TZ.key)
    app.run_polling()


if __name__ == "__main__":
    main()
