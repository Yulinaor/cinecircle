"""`UserDb`: every request query runs as the token user, in one transaction per request."""

import pytest
import sqlalchemy as sa
from fastapi import APIRouter
from fastapi.testclient import TestClient

from cinecircle_api.db import UserDb, act_as
from cinecircle_api.main import create_app
from tests.integration.conftest import URL, claims_for
from tests.tokens import auth_settings, make_token

pytestmark = pytest.mark.integration

_WHO = sa.text("SELECT auth.uid()::text, current_user")
_RENAME = sa.text("UPDATE app.profiles SET display_name = :name WHERE id = auth.uid()")
_NAME_OF = sa.text("SELECT display_name FROM app.profiles WHERE id = :id")


def build_client(user, *, raise_server_exceptions: bool = False) -> TestClient:
    router = APIRouter()

    @router.get("/_t/who")
    def who(db: UserDb) -> dict:
        uid, role = db.execute(_WHO).one()
        return {"uid": uid, "role": role}

    @router.post("/_t/rename-then-fail")
    def rename_then_fail(db: UserDb) -> dict:
        db.execute(_RENAME, {"name": "Changed"})
        raise RuntimeError("boom")

    @router.post("/_t/rename")
    def rename(db: UserDb) -> dict:
        db.execute(_RENAME, {"name": "Changed"})
        return {"ok": True}

    app = create_app(auth_settings(URL))
    app.include_router(router)
    headers = {"Authorization": f"Bearer {make_token(str(user.id))}"}
    client = TestClient(app, headers=headers, raise_server_exceptions=raise_server_exceptions)
    return client


def name_of(engine, user) -> str:
    with engine.connect() as conn:
        return conn.scalar(_NAME_OF, {"id": user.id})


def test_session_runs_as_the_token_user(people):
    client = build_client(people["gal"])
    r = client.get("/_t/who")
    assert r.status_code == 200
    assert r.json() == {"uid": str(people["gal"].id), "role": "authenticated"}


def test_role_does_not_leak_to_the_pool(people):
    client = build_client(people["gal"])
    # Replace the app's engine with a one-connection pool, so the next checkout is the same one.
    client.app.state.engine.dispose()
    single = sa.create_engine(URL, pool_size=1, max_overflow=0)
    client.app.state.engine = single
    assert client.get("/_t/who").json()["role"] == "authenticated"
    with single.connect() as conn:
        assert conn.scalar(sa.text("SELECT current_user")) == "postgres"
        assert conn.scalar(sa.text("SELECT auth.uid()")) is None
    single.dispose()


def test_handler_error_rolls_back(people, engine):
    client = build_client(people["gal"])
    r = client.post("/_t/rename-then-fail")
    assert r.status_code == 500
    assert name_of(engine, people["gal"]) == "Gal"


def test_write_is_committed(people, engine):
    client = build_client(people["gal"])
    assert client.post("/_t/rename").status_code == 200
    fresh = sa.create_engine(URL)
    try:
        assert name_of(fresh, people["gal"]) == "Changed"
    finally:
        fresh.dispose()


def test_stale_session_level_sub_cannot_override_the_token_user(people, engine):
    # Supabase's auth.uid() reads request.jwt.claim.sub before request.jwt.claims->>'sub'.
    with engine.connect() as conn:
        conn.execute(
            sa.text("SELECT set_config('request.jwt.claim.sub', :sub, false)"),
            {"sub": str(people["noa"].id)},
        )
        conn.commit()
        with conn.begin():
            act_as(conn, claims_for(people["gal"]))
            assert conn.scalar(sa.text("SELECT auth.uid()::text")) == str(people["gal"].id)
        conn.execute(sa.text("RESET request.jwt.claim.sub"))
        conn.commit()
