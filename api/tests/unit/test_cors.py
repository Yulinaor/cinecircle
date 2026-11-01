from fastapi.testclient import TestClient

from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings


def _client():
    settings = Settings(
        database_url="postgresql+psycopg://x@127.0.0.1:1/x",
        cors_origins=["http://localhost:5173"],
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_cors_allows_configured_origin_only():
    ok = _client().get("/live", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = _client().get("/live", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
