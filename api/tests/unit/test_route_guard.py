"""Every route except the liveness/health probes must demand a signed-in user."""

import pytest
from fastapi.testclient import TestClient

from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings
from tests.tokens import auth_settings, make_token

DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"
OPEN_PATHS = {"/live", "/health"}
# One placeholder per path parameter; later tasks add their own (e.g. "username": "gal").
PATH_PARAMS = {"media_type": "movie", "tmdb_id": "1", "title_id": "1"}
UID = "6f1c2b6e-0000-4000-8000-000000000001"


def test_every_route_requires_sign_in():
    app = create_app(auth_settings(DEAD))
    client = TestClient(app)
    # FastAPI nests included routers (app.routes no longer lists their paths), so walk the
    # OpenAPI document instead. Routes hidden from the schema would escape this check.
    paths = app.openapi()["paths"]
    for path, operations in paths.items():
        if path in OPEN_PATHS:
            continue
        for method in operations:
            r = client.request(method.upper(), path.format_map(PATH_PARAMS))
            assert r.status_code == 401, (method, path)
            assert r.headers["www-authenticate"] == "Bearer"
    assert "/titles/tmdb/{media_type}/{tmdb_id}" in paths


def test_probes_stay_open():
    client = TestClient(create_app(auth_settings(DEAD)))
    assert client.get("/live").status_code == 200
    assert client.get("/health").status_code in (200, 503)  # DB is dead here; never 401


@pytest.mark.parametrize("app_env", ["production", "test"])
def test_docs_and_schema_not_served_outside_local(app_env):
    client = TestClient(create_app(auth_settings(DEAD, app_env=app_env)))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_docs_served_locally():
    client = TestClient(create_app(auth_settings(DEAD)))
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer ", "Basic abc", "Bearer garbage"])
def test_bad_authorization_header_401(header):
    client = TestClient(create_app(auth_settings(DEAD)))
    headers = {} if header is None else {"Authorization": header}
    r = client.get("/titles/search", params={"q": "x"}, headers=headers)
    assert (r.status_code, r.json()) == (401, {"detail": "not_authenticated"})
    assert r.headers["www-authenticate"] == "Bearer"


def test_auth_unconfigured_503(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    client = TestClient(create_app(Settings(database_url=DEAD, _env_file=None)))
    headers = {"Authorization": f"Bearer {make_token(UID)}"}
    r = client.get("/titles/search", params={"q": "x"}, headers=headers)
    assert (r.status_code, r.json()) == (503, {"detail": "auth_unavailable"})
