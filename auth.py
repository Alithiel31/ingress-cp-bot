"""Authentification via res.blue (OneRing) : le compte Telegram doit être un agent approuvé sur 1R.

L'ID Telegram vient de Telegram lui-même (non falsifiable) ; on interroge
GET /api/v1/agent-info?telegramid=<id> avec la clé API du propriétaire du bot.
Les verdicts sont gardés en mémoire (jamais sur disque) pour rester sous la limite
de 100 requêtes par heure de l'API.
"""

import logging
import os
import time
from collections.abc import Callable
from enum import Enum

import httpx

log = logging.getLogger("ingress-cp-bot.auth")

BASE_URL = "https://res.blue"
TTL_OK_S = 3600  # agent approuvé : revérifié toutes les heures
TTL_REFUSED_S = 300  # refusé : on laisse l'utilisateur corriger son profil et réessayer
TTL_UNAVAILABLE_S = 30  # panne / limite : on ne martèle pas l'API
CACHE_MAX = 2000


class Verdict(Enum):
    OK = "ok"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


def _is_approved(payload) -> bool:
    """success=true et approved_on_1R=true (la doc indique true/false/none)."""
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return False
    return str(payload.get("approved_on_1R")).lower() == "true"


class OneRingAuth:
    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=10)
        self._clock = clock
        self._cache: dict[int, tuple[float, Verdict]] = {}

    @classmethod
    def from_env(cls) -> "OneRingAuth | None":
        """None si ONERING_APIKEY est absente : l'authentification est alors désactivée."""
        key = os.environ.get("ONERING_APIKEY", "").strip()
        return cls(key) if key else None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check(self, telegram_id: int) -> Verdict:
        now = self._clock()
        cached = self._cache.get(telegram_id)
        if cached and cached[0] > now:
            return cached[1]

        verdict = await self._fetch(telegram_id)
        ttl = {Verdict.OK: TTL_OK_S, Verdict.REFUSED: TTL_REFUSED_S}.get(verdict, TTL_UNAVAILABLE_S)
        self._store(telegram_id, verdict, now + ttl)
        return verdict

    def _store(self, telegram_id: int, verdict: Verdict, expires: float) -> None:
        if len(self._cache) >= CACHE_MAX:
            now = self._clock()
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
            if len(self._cache) >= CACHE_MAX:
                self._cache.clear()
        self._cache[telegram_id] = (expires, verdict)

    async def _fetch(self, telegram_id: int) -> Verdict:
        try:
            resp = await self._client.get(
                f"{self._base_url}/api/v1/agent-info",
                params={"telegramid": telegram_id},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.HTTPError as exc:
            # Pas de message d'exception : il peut contenir l'URL complète.
            log.warning("res.blue injoignable (%s)", type(exc).__name__)
            return Verdict.UNAVAILABLE

        match resp.status_code:
            case 200:
                try:
                    payload = resp.json()
                except ValueError:
                    log.warning("Réponse res.blue illisible (JSON invalide)")
                    return Verdict.UNAVAILABLE
                return Verdict.OK if _is_approved(payload) else Verdict.REFUSED
            case 404:
                return Verdict.REFUSED
            case 401:
                log.error("res.blue : clé API absente ou invalide (401)")
            case 403:
                log.error("res.blue : score insuffisant pour la clé API, il faut au moins 5 (403)")
            case 429:
                log.warning("res.blue : limite de requêtes dépassée (429)")
            case code:
                log.warning("res.blue : réponse inattendue (%s)", code)
        return Verdict.UNAVAILABLE
