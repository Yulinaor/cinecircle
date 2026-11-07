"""The fake-only readers (plan P14) and the replay against the database (spec 03 section 7): the
notebooks read only fake rows, and what they evaluate is what the app would have computed."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa

from cinecircle_analysis import frames
from cinecircle_analysis.fakedata import FAKE_DOMAIN, FAKE_TMDB_BASE, Dataset, generate
from cinecircle_analysis.load import NotLocal, load, wipe
from cinecircle_analysis.replay import Prediction, profile_from, title_score
from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.db import make_engine
from cinecircle_api.taste import score
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.taste.repository import load_profile
from tests.integration.conftest import GAL, TestUser, as_user, insert_post

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def small() -> Dataset:
    return generate(1, users=8, titles=30, ratings=150)


@pytest.fixture
def loaded(engine, small, people, clean_catalog) -> Iterator[Dataset]:
    """The small fake dataset in the database for one test (after `people` and `clean_catalog`,
    whose truncation would otherwise cascade into it), gone again afterwards."""
    load(engine, small)
    try:
        yield small
    finally:
        with engine.begin() as conn:  # a real account's rows on fake titles block the wipe
            for table in ("posts", "wishlist_items"):
                conn.execute(
                    sa.text(
                        f"DELETE FROM app.{table} WHERE title_id IN"
                        " (SELECT id FROM app.titles WHERE tmdb_id >= :base)"
                    ),
                    {"base": FAKE_TMDB_BASE},
                )
        wipe(engine)


def _real_rows_next_to_fake_ones(engine) -> int:
    """GAL (a real local account) and a real title, entangled with the fake data in every table
    `frames` reads. Returns the real title's id."""
    with engine.begin() as conn:
        real = conn.scalar(
            sa.text(
                "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
                " VALUES (7, 'movie', 'Real', 8.0, '{}') RETURNING id"
            )
        )
        fake_title = conn.scalar(
            sa.text("SELECT id FROM app.titles WHERE tmdb_id = :base"), {"base": FAKE_TMDB_BASE}
        )
        fake_user = conn.scalar(
            sa.text("SELECT id FROM auth.users WHERE email = :e"), {"e": f"fake01@{FAKE_DOMAIN}"}
        )
        insert_post(conn, GAL, real, 8.0, True)
        insert_post(conn, GAL, fake_title, 7.0, True)
        insert_post(conn, SimpleNamespace(id=fake_user), real, 9.0, True)
        follow = sa.text("INSERT INTO app.follows (follower_id, followee_id) VALUES (:a, :b)")
        conn.execute(follow, {"a": GAL.id, "b": fake_user})
        conn.execute(follow, {"a": fake_user, "b": GAL.id})
        wish = sa.text(
            "INSERT INTO app.wishlist_items (owner_id, title_id, source) VALUES (:o, :t, 'search')"
        )
        conn.execute(wish, {"o": GAL.id, "t": real})
        conn.execute(wish, {"o": GAL.id, "t": fake_title})
        conn.execute(wish, {"o": fake_user, "t": real})
        event = sa.text(
            "INSERT INTO app.events (user_id, event_type, title_id, props)"
            ' VALUES (:u, \'post_viewed\', :t, \'{"fit": 50, "surface": "home"}\')'
        )
        conn.execute(event, {"u": GAL.id, "t": fake_title})
        conn.execute(event, {"u": fake_user, "t": real})
    return real


def _fake_wish_from_a_real_post(engine) -> tuple[Any, int]:
    """A fake user's wish on a fake title whose source post is GAL's (a real account): the post
    is on the same title, as the wishlist trigger demands. Needs `_real_rows_next_to_fake_ones`
    first (GAL's post on the first fake title). Returns the new wish's (owner id, title id)."""
    with engine.begin() as conn:
        fake_title = conn.scalar(
            sa.text("SELECT id FROM app.titles WHERE tmdb_id = :base"), {"base": FAKE_TMDB_BASE}
        )
        row = conn.execute(
            sa.text(
                "SELECT u.id AS owner, p.id AS post FROM auth.users u, app.posts p"
                " WHERE u.email LIKE :pattern AND p.author_id = :gal AND p.title_id = :title"
                "   AND NOT EXISTS (SELECT 1 FROM app.wishlist_items w"
                "                   WHERE w.owner_id = u.id AND w.title_id = :title)"
                " ORDER BY u.email LIMIT 1"
            ),
            {"pattern": f"%@{FAKE_DOMAIN}", "gal": GAL.id, "title": fake_title},
        ).one()
        conn.execute(
            sa.text(
                "INSERT INTO app.wishlist_items (owner_id, title_id, source, source_post_id)"
                " VALUES (:owner, :title, 'post', :post)"
            ),
            {"owner": row.owner, "title": fake_title, "post": row.post},
        )
        return row.owner, fake_title


def test_frames_read_fake_users_only(engine, loaded):
    _real_rows_next_to_fake_ones(engine)
    stray_wish = _fake_wish_from_a_real_post(engine)
    ds = loaded

    users = frames.users(engine)
    assert len(users) == len(ds.users)
    assert all(u["email"].endswith(f"@{FAKE_DOMAIN}") for u in users)
    assert GAL.email not in {u["email"] for u in users}

    titles = frames.titles(engine)
    assert len(titles) == len(ds.titles)
    assert all(t["tmdb_id"] >= FAKE_TMDB_BASE for t in titles)
    assert sorted(titles[0]["genre_ids"]) == list(ds.titles[0].genre_ids)

    posts = frames.posts(engine)
    assert len(posts) == len(ds.posts)  # not GAL's two, nor the fake user's post on a real title
    assert all(p["author"] >= 1 and p["title"] >= 0 for p in posts)

    assert len(frames.follows(engine)) == len(ds.follows)  # not the two that involve GAL
    assert len(frames.wishlist(engine)) == len(ds.wishes)  # not the wish sourced from GAL's post
    with engine.connect() as conn:  # the stray wish is really there, only the reader skips it
        assert (
            conn.scalar(
                sa.text(
                    "SELECT count(*) FROM app.wishlist_items WHERE owner_id = :o AND title_id = :t"
                ),
                {"o": stray_wish[0], "t": stray_wish[1]},
            )
            == 1
        )
    assert len(frames.events(engine)) == len(ds.events)

    rebuilt = frames.dataset_from_db(engine)
    assert rebuilt.posts == ds.posts
    assert rebuilt.follows == ds.follows
    assert rebuilt.titles == ds.titles
    assert rebuilt.wishes == ds.wishes
    assert [
        (u.n, u.id, u.email, u.username, u.display_name, u.signed_up, u.picks)
        for u in rebuilt.users
    ] == [(u.n, u.id, u.email, u.username, u.display_name, u.signed_up, u.picks) for u in ds.users]

    def key(e):
        return (e.created_at, e.user, e.event_type, e.title or -1, repr(sorted(e.props.items())))

    assert sorted(rebuilt.events, key=key) == sorted(ds.events, key=key)


def test_frames_refuse_a_remote_database():
    remote = make_engine("postgresql+psycopg://postgres:x@db.example.com:5432/postgres")
    for read in (
        frames.users,
        frames.titles,
        frames.posts,
        frames.follows,
        frames.wishlist,
        frames.events,
        frames.dataset_from_db,
    ):
        with pytest.raises(NotLocal):
            read(remote)


def test_replay_matches_the_app(engine, loaded):
    """A fake user's profile rebuilt from their whole history equals `load_profile` run as that
    user, and a replayed title fit equals the app's Discover fit for the same title."""
    ds = frames.dataset_from_db(engine)
    genres = {t.i: t.genre_ids for t in ds.titles}
    by_title = {t.i: t for t in ds.titles}
    counts = {u.n: sum(p.author == u.n for p in ds.posts) for u in ds.users}
    chosen = sorted(ds.users, key=lambda u: -counts[u.n])[:3]
    assert all(counts[u.n] >= score.FULL_AFTER for u in chosen)
    assert any(u.picks for u in chosen)

    for user in chosen:
        mine = [(p.title, p.rating) for p in ds.posts if p.author == user.n]
        replayed = profile_from(mine, genres, user.picks)
        as_db = TestUser(user.username, user.id, user.username, user.email)
        with as_user(engine, as_db) as conn:
            actual = load_profile(conn)
            assert replayed.rated == actual.rated
            assert replayed.mean_all == pytest.approx(actual.mean_all, abs=1e-9)
            assert replayed.picked == actual.picked
            assert replayed.state == actual.state
            assert set(replayed.genres) == set(actual.genres)
            for genre, stat in actual.genres.items():
                assert replayed.genres[genre].n == stat.n
                assert replayed.genres[genre].mean == pytest.approx(stat.mean, abs=1e-9)

            rated = {t for t, _ in mine}
            title = next(t for t in ds.titles if t.i not in rated)
            rows = conn.execute(
                sa.text(
                    "SELECT g.id, g.name_en, g.name_he FROM app.title_genres tg"
                    " JOIN app.genres g ON g.id = tg.genre_id"
                    " JOIN app.titles t ON t.id = tg.title_id WHERE t.tmdb_id = :tmdb"
                ),
                {"tmdb": title.tmdb_id},
            ).all()
            taste = TasteContext(conn, actual).for_title(
                [GenreRow(*row) for row in rows], title.imdb_rating, title.tmdb_rating, "en"
            )
        prediction = Prediction(
            user=user.n,
            title=title.i,
            at=ds.posts[-1].created_at,
            actual=0.0,
            imdb=by_title[title.i].imdb_rating,
            g=score.genre_fit(replayed, title.genre_ids),
            q=score.quality(title.imdb_rating, title.tmdb_rating),
            s=None,
            state=replayed.state,
        )
        assert taste is not None
        assert score.round_half_up(title_score(prediction)) == taste.fit
