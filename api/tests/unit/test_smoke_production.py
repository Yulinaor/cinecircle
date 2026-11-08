"""The production smoke script, run against a fake deployment (httpx.MockTransport): no test here
touches the network."""

import base64
import json

import httpx
import pytest

from scripts.smoke_production import Failure, check

API = "https://api.test"
WEB = "https://web.test"
INDEX = '<!doctype html><html><head><script type="module" src="/assets/index-abc.js"></script>'
BUNDLE = 'const url="https://x.supabase.co";const key="sb_publishable_abc";'
# Built in pieces so no secret-shaped literal sits in the repository.
FAKE_SECRET = "sb_" + "secret_" + "x1Y2z3" * 5
SECRET_CHECK = "web bundle holds no secret key"


def _jwt(role: str) -> str:
    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'HS256', 'typ': 'JWT'})}.{part({'role': role, 'iss': 'x'})}.c2ln"


class FakeTime:
    """A clock the tests move by hand; `sleep` moves it too."""

    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _json(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body)


def _js(text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "text/javascript"})


def _healthy(request: httpx.Request, **overrides) -> httpx.Response:
    """A correct deployment. `overrides` maps "METHOD host/path" to a replacement response."""
    key = f"{request.method} {request.url.host}{request.url.path}"
    if key in overrides:
        return overrides[key]
    origin = request.headers.get("origin")
    if request.url.host == "api.test":
        if request.method == "OPTIONS" and request.url.path == "/me":
            if origin == WEB:
                return httpx.Response(200, headers={"access-control-allow-origin": WEB})
            return httpx.Response(400, text="Disallowed CORS origin")
        return {
            "/live": _json(200, {"status": "ok"}),
            "/health": _json(200, {"status": "ok", "db": "ok"}),
            "/me": _json(401, {"detail": "not_authenticated"}),
        }.get(request.url.path, _json(404, {"detail": "not_found"}))
    if request.url.path == "/assets/index-abc.js":
        return _js(BUNDLE)
    return httpx.Response(200, text=INDEX, headers={"content-type": "text/html"})


def _client(**overrides) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: _healthy(request, **overrides))
    )


def _run(client: httpx.Client) -> list[Failure]:
    fake = FakeTime()
    return check(client, API, WEB, sleep=fake.sleep, clock=fake.clock)


def _bundle_client(text: str) -> httpx.Client:
    return _client(**{"GET web.test/assets/index-abc.js": _js(text)})


def test_smoke_passes_on_a_healthy_deployment():
    assert _run(_client()) == []


def test_smoke_reports_each_failure():
    client = _client(
        **{
            "GET api.test/docs": _json(200, {}),
            "OPTIONS api.test/me": httpx.Response(
                200, headers={"access-control-allow-origin": "*"}
            ),
            "GET api.test/health": _json(503, {"status": "degraded", "db": "unreachable"}),
            "GET web.test/assets/index-abc.js": _js(f'k="{FAKE_SECRET}"'),
        }
    )
    failures = _run(client)
    assert sorted(f.check for f in failures) == [
        "GET /docs is 404",
        "GET /health is ok",
        "OPTIONS /me refuses another origin",
        SECRET_CHECK,
    ]
    # A failure says what was wrong but never repeats the secret itself.
    assert all(FAKE_SECRET not in f.detail for f in failures)


def test_smoke_reports_an_unprotected_me_and_a_missing_deep_link():
    client = _client(
        **{
            "GET api.test/me": _json(200, {}),
            "GET web.test/stats": httpx.Response(404, text="nope"),
            "GET api.test/openapi.json": _json(200, {}),
        }
    )
    assert sorted(f.check for f in _run(client)) == [
        "GET /me without a token is 401",
        "GET /openapi.json is 404",
        "web /stats serves the app",
    ]


# ----- the secret scan ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bundle",
    [
        # supabase-js itself tests for the prefix; the word alone is not a key.
        'if(e.startsWith(`sb_secret_`))throw Error("secret key in browser")',
        'if (key.startsWith("sb_secret_")) {}',
        "sb_secret_short",
        'const role="service_role"',
        f'const anon="{_jwt("anon")}"',
        'const odd="eyJhbGciOi.eyJ-not-base64.sig"',  # looks like a JWT, decodes to nothing
        f'const user="{_jwt("authenticated")}"',
    ],
)
def test_the_scan_passes_bundles_without_a_real_key(bundle):
    assert _run(_bundle_client(bundle)) == []


@pytest.mark.parametrize(
    "bundle, marker",
    [
        (f'k="{FAKE_SECRET}"', "sb_secret_"),
        (f"k='{FAKE_SECRET}'", "sb_secret_"),
        (f'k="{_jwt("service_role")}"', "service_role"),
        (f'a="{_jwt("anon")}";b="{_jwt("service_role")}"', "service_role"),
    ],
)
def test_the_scan_fails_on_a_real_key(bundle, marker):
    failures = _run(_bundle_client(bundle))
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert marker in failures[0].detail
    # The matched text is never echoed, only the marker and the file.
    assert FAKE_SECRET not in failures[0].detail
    assert "eyJ" not in failures[0].detail


def test_the_scan_follows_imported_chunks():
    def chunk(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/assets/index-abc.js":
            return _js('import("./lazy-1.js")')
        if request.url.path == "/assets/lazy-1.js":
            return _js(f'k="{FAKE_SECRET}"')
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(chunk))
    failures = _run(client)
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert "/assets/lazy-1.js" in failures[0].detail


def _chunk_answers(status: int):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/assets/index-abc.js":
            return _js('import("./chunk.js")')
        if request.url.path == "/assets/chunk.js":
            return httpx.Response(status, text="nope")
        return _healthy(request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_scan_still_passes_when_a_guessed_chunk_is_404():
    assert _run(_chunk_answers(404)) == []


@pytest.mark.parametrize("status", [429, 500, 503])
def test_the_scan_fails_when_a_chunk_answers_anything_but_200_or_404(status):
    failures = _run(_chunk_answers(status))
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert f"/assets/chunk.js answered {status}" in failures[0].detail


def test_the_scan_fails_when_there_is_nothing_to_scan():
    def page_without_scripts(request: httpx.Request) -> httpx.Response:
        if request.url.host == "web.test":
            return httpx.Response(
                200, text="<!doctype html><p>hi", headers={"content-type": "text/html"}
            )
        return _healthy(request)

    failures = _run(httpx.Client(transport=httpx.MockTransport(page_without_scripts)))
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert "no script" in failures[0].detail


def test_the_scan_fails_when_a_script_does_not_load():
    failures = _run(
        _client(**{"GET web.test/assets/index-abc.js": httpx.Response(404, text="gone")})
    )
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert "404" in failures[0].detail


def test_the_scan_fails_when_it_hits_its_file_limit():
    def endless(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "web.test" and path.endswith(".js"):
            n = int(path.rsplit("-", 1)[-1].removesuffix(".js")) if "chunk-" in path else 0
            return _js(f'import("./chunk-{n + 1}.js")')
        return _healthy(request)

    failures = _run(httpx.Client(transport=httpx.MockTransport(endless)))
    assert [f.check for f in failures] == [SECRET_CHECK]
    assert "limit" in failures[0].detail


# ----- waking the server ----------------------------------------------------------------------


def test_smoke_waits_for_a_sleeping_server():
    calls = {"live": 0}
    fake = FakeTime()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test" and request.url.path == "/live":
            calls["live"] += 1
            if calls["live"] <= 2:
                raise httpx.ConnectError("asleep")
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert check(client, API, WEB, sleep=fake.sleep, clock=fake.clock) == []
    assert calls["live"] == 3
    assert fake.now > 0  # it did wait


def test_smoke_gives_up_when_the_server_never_wakes():
    fake = FakeTime()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            return httpx.Response(502)
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    failures = check(client, API, WEB, sleep=fake.sleep, clock=fake.clock)
    assert [f.check for f in failures] == ["GET /live is 200"]
    assert "502" in failures[0].detail
    assert fake.now <= 90


def test_a_hanging_server_stops_at_the_deadline():
    """Each attempt is cut short by a timeout, so waiting is bounded by the clock and not by a
    count of sleeps: here every attempt eats its whole timeout."""
    fake = FakeTime()
    seen: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            read_timeout = request.extensions["timeout"]["read"]
            seen.append(read_timeout)
            fake.now += read_timeout
            raise httpx.ReadTimeout("hung")
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    failures = check(client, API, WEB, sleep=fake.sleep, clock=fake.clock)
    assert [f.check for f in failures] == ["GET /live is 200"]
    assert max(seen) <= 10  # a short per-attempt timeout, not the client's 30 s
    assert 89 <= fake.now <= 91


# ----- other answers the server might give -------------------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["ok"]),
        httpx.Response(200, json={"status": "ok", "db": ["ok"]}),
        httpx.Response(200, text="", headers={"content-type": "application/json"}),
    ],
)
def test_a_malformed_health_body_is_a_failure_not_a_traceback(response):
    failures = _run(_client(**{"GET api.test/health": response}))
    assert [f.check for f in failures] == ["GET /health is ok"]


def test_smoke_main_exit_codes(monkeypatch, capsys):
    from scripts import smoke_production

    monkeypatch.setattr(smoke_production, "_make_client", lambda: _client())
    assert smoke_production.main(["--api", API, "--web", WEB]) == 0
    assert "ok" in capsys.readouterr().out

    monkeypatch.setattr(
        smoke_production, "_make_client", lambda: _client(**{"GET api.test/docs": _json(200, {})})
    )
    assert smoke_production.main(["--api", API, "--web", WEB]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "/docs" in out


@pytest.mark.parametrize(
    "url", ["https://cinecircle-server.onrender.com", "https://cinecircle-web.onrender.com"]
)
def test_defaults_point_at_the_render_services(url):
    from scripts import smoke_production

    assert url in (smoke_production.DEFAULT_API, smoke_production.DEFAULT_WEB)
