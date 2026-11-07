"""The fake-data loader on the local database (plan P7-P9): it writes as postgres, keeps the
generated timestamps, makes no notifications, and wipes nothing but fake rows."""

import pytest
import sqlalchemy as sa

from cinecircle_analysis.fakedata import FAKE_DOMAIN, FAKE_TMDB_BASE, GENRES, generate
from cinecircle_analysis.load import load, wipe
from tests.integration.conftest import GAL, insert_post

pytestmark = pytest.mark.integration

FAKE_USERS = f"(SELECT id FROM auth.users WHERE email LIKE '%@{FAKE_DOMAIN}')"


def _count(engine, sql: str, **params) -> int:
    with engine.connect() as conn:
        return conn.scalar(sa.text(sql), params)


def _fake_counts(engine) -> dict[str, int]:
    return {
        "profiles": _count(engine, f"SELECT count(*) FROM app.profiles WHERE id IN {FAKE_USERS}"),
        "titles": _count(
            engine, "SELECT count(*) FROM app.titles WHERE tmdb_id >= :base", base=FAKE_TMDB_BASE
        ),
        "follows": _count(
            engine, f"SELECT count(*) FROM app.follows WHERE follower_id IN {FAKE_USERS}"
        ),
        "posts": _count(engine, f"SELECT count(*) FROM app.posts WHERE author_id IN {FAKE_USERS}"),
        "wishlist_items": _count(
            engine, f"SELECT count(*) FROM app.wishlist_items WHERE owner_id IN {FAKE_USERS}"
        ),
        "events": _count(engine, f"SELECT count(*) FROM app.events WHERE user_id IN {FAKE_USERS}"),
    }


@pytest.fixture(scope="module")
def small():
    return generate(1, users=8, titles=30, ratings=150)


def test_conftest_wipes_fake_data(engine):
    """The session fixture ran: no fake users at test start (plan P9)."""
    assert (
        _count(engine, f"SELECT count(*) FROM auth.users WHERE email LIKE '%@{FAKE_DOMAIN}'") == 0
    )


def test_load_small_dataset(engine, small):
    counts = load(engine, small)
    try:
        expected = {
            "profiles": len(small.users),
            "titles": len(small.titles),
            "follows": len(small.follows),
            "posts": len(small.posts),
            "wishlist_items": len(small.wishes),
            "events": len(small.events),
        }
        assert _fake_counts(engine) == expected
        assert {k: counts[k] for k in expected} == expected
        assert counts["user_genre_prefs"] == sum(len(u.picks) for u in small.users)

        # Historical timestamps survive (the watched_at trigger would stamp now()).
        watched = [w for w in small.wishes if w.status == "watched"]
        assert watched
        with engine.connect() as conn:
            stamped = conn.execute(
                sa.text(
                    "SELECT count(*) FROM app.wishlist_items w"
                    " JOIN app.posts p ON p.author_id = w.owner_id AND p.title_id = w.title_id"
                    f" WHERE w.owner_id IN {FAKE_USERS}"
                    "   AND w.status = 'watched' AND w.watched_at = p.created_at"
                )
            ).scalar()
            first = min(small.posts, key=lambda p: p.created_at)
            created = conn.scalar(
                sa.text(f"SELECT min(created_at) FROM app.posts WHERE author_id IN {FAKE_USERS}")
            )
            # No notification triggers fired for the follows.
            notifications = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM app.notifications"
                    f" WHERE recipient_id IN {FAKE_USERS} OR actor_id IN {FAKE_USERS}"
                )
            )
            # Every wishlist source post and every event post exists.
            orphans = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM app.wishlist_items w WHERE w.source = 'post'"
                    f" AND w.owner_id IN {FAKE_USERS}"
                    " AND NOT EXISTS (SELECT 1 FROM app.posts p WHERE p.id = w.source_post_id)"
                )
            )
            genres = conn.scalar(sa.text("SELECT count(*) FROM app.genres"))
            shapes = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM app.events"
                    f" WHERE user_id IN {FAKE_USERS} AND event_type = 'post_viewed'"
                    "  AND (props->>'fit') IS NOT NULL AND props->>'surface' = 'home'"
                )
            )
        assert stamped == len(watched)
        assert created == first.created_at
        assert notifications == 0
        assert orphans == 0
        assert genres >= len(GENRES)
        assert shapes == sum(e.event_type == "post_viewed" for e in small.events)

        # Idempotent: loading again leaves the same rows.
        again = load(engine, small)
        assert again == counts
        assert _fake_counts(engine) == expected
    finally:
        wipe(engine)


def test_wipe_removes_only_fake_rows(engine, people, clean_catalog, small):
    with engine.begin() as conn:
        title = conn.scalar(
            sa.text(
                "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                " VALUES (7, 'movie', 'Real', '{}') RETURNING id"
            )
        )
        insert_post(conn, GAL, title, 8.0, True)
    load(engine, small)
    assert _fake_counts(engine)["posts"] == len(small.posts)
    wipe(engine)
    assert _fake_counts(engine) == dict.fromkeys(_fake_counts(engine), 0)
    assert _count(engine, "SELECT count(*) FROM app.posts WHERE author_id = :g", g=GAL.id) == 1
    assert _count(engine, "SELECT count(*) FROM app.titles WHERE tmdb_id = 7") == 1
    assert _count(engine, "SELECT count(*) FROM app.genres WHERE id = 28") == 1
    assert _count(engine, "SELECT count(*) FROM app.profiles WHERE id = :g", g=GAL.id) == 1
