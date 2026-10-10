"""Traduit une commande + argument en texte de réponse (pur, testable)."""

import re
import time
from datetime import date, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

import ingress as ig

HINT = "\n\nTape /help pour la liste des commandes."
WEEKDAYS_FR = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")

class Entry(NamedTuple):
    """Une ligne d'aide. `menu` : description courte dans le menu Telegram (None = absente du menu)."""

    section: str
    usage: str
    desc: str
    command: str
    menu: str | None = None


CP, SP, OTHER = "📆 Checkpoints", "📅 Septicycles", "ℹ️ Autres"

# Source unique : alimente /help ET le menu des commandes Telegram.
ENTRIES = [
    Entry(CP, "/today", "Checkpoints du jour", "today", "Checkpoints du jour"),
    Entry(CP, "/next ou /cp", "Prochain checkpoint", "next", "Prochain checkpoint"),
    Entry(CP, "/tomorrow", "Checkpoints de demain", "tomorrow", "Checkpoints de demain"),
    Entry(CP, "/cp yyyy-mm-dd", "Checkpoints du jour donné", "cp", "Checkpoints : /cp yyyy-mm-dd ou /cp 14H"),
    Entry(CP, "/cp xxH", "Prochains checkpoints à l'heure xx (ex. /cp 14H)", "cp"),
    Entry(SP, "/cycle, /sp ou /septicycle", "Prochain septicycle", "cycle", "Prochain septicycle"),
    Entry(SP, "/sp yyyy.nn", "Septicycle nn de l'année yyyy", "sp", "Septicycles : /sp yyyy.nn ou /sp yyyy"),
    Entry(SP, "/sp yyyy", "Début et fin de chaque septicycle de l'année yyyy", "sp"),
    Entry(OTHER, "/help", "Cette aide", "help", "Aide"),
    Entry(OTHER, "/tos", "Conditions d'utilisation", "tos", "Conditions d'utilisation"),
]

# Toutes les commandes comprises par le bot (alias compris).
ALL_COMMANDS = ["start", "help", "tos", "today", "tomorrow", "next", "cp", "cycle", "septicycle", "sp"]
# Accessibles sans authentification res.blue.
PUBLIC_COMMANDS = {"start", "help", "tos"}


def menu_commands() -> list[tuple[str, str]]:
    """(commande, description) pour le menu Telegram."""
    return [(e.command, e.menu) for e in ENTRIES if e.menu]


def help_text(auth_enabled: bool = False) -> str:
    """Aide générée depuis ENTRIES ; marque 🔒 les commandes réservées si l'auth est active."""
    lines = ["✅ Ingress Checkpoint Bot 🔎", "Checkpoints et septicycles Ingress, en heure de France"]
    sections: dict[str, list[Entry]] = {}
    for e in ENTRIES:
        sections.setdefault(e.section, []).append(e)
    for title, entries in sections.items():
        lines += ["", title]
        for e in entries:
            lock = "🔒 " if auth_enabled and e.command not in PUBLIC_COMMANDS else ""
            lines.append(f"{lock}{e.usage} ▶️ {e.desc}")
    if auth_enabled:
        lines += ["", "🔒 Réservé aux agents approuvés sur res.blue"]
    return "\n".join(lines)


TOS_TEXT = """ℹ️ Conditions d'utilisation
Ce bot calcule uniquement les heures de checkpoints et de septicycles à partir d'une règle fixe
(5 h par checkpoint, 35 checkpoints = 175 h par septicycle).
Il ne conserve aucune donnée vous concernant sur disque et est fourni tel quel, sans aucune garantie.
Si l'authentification res.blue est activée, votre identifiant Telegram est transmis à res.blue
pour vérifier votre profil ; le résultat est gardé en mémoire au plus une heure.
Sans lien avec Niantic. Ingress est une marque de Niantic, Inc."""

DENIED_TEXT = """🔒 Accès réservé aux agents approuvés sur res.blue.
Vérifie que ton identifiant Telegram est renseigné sur ton profil OneRing (res.blue)
et que tu es approuvé, puis réessaie dans quelques minutes."""

UNAVAILABLE_TEXT = "⚠️ Vérification res.blue indisponible pour le moment, réessaie dans quelques instants."


# ---------- Formatage ----------

def fmt_time(ts: int, tz: ZoneInfo) -> str:
    return ig.local(ts, tz).strftime("%H:%M")


def fmt_datetime(ts: int, tz: ZoneInfo) -> str:
    d = ig.local(ts, tz)
    return f"{WEEKDAYS_FR[d.weekday()]}. {d:%d/%m/%Y %H:%M}"


def fmt_countdown(target: int, now: int) -> str:
    minutes = max(0, round((target - now) / 60))
    if minutes == 0:
        return "dans moins d'une minute"
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"dans {days} j {hours} h {minutes:02d} min"
    if hours:
        return f"dans {hours} h {minutes:02d} min"
    return f"dans {minutes} min"


# ---------- Commandes ----------

def _day_list(d: date, tz: ZoneInfo) -> str:
    lines = [f"• {fmt_time(t, tz)}" for t in ig.checkpoints_of_day(d, tz)]
    return f"📆 Checkpoints du {d:%d/%m/%Y}\n" + "\n".join(lines)


def _next(now: int, tz: ZoneInfo) -> str:
    t = ig.next_checkpoint(now)
    return f"⏱ Prochain checkpoint\n{fmt_datetime(t, tz)}\n{fmt_countdown(t, now)}"


def _checkpoint_cmd(arg: str, now: int, tz: ZoneInfo) -> str:
    if not arg:
        return _next(now, tz)

    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", arg):
        try:
            d = date(*map(int, m.groups()))
        except ValueError:
            return f"Date invalide : {arg}{HINT}"
        return _day_list(d, tz)

    if m := re.fullmatch(r"(\d{1,2})\s*h?", arg, re.IGNORECASE):
        hour = int(m.group(1))
        if hour > 23:
            return f"Heure invalide : {arg}{HINT}"
        lines = [f"• {fmt_datetime(t, tz)}" for t in ig.next_checkpoints_at_hour(hour, now, 5, tz)]
        return f"⏱ Prochains checkpoints à {hour:02d}h\n" + "\n".join(lines)

    return f"Argument non reconnu : {arg}{HINT}"


def _next_cycle(now: int, tz: ZoneInfo) -> str:
    current = ig.cycle_start_of(now)
    nxt = ig.next_cycle_start(now)
    return "\n".join([
        f"📅 Septicycle en cours : {ig.cycle_label(current, tz)}",
        f"Début : {fmt_datetime(current, tz)}",
        "",
        f"➡️ Prochain septicycle : {ig.cycle_label(nxt, tz)}",
        f"Début : {fmt_datetime(nxt, tz)}",
        fmt_countdown(nxt, now),
    ])


def _cycle_cmd(arg: str, now: int, tz: ZoneInfo) -> str:
    if not arg:
        return _next_cycle(now, tz)

    if m := re.fullmatch(r"(\d{4})[.\-/](\d{1,2})", arg):
        year, n = int(m.group(1)), int(m.group(2))
        c = ig.cycle_of_year(year, n, tz)
        if c is None:
            return f"Le septicycle {year}.{n:02d} n'existe pas.{HINT}"
        return "\n".join([
            f"📅 Septicycle {year}.{n:02d}",
            f"Début : {fmt_datetime(c[1], tz)}",
            f"Fin : {fmt_datetime(c[2], tz)}",
        ])

    if re.fullmatch(r"\d{4}", arg):
        year = int(arg)
        cycles = ig.cycles_of_year(year, tz)
        if not cycles:
            return f"Aucun septicycle trouvé pour {year}.{HINT}"
        lines = [f"{year}.{n:02d}  {fmt_datetime(s, tz)} → {fmt_datetime(e, tz)}" for n, s, e in cycles]
        return f"📅 Septicycles {year}\n" + "\n".join(lines)

    return f"Argument non reconnu : {arg}{HINT}"


def handle_command(
    command: str,
    arg: str = "",
    now: int | None = None,
    tz: ZoneInfo = ig.DEFAULT_TZ,
    auth_enabled: bool = False,
):
    """Retourne le texte de réponse, ou None si la commande est inconnue."""
    now = int(time.time()) if now is None else now
    arg = arg.strip()
    match command:
        case "start" | "help":
            return help_text(auth_enabled)
        case "tos":
            return TOS_TEXT
        case "today":
            return _day_list(ig.local(now, tz).date(), tz)
        case "tomorrow":
            return _day_list(ig.local(now, tz).date() + timedelta(days=1), tz)
        case "next":
            return _next(now, tz)
        case "cp":
            return _checkpoint_cmd(arg, now, tz)
        case "cycle" | "septicycle" | "sp":
            return _cycle_cmd(arg, now, tz)
    return None
