"""The production smoke script, run against a fake deployment (httpx.MockTransport): no test here
touches the network."""

import httpx
import pytest

from scripts.smoke_production import Failure, check

API = "https://api.test"
WEB = "https://web.test"
INDEX = '<!doctype html><html><head><script type="module" src="/assets/index-abc.js"></script>'
BUNDLE = 'const url="https://x.supabase.co";const key="sb_publishable_abc";'


def _json(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)


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
        return httpx.Response(200, text=BUNDLE, headers={"content-type": "text/javascript"})
    return httpx.Response(200, text=INDEX, headers={"content-type": "text/html"})


def _client(**overrides) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: _healthy(request, **overrides))
    )


def _run(client: httpx.Client, **kwargs) -> list[Failure]:
    return check(client, API, WEB, sleep=lambda _: None, **kwargs)


def test_smoke_passes_on_a_healthy_deployment():
    assert _run(_client()) == []


def test_smoke_reports_each_failure():
    leaky = httpx.Response(
        200, text='k="sb_secret_abc123"', headers={"content-type": "text/javascript"}
    )
    client = _client(
        **{
            "GET api.test/docs": _json(200, {}),
            "OPTIONS api.test/me": httpx.Response(
                200, headers={"access-control-allow-origin": "*"}
            ),
            "GET api.test/health": _json(503, {"status": "degraded", "db": "unreachable"}),
            "GET web.test/assets/index-abc.js": leaky,
        }
    )
    failures = _run(client)
    assert sorted(f.check for f in failures) == [
        "GET /docs is 404",
        "GET /health is ok",
        "OPTIONS /me refuses another origin",
        "web bundle holds no secret key",
    ]
    # A failure says what was wrong but never repeats the secret itself.
    assert all("sb_secret_abc123" not in f.detail for f in failures)


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


def test_smoke_waits_for_a_sleeping_server():
    calls = {"live": 0}
    naps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test" and request.url.path == "/live":
            calls["live"] += 1
            if calls["live"] <= 2:
                raise httpx.ConnectError("asleep")
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert check(client, API, WEB, sleep=naps.append) == []
    assert calls["live"] == 3
    assert len(naps) == 2


def test_smoke_gives_up_when_the_server_never_wakes():
    naps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            return httpx.Response(502)
        return _healthy(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    failures = check(client, API, WEB, sleep=naps.append)
    assert [f.check for f in failures] == ["GET /live is 200"]
    assert sum(naps) <= 90


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
