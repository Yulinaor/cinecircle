"""Read the FAKE rows back out of the local database, for the notebooks (plan P14).

Every reader keeps only rows whose user is a fake user (`email LIKE '%@fake.cinecircle.local'`)
and whose title is a fake title (`tmdb_id >= FAKE_TMDB_BASE`), so real local accounts never reach
an analysis (analysing real users needs a privacy policy first). They read as the connecting
role (the same as the loader), so no row-level security is involved, and refuse a database that
is not on this machine before connecting. Rows are plain dicts (no pandas in the package; the
notebooks wrap them) keyed by the `Dataset` index conventions: a user is `n` (from 1), a title is
`i` (from 0), a post is `(author n, title i)`.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine

from cinecircle_analysis.fakedata import (
    FAKE_DOMAIN,
    FAKE_TMDB_BASE,
    Dataset,
    FakeEvent,
    FakeFollow,
    FakePost,
    FakeTitle,
    FakeUser,
    FakeWish,
)
from cinecircle_analysis.load import assert_local

# The fake users (their number comes from the address, `fake07@...` is user 7) and fake titles
# (their index is the offset from the base id), as CTEs every query starts with.
_FAKE = (
    "WITH fu AS ("
    " SELECT id, CAST(substring(email from '^fake([0-9]+)@') AS integer) AS n"
    " FROM auth.users WHERE email LIKE :pattern),"
    " ft AS ("
    " SELECT id, CAST(tmdb_id - :base AS integer) AS i"
    " FROM app.titles WHERE tmdb_id >= :base) "
)

_USERS = sa.text(
    _FAKE + "SELECT fu.n, u.id, u.email, p.username, p.display_name, p.created_at AS signed_up,"
    " COALESCE((SELECT array_agg(g.genre_id ORDER BY g.genre_id)"
    "           FROM app.user_genre_prefs g WHERE g.user_id = fu.id), '{}') AS picks"
    " FROM fu JOIN auth.users u ON u.id = fu.id JOIN app.profiles p ON p.id = fu.id"
    " ORDER BY fu.n"
)
_TITLES = sa.text(
    _FAKE + "SELECT ft.i, t.tmdb_id, t.media_type, t.name_en, t.name_he, t.year_start AS year,"
    " COALESCE((SELECT array_agg(tg.genre_id ORDER BY tg.genre_id)"
    "           FROM app.title_genres tg WHERE tg.title_id = t.id), '{}') AS genre_ids,"
    " t.imdb_rating, t.tmdb_rating"
    " FROM ft JOIN app.titles t ON t.id = ft.id ORDER BY ft.i"
)
_POSTS = sa.text(
    _FAKE + "SELECT fu.n AS author, ft.i AS title, p.rating, p.is_shared, p.created_at"
    " FROM app.posts p JOIN fu ON fu.id = p.author_id JOIN ft ON ft.id = p.title_id"
    " WHERE p.season_number = 0 ORDER BY p.created_at, fu.n, ft.i"
)
_FOLLOWS = sa.text(
    _FAKE + "SELECT a.n AS follower, b.n AS followee, f.status, f.created_at, f.responded_at"
    " FROM app.follows f JOIN fu a ON a.id = f.follower_id JOIN fu b ON b.id = f.followee_id"
    " ORDER BY f.created_at, a.n, b.n"
)
_WISHLIST = sa.text(
    _FAKE + "SELECT fu.n AS owner, ft.i AS title, w.source, w.status, w.fit_at_save, w.added_at,"
    " w.watched_at, sa.n AS source_author, st.i AS source_title"
    " FROM app.wishlist_items w JOIN fu ON fu.id = w.owner_id JOIN ft ON ft.id = w.title_id"
    " LEFT JOIN app.posts sp ON sp.id = w.source_post_id"
    " LEFT JOIN fu sa ON sa.id = sp.author_id LEFT JOIN ft st ON st.id = sp.title_id"
    " WHERE w.source_post_id IS NULL OR (sa.id IS NOT NULL AND st.id IS NOT NULL)"
    " ORDER BY w.added_at, fu.n, ft.i"
)
_EVENTS = sa.text(
    _FAKE + 'SELECT fu.n AS "user", e.event_type, ft.i AS title, pa.n AS post_author,'
    " pt.i AS post_title, e.props, e.created_at"
    " FROM app.events e JOIN fu ON fu.id = e.user_id"
    " LEFT JOIN ft ON ft.id = e.title_id"
    " LEFT JOIN app.posts p ON p.id = e.post_id"
    " LEFT JOIN fu pa ON pa.id = p.author_id LEFT JOIN ft pt ON pt.id = p.title_id"
    " WHERE (e.title_id IS NULL OR ft.id IS NOT NULL)"
    "   AND (e.post_id IS NULL OR (pa.id IS NOT NULL AND pt.id IS NOT NULL))"
    " ORDER BY e.created_at, e.id"
)


def _read(engine: Engine, query: sa.TextClause) -> list[dict[str, Any]]:
    assert_local(engine)
    params = {"pattern": f"%@{FAKE_DOMAIN}", "base": FAKE_TMDB_BASE}
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(query, params).mappings()]
    for row in rows:
        for key, value in row.items():
            if isinstance(value, Decimal):
                row[key] = float(value)
    return rows


def users(engine: Engine) -> list[dict[str, Any]]:
    """n, id, email, username, display_name, signed_up, picks (onboarding genre ids)."""
    return _read(engine, _USERS)


def titles(engine: Engine) -> list[dict[str, Any]]:
    """i, tmdb_id, media_type, name_en, name_he, year, genre_ids, imdb_rating, tmdb_rating."""
    return _read(engine, _TITLES)


def posts(engine: Engine) -> list[dict[str, Any]]:
    """author, title, rating, is_shared, created_at (whole-title ratings, in time order)."""
    return _read(engine, _POSTS)


def follows(engine: Engine) -> list[dict[str, Any]]:
    """follower, followee, status, created_at, responded_at (both ends are fake users)."""
    return _read(engine, _FOLLOWS)


def wishlist(engine: Engine) -> list[dict[str, Any]]:
    """owner, title, source, status, fit_at_save, added_at, watched_at, source_author and
    source_title (the post it was saved from, else None)."""
    return _read(engine, _WISHLIST)


def events(engine: Engine) -> list[dict[str, Any]]:
    """user, event_type, title, post_author, post_title, props, created_at."""
    return _read(engine, _EVENTS)


def _pair(author: int | None, title: int | None) -> tuple[int, int] | None:
    return (author, title) if author is not None and title is not None else None


def dataset_from_db(engine: Engine) -> Dataset:
    """The fake rows in the database as the same `Dataset` the generator makes, so `replay`
    judges exactly what is stored. `FakeUser.cluster` is the generator's hidden state and is not
    stored: it reads -1 here."""
    return Dataset(
        users=tuple(
            FakeUser(
                n=u["n"],
                id=u["id"],
                email=u["email"],
                username=u["username"],
                display_name=u["display_name"],
                cluster=-1,
                signed_up=u["signed_up"],
                picks=tuple(u["picks"]),
            )
            for u in users(engine)
        ),
        titles=tuple(
            FakeTitle(
                i=t["i"],
                tmdb_id=t["tmdb_id"],
                media_type=t["media_type"],
                name_en=t["name_en"],
                name_he=t["name_he"],
                year=t["year"],
                genre_ids=tuple(t["genre_ids"]),
                imdb_rating=t["imdb_rating"],
                tmdb_rating=t["tmdb_rating"],
            )
            for t in titles(engine)
        ),
        follows=tuple(
            FakeFollow(
                f["follower"], f["followee"], f["status"], f["created_at"], f["responded_at"]
            )
            for f in follows(engine)
        ),
        posts=tuple(
            FakePost(p["author"], p["title"], p["rating"], p["is_shared"], p["created_at"])
            for p in posts(engine)
        ),
        wishes=tuple(
            FakeWish(
                owner=w["owner"],
                title=w["title"],
                source=w["source"],
                source_post=_pair(w["source_author"], w["source_title"]),
                status=w["status"],
                fit_at_save=w["fit_at_save"],
                added_at=w["added_at"],
                watched_at=w["watched_at"],
            )
            for w in wishlist(engine)
        ),
        events=tuple(
            FakeEvent(
                user=e["user"],
                event_type=e["event_type"],
                title=e["title"],
                post=_pair(e["post_author"], e["post_title"]),
                props=_props(e["props"]),
                created_at=e["created_at"],
            )
            for e in events(engine)
        ),
    )


def _props(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value else {}
