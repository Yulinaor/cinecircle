import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa

from cinecircle_api.db import act_as, make_engine

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


# ===== People (Gal = owner, Dana = approved follower, Noa = stranger, Ron = pending) =====

GAL_BIO = "gal-bio-sentinel"
TEST_EMAIL_DOMAIN = "test.cinecircle.local"


@dataclass(frozen=True)
class TestUser:
    __test__ = False  # not a pytest test class

    key: str
    id: UUID
    username: str
    email: str


def _user(key: str, n: int) -> TestUser:
    return TestUser(
        key=key,
        id=UUID(f"00000000-0000-4000-8000-0000000000{n:02d}"),
        username=key,
        email=f"{key}@{TEST_EMAIL_DOMAIN}",
    )


GAL, DANA, NOA, RON = _user("gal", 1), _user("dana", 2), _user("noa", 3), _user("ron", 4)
_DISPLAY_NAMES = {"gal": "Gal", "dana": "Dana", "noa": "נועה", "ron": "Ron"}

_DELETE_TEST_USERS = sa.text("DELETE FROM auth.users WHERE email LIKE :pattern").bindparams(
    pattern=f"%@{TEST_EMAIL_DOMAIN}"
)


def claims_for(user: TestUser) -> dict[str, Any]:
    return {"sub": str(user.id), "role": "authenticated"}


@contextmanager
def as_user(engine: sa.Engine, user: TestUser) -> Iterator[sa.Connection]:
    """One transaction running as `user` (RLS applies); always rolled back on exit."""
    with engine.connect() as conn:
        conn.begin()
        act_as(conn, claims_for(user))
        yield conn
        # Leaving engine.connect() without a commit rolls the transaction back.


@pytest.fixture
def people(engine) -> Iterator[dict[str, TestUser]]:
    users = {u.key: u for u in (GAL, DANA, NOA, RON)}
    with engine.begin() as conn:  # as postgres: no RLS
        conn.execute(_DELETE_TEST_USERS)
        for u in users.values():
            conn.execute(
                sa.text(
                    "INSERT INTO auth.users (id, email, aud, role)"
                    " VALUES (:id, :email, 'authenticated', 'authenticated')"
                ),
                {"id": u.id, "email": u.email},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO app.profiles (id, username, display_name)"
                    " VALUES (:id, :username, :display_name)"
                ),
                {"id": u.id, "username": u.username, "display_name": _DISPLAY_NAMES[u.key]},
            )
            conn.execute(
                sa.text("INSERT INTO app.profile_details (user_id, bio) VALUES (:id, :bio)"),
                {"id": u.id, "bio": GAL_BIO if u is GAL else None},
            )
            conn.execute(
                sa.text("INSERT INTO app.user_settings (user_id) VALUES (:id)"), {"id": u.id}
            )
        follow = sa.text("INSERT INTO app.follows (follower_id, followee_id) VALUES (:a, :b)")
        conn.execute(follow, {"a": DANA.id, "b": GAL.id})
        conn.execute(follow, {"a": RON.id, "b": GAL.id})
        # Insert then update (not insert 'accepted'), so the follows triggers run as in real use.
        conn.execute(
            sa.text(
                "UPDATE app.follows SET status = 'accepted'"
                " WHERE follower_id = :a AND followee_id = :b"
            ),
            {"a": DANA.id, "b": GAL.id},
        )
    yield users
    with engine.begin() as conn:
        conn.execute(_DELETE_TEST_USERS)  # cascades to profiles, follows, notifications
