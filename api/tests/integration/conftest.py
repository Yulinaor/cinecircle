import os

import pytest
import sqlalchemy as sa

from cinecircle_api.db import make_engine

URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:55322/postgres"
)
_TRUNCATE = sa.text(
    "TRUNCATE app.title_genres, app.title_seasons, app.titles, app.genres RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session")
def engine() -> sa.Engine:
    return make_engine(URL)


@pytest.fixture
def clean_catalog(engine):
    # Before too: a manual `npm run api:dev` session leaves cached titles behind.
    with engine.begin() as conn:
        conn.execute(_TRUNCATE)
    yield
    with engine.begin() as conn:
        conn.execute(_TRUNCATE)
