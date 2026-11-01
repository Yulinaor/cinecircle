import os

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from cinecircle_api.db import make_engine
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

pytestmark = pytest.mark.integration
URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
)


def test_health_ok_against_local_supabase():
    r = TestClient(create_app(Settings(database_url=URL, _env_file=None))).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "db": "ok"}


def test_anon_has_no_access_to_app_schema():
    with make_engine(URL).connect() as c:
        assert c.scalar(sa.text("select has_schema_privilege('anon', 'app', 'USAGE')")) is False
        assert (
            c.scalar(sa.text("select has_schema_privilege('authenticated', 'app', 'USAGE')"))
            is True
        )
