"""Exception handlers and shutdown behaviour of the app."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from cinecircle_api.db import UserDb
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


def test_unknown_path_is_404_not_found():
    r = client().get("/users/gal/followers")  # signed in, no such route
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})
    r = TestClient(create_app(auth_settings(DEAD))).get("/nope")  # unknown paths need no sign-in
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})


def test_wrong_method_stays_405_and_other_http_errors_keep_their_detail():
    r = client().post("/live")
    assert r.status_code == 405
    assert r.json() == {"detail": "Method Not Allowed"}
    assert "allow" in r.headers
    r = TestClient(create_app(auth_settings(DEAD))).get("/me")
    assert (r.status_code, r.json()) == (401, {"detail": "not_authenticated"})


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


def test_unauthenticated_is_401_before_any_db_connection():
    r = TestClient(create_app(auth_settings(DEAD))).get("/titles/1")
    assert (r.status_code, r.json()) == (401, {"detail": "not_authenticated"})


def test_user_db_route_on_a_dead_database_is_503():
    router = APIRouter()

    @router.get("/_t/db")
    def db_route(db: UserDb) -> dict:
        return {"ok": True}

    app = create_app(auth_settings(DEAD))
    app.include_router(router)
    r = TestClient(app, headers=AUTH).get("/_t/db")
    assert (r.status_code, r.json()) == (503, {"detail": "db_unavailable"})
