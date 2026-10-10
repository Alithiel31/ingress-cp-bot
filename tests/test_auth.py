import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import TTL_OK_S, TTL_REFUSED_S, TTL_UNAVAILABLE_S, OneRingAuth, Verdict


class FakeApi:
    """Faux res.blue : compte les appels et répond selon `response`."""

    def __init__(self, response):
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_auth(api: FakeApi, now: list[float] | None = None) -> OneRingAuth:
    now = now if now is not None else [0.0]
    client = httpx.AsyncClient(transport=httpx.MockTransport(api))
    return OneRingAuth("CLE-DE-TEST", base_url="https://exemple.test", client=client, clock=lambda: now[0])


def ok_payload(approved):
    return httpx.Response(200, json={"success": True, "data": {}, "approved_on_1R": approved})


class VerdictTests(unittest.IsolatedAsyncioTestCase):
    async def test_approved_agent_is_ok_and_request_is_well_formed(self):
        api = FakeApi(ok_payload(True))
        self.assertEqual(await make_auth(api).check(42), Verdict.OK)
        req = api.requests[0]
        self.assertEqual(req.url.path, "/api/v1/agent-info")
        self.assertEqual(req.url.params["telegramid"], "42")
        self.assertEqual(req.headers["Authorization"], "Bearer CLE-DE-TEST")

    async def test_not_approved_is_refused(self):
        for approved in (False, "none", None):
            api = FakeApi(ok_payload(approved))
            self.assertEqual(await make_auth(api).check(1), Verdict.REFUSED, approved)

    async def test_unknown_agent_is_refused(self):
        api = FakeApi(httpx.Response(200, json={"success": False, "data": {}}))
        self.assertEqual(await make_auth(api).check(1), Verdict.REFUSED)
        api = FakeApi(httpx.Response(404))
        self.assertEqual(await make_auth(api).check(1), Verdict.REFUSED)

    async def test_api_problems_are_unavailable_not_refused(self):
        cases = [
            httpx.Response(401), httpx.Response(403), httpx.Response(429), httpx.Response(500),
            httpx.Response(200, content=b"pas du json"),
            httpx.ConnectError("réseau coupé"),
        ]
        for response in cases:
            self.assertEqual(await make_auth(FakeApi(response)).check(1), Verdict.UNAVAILABLE, response)


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_avoids_repeated_calls_until_ttl(self):
        now = [0.0]
        api = FakeApi(ok_payload(True))
        auth = make_auth(api, now)
        await auth.check(1)
        await auth.check(1)
        self.assertEqual(len(api.requests), 1)
        await auth.check(2)  # autre utilisateur : nouvel appel
        self.assertEqual(len(api.requests), 2)
        now[0] = TTL_OK_S + 1
        await auth.check(1)
        self.assertEqual(len(api.requests), 3)

    async def test_refused_and_unavailable_have_short_ttls(self):
        now = [0.0]
        api = FakeApi(ok_payload(False))
        auth = make_auth(api, now)
        await auth.check(1)
        now[0] = TTL_REFUSED_S - 1
        await auth.check(1)
        self.assertEqual(len(api.requests), 1)
        now[0] = TTL_REFUSED_S + 1
        await auth.check(1)
        self.assertEqual(len(api.requests), 2)

        api = FakeApi(httpx.Response(429))
        auth = make_auth(api, now)
        await auth.check(9)
        now[0] += TTL_UNAVAILABLE_S + 1
        await auth.check(9)
        self.assertEqual(len(api.requests), 2)


class FromEnvTests(unittest.TestCase):
    def test_disabled_without_key(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"ONERING_APIKEY": ""}):
            self.assertIsNone(OneRingAuth.from_env())
        with mock.patch.dict(os.environ, {"ONERING_APIKEY": "abc"}):
            self.assertIsNotNone(OneRingAuth.from_env())


if __name__ == "__main__":
    unittest.main()
