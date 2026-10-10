"""Logique pure : checkpoints et septicycles Ingress.

Les checkpoints et cycles sont de simples modulos du timestamp Unix (UTC) :
  - un checkpoint toutes les 5 h
  - un septicycle = 35 checkpoints = 175 h
Aucune époque particulière n'est nécessaire (le premier cycle des scores régionaux
a commencé le 2014-01-15 10:00 UTC, ce qui est bien un multiple de 175 h).

Tous les instants manipulés ici sont des timestamps Unix en secondes (int).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CHECKPOINT_S = 5 * 3600
CYCLE_S = 35 * CHECKPOINT_S
DEFAULT_TZ = ZoneInfo("Europe/Paris")


def local(ts: int, tz: ZoneInfo = DEFAULT_TZ) -> datetime:
    """Timestamp -> datetime locale."""
    return datetime.fromtimestamp(ts, tz)


# ---------- Checkpoints ----------

def next_checkpoint(now: int) -> int:
    """Prochain checkpoint strictement après `now`."""
    return (now // CHECKPOINT_S + 1) * CHECKPOINT_S


def checkpoints_between(start: int, end: int) -> list[int]:
    """Checkpoints dans l'intervalle [start, end[."""
    first = -(-start // CHECKPOINT_S) * CHECKPOINT_S  # arrondi au multiple supérieur
    return list(range(first, end, CHECKPOINT_S))


def day_bounds(d: date, tz: ZoneInfo = DEFAULT_TZ) -> tuple[int, int]:
    """[minuit local de d, minuit local de d+1[ (gère les jours de 23 h / 25 h)."""
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    nxt = d + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz)
    return int(start.timestamp()), int(end.timestamp())


def checkpoints_of_day(d: date, tz: ZoneInfo = DEFAULT_TZ) -> list[int]:
    return checkpoints_between(*day_bounds(d, tz))


def next_checkpoints_at_hour(hour: int, now: int, count: int = 5, tz: ZoneInfo = DEFAULT_TZ) -> list[int]:
    """Les `count` prochains checkpoints tombant à l'heure locale `hour`."""
    out: list[int] = []
    t = next_checkpoint(now)
    # L'heure locale se répète tous les 5 jours : borne large de sécurité
    for _ in range(count * 40):
        if local(t, tz).hour == hour:
            out.append(t)
            if len(out) == count:
                break
        t += CHECKPOINT_S
    return out


# ---------- Septicycles ----------

def cycle_start_of(ts: int) -> int:
    """Début du septicycle en cours à l'instant ts."""
    return ts // CYCLE_S * CYCLE_S


def next_cycle_start(now: int) -> int:
    return cycle_start_of(now) + CYCLE_S


def _first_cycle_start_of_year(year: int, tz: ZoneInfo) -> int:
    jan1 = int(datetime(year, 1, 1, tzinfo=tz).timestamp())
    return -(-jan1 // CYCLE_S) * CYCLE_S


def cycle_label(cycle_start: int, tz: ZoneInfo = DEFAULT_TZ) -> str:
    """Convention : yyyy.nn = n-ième septicycle dont le début tombe (heure locale)
    dans l'année yyyy, en comptant à partir de 1."""
    year = local(cycle_start, tz).year
    n = (cycle_start - _first_cycle_start_of_year(year, tz)) // CYCLE_S + 1
    return f"{year}.{n:02d}"


def cycles_of_year(year: int, tz: ZoneInfo = DEFAULT_TZ) -> list[tuple[int, int, int]]:
    """Tous les septicycles d'une année : [(n, début, fin)]."""
    out = []
    start = _first_cycle_start_of_year(year, tz)
    n = 1
    while local(start, tz).year == year:
        out.append((n, start, start + CYCLE_S))
        start += CYCLE_S
        n += 1
    return out


def cycle_of_year(year: int, n: int, tz: ZoneInfo = DEFAULT_TZ):
    """Septicycle yyyy.nn sous la forme (n, début, fin), ou None."""
    for c in cycles_of_year(year, tz):
        if c[0] == n:
            return c
    return None
