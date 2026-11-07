"""Taste Match from real SQL, as the viewer (RLS applies): spec 03 section 4 reproduced end to end,
and the privacy rules of section 1.3 (plan P5): a private rating never moves anyone's score.

The dataset is the one of 03 section 4. Dana has 20 rated titles (mean exactly 0.70, no picks),
all private. Gal (whom Dana follows) shares 6.5 on each of Dana's eight Comedy titles C1-C8
(gap 1.5) and 9.0 on *The Odyssey*; his 1.0 on A1 is private.
"""

import pytest
import sqlalchemy as sa

from cinecircle_api.posts.repository import get_post
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.taste.models import Taste
from cinecircle_api.taste.repository import load_agreements, load_profile, title_inputs
from cinecircle_api.taste.score import GenreStat
from tests.integration.conftest import (
    ACTION,
    COMEDY,
    DANA,
    DRAMA,
    GAL,
    INSERT_GENRE,
    INSERT_TITLE_GENRE,
    MYSTERY,
    NOA,
    RON,
    SCIFI,
    SEVERANCE_GENRES,
    as_user,
    insert_post,
    insert_series,
)

pytestmark = pytest.mark.integration


def test_feed_example_end_to_end(spec, engine):
    with as_user(engine, DANA) as conn:
        ctx = TasteContext.load(conn)
        row = get_post(conn, spec.odyssey_post_id)
        assert ctx.unlocked
        assert ctx.for_post(row, "en") == Taste(
            fit=76, genres=["Action", "Adventure"], agreement=74
        )
        assert ctx.for_post(row, "he") == Taste(fit=76, genres=["אקשן", "הרפתקאות"], agreement=74)


def test_profile_matches_the_spec_affinities(spec, engine):
    with as_user(engine, DANA) as conn:
        profile = load_profile(conn)
    assert profile.rated == 20
    assert profile.mean_all == pytest.approx(0.70)
    assert profile.picked == frozenset()
    assert profile.state == "full"
    assert profile.genres[ACTION] == GenreStat(n=2, mean=pytest.approx(1.0))
    assert profile.genres[COMEDY].n == 9


def test_title_example_end_to_end(spec, engine):
    with as_user(engine, DANA) as conn:
        ctx = TasteContext.load(conn)
        stored = title_inputs(conn, spec.severance_title_id)
        assert stored is not None
        # Scored from what the database returns for the title, not from hand-built inputs.
        assert ctx.for_title(stored.genres, stored.imdb_rating, stored.tmdb_rating, "en") == Taste(
            fit=79, genres=["Science Fiction", "Mystery"], agreement=None
        )
        assert [g.id for g in stored.genres] == [DRAMA, SCIFI, MYSTERY]
        assert float(stored.imdb_rating) == 8.7
        assert stored.tmdb_rating is None
        assert title_inputs(conn, 999_999) is None


def test_private_ratings_never_move_a_score(spec, engine):
    with as_user(engine, DANA) as conn:
        before = TasteContext.load(conn).for_post(get_post(conn, spec.odyssey_post_id), "en")
    with engine.begin() as conn:  # Gal adds a private rating on a title Dana also rated
        insert_post(conn, GAL, spec.c9_title_id, 1.0, False)
    with as_user(engine, DANA) as conn:
        ctx = TasteContext.load(conn)
        after = ctx.for_post(get_post(conn, spec.odyssey_post_id), "en")
        agreements = load_agreements(conn)
    assert after == before
    assert set(agreements) == {GAL.id}
    common, gap = agreements[GAL.id]
    assert common == 8
    assert gap == pytest.approx(1.5)


def test_strangers_have_no_agreement(spec, engine):
    with engine.begin() as conn:
        for title in spec.comedy_title_ids:
            insert_post(conn, NOA, title, 5.0, False)
    with as_user(engine, NOA) as conn:
        assert load_agreements(conn) == {}


def test_own_post_and_locked(spec, engine):
    with as_user(engine, DANA) as conn:
        ctx = TasteContext.load(conn)
        own = get_post(conn, spec.dana_post_id)
        assert own.author.follow_state == "self"
        assert ctx.for_post(own, "en") is None
    with as_user(engine, RON) as conn:  # no ratings, no picks
        ctx = TasteContext.load(conn)
        assert not ctx.unlocked
        assert ctx.for_title(SEVERANCE_GENRES, 8.7, None, "en") is None


def test_one_rating_per_title_for_series(people, clean_catalog, engine):
    with engine.begin() as conn:
        conn.execute(INSERT_GENRE, {"id": DRAMA, "en": "Drama", "he": None})
        series = insert_series(conn, 4001, (1, 2))
        conn.execute(INSERT_TITLE_GENRE, {"title": series, "genre": DRAMA})
        insert_post(conn, NOA, series, 6.0, False, season=1)
        insert_post(conn, NOA, series, 8.0, False, season=2)
    with as_user(engine, NOA) as conn:
        profile = load_profile(conn)
    assert profile.rated == 1
    assert profile.mean_all == pytest.approx(0.7)
    assert profile.genres[DRAMA] == GenreStat(n=1, mean=pytest.approx(0.7))

    with engine.begin() as conn:  # the whole-series rating wins when it exists
        insert_post(conn, NOA, series, 9.0, False, season=0)
    with as_user(engine, NOA) as conn:
        profile = load_profile(conn)
    assert profile.rated == 1
    assert profile.mean_all == pytest.approx(0.9)
    assert profile.genres[DRAMA] == GenreStat(n=1, mean=pytest.approx(0.9))


def test_picks_unlock_a_cold_viewer(spec, engine):
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO app.user_genre_prefs (user_id, genre_id) VALUES (:u, :g)"),
            {"u": RON.id, "g": SCIFI},
        )
    with as_user(engine, RON) as conn:
        ctx = TasteContext.load(conn)
        assert ctx.unlocked
        taste = ctx.for_title(SEVERANCE_GENRES, 8.7, None, "en")
    assert taste is not None
    # G = (0.5 + 0.5 + 0.8) / 3 = 0.6 (one pick, no ratings); 0.7 * 0.6 + 0.3 * 0.87 = 0.681.
    assert taste.fit == 68
    assert taste.genres == ["Science Fiction"]
    assert taste.agreement is None
