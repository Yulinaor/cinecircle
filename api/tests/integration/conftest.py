import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from cinecircle_api.catalog.service import TitleService
from cinecircle_api.db import act_as, make_engine
from cinecircle_api.main import create_app
from tests.fakes import FakeOmdb, FakeTmdb
from tests.tokens import auth_settings, make_token

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
GAL_SHARED_OPINION = "gal-shared-opinion-sentinel"
GAL_PRIVATE_OPINION = "gal-private-opinion-sentinel"
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


# ===== HTTP clients (the real app on the real DB, one signed-in user each) =====

_FRESH_NAMESPACE = UUID("00000000-0000-4000-8000-00000000f000")
_INSERT_FRESH_USER = sa.text(
    "INSERT INTO auth.users (id, email, aud, role)"
    " VALUES (:id, :email, 'authenticated', 'authenticated') ON CONFLICT DO NOTHING"
)


@pytest.fixture
def api(people, engine) -> Iterator[Callable[..., TestClient]]:
    """`api("noa")` is a client signed in as that person; extra keyword arguments become
    token claims (e.g. `user_metadata=...`). A key starting with "fresh" is a signed-in user
    who has no profile yet (an auth.users row is created for them; `people` cleans it up)."""
    apps = []

    def client_for(key: str, **claims: Any) -> TestClient:
        if key in people:
            user_id, email = people[key].id, people[key].email
        else:
            assert key.startswith("fresh"), key
            user_id, email = uuid5(_FRESH_NAMESPACE, key), f"{key}@{TEST_EMAIL_DOMAIN}"
            with engine.begin() as conn:
                conn.execute(_INSERT_FRESH_USER, {"id": user_id, "email": email})
        app = create_app(auth_settings(URL))
        app.state.title_service = TitleService(app.state.engine, FakeTmdb(), FakeOmdb())
        apps.append(app)
        token = make_token(str(user_id), **{"email": email, **claims})
        return TestClient(app, headers={"Authorization": f"Bearer {token}"})

    yield client_for
    for app in apps:
        app.state.engine.dispose()


# ===== Catalogue helpers =====


def insert_series(conn: sa.Connection, tmdb_id: int, seasons: tuple[int, ...]) -> int:
    """A cached series with the given season numbers, inserted as postgres (no RLS)."""
    title_id = conn.scalar(
        sa.text(
            "INSERT INTO app.titles (tmdb_id, media_type, name_en, season_count, raw_tmdb)"
            " VALUES (:tmdb_id, 'series', :name, :count, '{}') RETURNING id"
        ),
        {"tmdb_id": tmdb_id, "name": f"Series {tmdb_id}", "count": len(seasons)},
    )
    for number in seasons:
        conn.execute(
            sa.text(
                "INSERT INTO app.title_seasons (title_id, season_number) VALUES (:title, :number)"
            ),
            {"title": title_id, "number": number},
        )
    return title_id


# ===== Gal's content (shared post, private rating, wishlist, genre pref, event) =====


@dataclass(frozen=True)
class GalContent:
    shared_post_id: int
    private_post_id: int
    title_ids: tuple[int, int]


_INSERT_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
    " VALUES (:tmdb_id, 'movie', :name, '{}') RETURNING id"
)
_INSERT_POST = sa.text(
    "INSERT INTO app.posts (author_id, title_id, rating, opinion, is_shared)"
    " VALUES (:author, :title, :rating, :opinion, :shared) RETURNING id"
)


@pytest.fixture
def gal_content(people, clean_catalog, engine) -> GalContent:
    """Rows owned by Gal, inserted as postgres (no RLS). `people` cleanup cascades to them."""
    with engine.begin() as conn:
        first, second = (
            conn.scalar(_INSERT_TITLE, {"tmdb_id": n, "name": f"Title {n}"}) for n in (1, 2)
        )
        shared = conn.scalar(
            _INSERT_POST,
            {
                "author": GAL.id,
                "title": first,
                "rating": 9.0,
                "opinion": GAL_SHARED_OPINION,
                "shared": True,
            },
        )
        private = conn.scalar(
            _INSERT_POST,
            {
                "author": GAL.id,
                "title": second,
                "rating": 4.5,
                "opinion": GAL_PRIVATE_OPINION,
                "shared": False,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO app.wishlist_items (owner_id, title_id, source)"
                " VALUES (:gal, :title, 'discover')"
            ),
            {"gal": GAL.id, "title": second},
        )
        conn.execute(sa.text("INSERT INTO app.genres (id, name_en) VALUES (28, 'Action')"))
        conn.execute(
            sa.text("INSERT INTO app.user_genre_prefs (user_id, genre_id) VALUES (:gal, 28)"),
            {"gal": GAL.id},
        )
        conn.execute(
            sa.text("INSERT INTO app.events (user_id, event_type) VALUES (:gal, 'post_created')"),
            {"gal": GAL.id},
        )
        # Gal follows Noa (accepted): gives Gal a "following" list. Insert then update, so the
        # follows triggers run as in real use. Noa follows nobody, so she gains no access to Gal.
        pair = {"gal": GAL.id, "noa": NOA.id}
        conn.execute(
            sa.text("INSERT INTO app.follows (follower_id, followee_id) VALUES (:gal, :noa)"), pair
        )
        conn.execute(
            sa.text(
                "UPDATE app.follows SET status = 'accepted'"
                " WHERE follower_id = :gal AND followee_id = :noa"
            ),
            pair,
        )
    return GalContent(shared_post_id=shared, private_post_id=private, title_ids=(first, second))
