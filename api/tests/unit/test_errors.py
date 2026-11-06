"""Exception handlers and shutdown behaviour of the app."""

import pytest
from fastapi.testclient import TestClient

from cinecircle_api.main import create_app
from tests.tokens import auth_settings, make_token

DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"
UID = "6f1c2b6e-0000-4000-8000-000000000001"
AUTH = {"Authorization": f"Bearer {make_token(UID)}"}


def client(**settings) -> TestClient:
    return TestClient(create_app(auth_settings(DEAD, **settings)), headers=AUTH)


def test_db_down_is_503():
    r = client().get("/titles/1")
    assert (r.status_code, r.json()) == (503, {"detail": "db_unavailable"})


@pytest.mark.parametrize("path", ["/titles/abc", "/titles/tmdb", "/titles/tmdb/person/1"])
def test_bad_path_param_is_404(path):
    r = client().get(path)
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})


def test_query_validation_stays_422():
    assert client().get("/titles/search", params={"q": ""}).status_code == 422


def test_mixed_path_and_query_errors_stay_422():
    assert client().get("/titles/abc", params={"lang": "xx"}).status_code == 422


def test_shutdown_closes_http_clients():
    app = create_app(auth_settings(DEAD, tmdb_api_key="k", omdb_api_key="k"))
    service = app.state.title_service
    with TestClient(app):
        assert not service._tmdb._http.is_closed
        assert not service._omdb._http.is_closed
    assert service._tmdb._http.is_closed
    assert service._omdb._http.is_closed
