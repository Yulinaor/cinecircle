import time

from fastapi.testclient import TestClient

from cinecircle_api.db import check_db, make_engine
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"  # nothing listens on port 1


def test_make_engine_is_lazy():
    make_engine(DEAD)  # must not raise or connect


def test_check_db_unreachable_is_fast():
    t0 = time.monotonic()
    assert check_db(make_engine(DEAD)) == "unreachable"
    assert time.monotonic() - t0 < 5


def test_health_503_when_db_down():
    app = create_app(Settings(database_url=DEAD, _env_file=None))
    r = TestClient(app).get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "db": "unreachable"}


def test_health_200_when_db_ok(monkeypatch):
    app = create_app(Settings(database_url=DEAD, _env_file=None))
    monkeypatch.setattr("cinecircle_api.routes.health.check_db", lambda engine: "ok")
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}
