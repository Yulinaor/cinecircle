import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from cinecircle_analysis import load as fake_load
from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.catalog.service import TitleService
from cinecircle_api.db import act_as, make_engine
from cinecircle_api.discover.service import DiscoverService
from cinecircle_api.main import create_app
from tests.fakes import FakeOmdb, FakeTmdb
from tests.tokens import auth_settings, make_token

URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:55322/postgres"
)
_TRUNCATE = sa.text(
    "TRUNCATE app.title_genres, app.title_seasons, app.titles, app.genres, app.discover_cache"
    " RESTART IDENTITY CASCADE"  # external_reviews goes with titles
)


@pytest.fixture(scope="session")
def engine() -> sa.Engine:
    return make_engine(URL)


@pytest.fixture(scope="session", autouse=True)
def _no_fake_data(engine) -> None:
    """Fake rows (`npm run fake:load`) would break "count every profile" tests, and the catalogue
    truncation below cascades into them anyway: start the session without them (plan P9)."""
    fake_load.wipe(engine)


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
        tmdb = FakeTmdb()
        app.state.title_service = TitleService(app.state.engine, tmdb, FakeOmdb())
        app.state.discover_service = DiscoverService(
            app.state.engine, tmdb, app.state.title_service
        )
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
        conn.execute(
            sa.text(
                "INSERT INTO app.external_reviews"
                " (title_id, source_review_id, author_name, excerpt, url)"
                " VALUES (:title, 'r1', 'jdoe', 'Fine.', 'https://www.themoviedb.org/review/r1')"
            ),
            {"title": first},
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


GAL_WISHLIST_TITLE = "gal-wishlist-title-sentinel"


@pytest.fixture
def gal_wish(gal_content, engine) -> int:
    """A third cached movie on Gal's wishlist (source `search`), inserted as postgres. No post
    mentions it, so only Gal's own wishlist can ever show its name. Returns its title id."""
    with engine.begin() as conn:
        title_id = conn.scalar(_INSERT_TITLE, {"tmdb_id": 3, "name": GAL_WISHLIST_TITLE})
        conn.execute(
            sa.text(
                "INSERT INTO app.wishlist_items (owner_id, title_id, source)"
                " VALUES (:gal, :title, 'search')"
            ),
            {"gal": GAL.id, "title": title_id},
        )
    return title_id


# ===== The spec 03 section 4 dataset (Taste Match) =====
# Dana has 20 rated titles (mean exactly 0.70, no picks), all private. Gal (whom Dana follows)
# shares 6.5 on each of Dana's eight Comedy titles C1-C8 (gap 1.5) and 9.0 on *The Odyssey*;
# his 1.0 on A1 is private. Severance is a series Dana has not rated.

ACTION, ADVENTURE, DRAMA, MYSTERY, SCIFI, COMEDY = 28, 12, 18, 9648, 878, 35
_SPEC_GENRES = (
    (ACTION, "Action", "אקשן"),
    (ADVENTURE, "Adventure", "הרפתקאות"),
    (DRAMA, "Drama", None),
    (MYSTERY, "Mystery", None),
    (SCIFI, "Science Fiction", None),
    (COMEDY, "Comedy", None),
)
SEVERANCE_GENRES = (
    GenreRow(DRAMA, "Drama", None),
    GenreRow(MYSTERY, "Mystery", None),
    GenreRow(SCIFI, "Science Fiction", "מדע בדיוני"),
)

INSERT_GENRE = sa.text("INSERT INTO app.genres (id, name_en, name_he) VALUES (:id, :en, :he)")
_INSERT_SPEC_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
    " VALUES (:tmdb_id, :media_type, :name, :imdb, '{}') RETURNING id"
)
INSERT_TITLE_GENRE = sa.text(
    "INSERT INTO app.title_genres (title_id, genre_id) VALUES (:title, :genre)"
)
_INSERT_SPEC_POST = sa.text(
    "INSERT INTO app.posts (author_id, title_id, season_number, rating, is_shared)"
    " VALUES (:author, :title, :season, :rating, :shared) RETURNING id"
)


@dataclass(frozen=True)
class SpecIds:
    odyssey_post_id: int
    odyssey_title_id: int
    severance_title_id: int
    dana_post_id: int  # Dana's own post on C9
    comedy_title_ids: tuple[int, ...]  # C1-C8 (Dana 5.0, Gal shared 6.5)
    c9_title_id: int


def insert_post(conn, author, title, rating, shared, season=0) -> int:
    return conn.scalar(
        _INSERT_SPEC_POST,
        {
            "author": author.id,
            "title": title,
            "season": season,
            "rating": rating,
            "shared": shared,
        },
    )


def _spec_title(conn, tmdb_id, name, genres, imdb=None, media_type="movie") -> int:
    title_id = conn.scalar(
        _INSERT_SPEC_TITLE,
        {"tmdb_id": tmdb_id, "media_type": media_type, "name": name, "imdb": imdb},
    )
    for genre in genres:
        conn.execute(INSERT_TITLE_GENRE, {"title": title_id, "genre": genre})
    return title_id


def spec_dataset(engine, people) -> SpecIds:
    """03 section 4, built as postgres (no RLS). `people` cleanup removes the posts; the
    `clean_catalog` fixture removes the titles."""
    n = iter(range(1000, 2000))
    with engine.begin() as conn:
        for genre_id, name_en, name_he in _SPEC_GENRES:
            conn.execute(INSERT_GENRE, {"id": genre_id, "en": name_en, "he": name_he})

        def dana(name, genres, rating):
            title = _spec_title(conn, next(n), name, genres)
            return title, insert_post(conn, DANA, title, rating, False)

        a1, _ = dana("A1", [ACTION], 10)
        dana("A2", [ACTION], 10)
        dana("B1", [ADVENTURE], 9)
        dana("B2", [ADVENTURE], 9)
        for i in range(1, 5):
            dana(f"D{i}", [DRAMA], 7)
        dana("M1", [MYSTERY], 9)
        dana("S1", [SCIFI], 9.5)
        dana("S2", [SCIFI], 9.5)
        comedies = []
        for i in range(1, 9):
            title, _ = dana(f"C{i}", [COMEDY], 5)
            insert_post(conn, GAL, title, 6.5, True)
            comedies.append(title)
        c9, dana_post = dana("C9", [COMEDY], 6)
        insert_post(conn, GAL, a1, 1.0, False)  # private: must be ignored

        odyssey = _spec_title(conn, next(n), "The Odyssey", [ACTION, ADVENTURE, DRAMA], imdb=8.5)
        odyssey_post = insert_post(conn, GAL, odyssey, 9.0, True)
        severance = _spec_title(
            conn,
            next(n),
            "Severance",
            [DRAMA, MYSTERY, SCIFI],
            imdb=8.7,
            media_type="series",
        )
    return SpecIds(
        odyssey_post_id=odyssey_post,
        odyssey_title_id=odyssey,
        severance_title_id=severance,
        dana_post_id=dana_post,
        comedy_title_ids=tuple(comedies),
        c9_title_id=c9,
    )


@pytest.fixture
def spec(people, clean_catalog, engine) -> SpecIds:
    return spec_dataset(engine, people)
