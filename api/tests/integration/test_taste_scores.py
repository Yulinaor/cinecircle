"""Taste Match from real SQL, as the viewer (RLS applies): spec 03 section 4 reproduced end to end,
and the privacy rules of section 1.3 (plan P5): a private rating never moves anyone's score.

The dataset is the one of 03 section 4. Dana has 20 rated titles (mean exactly 0.70, no picks),
all private. Gal (whom Dana follows) shares 6.5 on each of Dana's eight Comedy titles C1-C8
(gap 1.5) and 9.0 on *The Odyssey*; his 1.0 on A1 is private.
"""

from dataclasses import dataclass

import pytest
import sqlalchemy as sa

from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.posts.repository import get_post
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.taste.models import Taste
from cinecircle_api.taste.repository import load_agreements, load_profile, title_inputs
from cinecircle_api.taste.score import GenreStat
from tests.integration.conftest import DANA, GAL, NOA, RON, as_user, insert_series

pytestmark = pytest.mark.integration

ACTION, ADVENTURE, DRAMA, MYSTERY, SCIFI, COMEDY = 28, 12, 18, 9648, 878, 35
_GENRES = (
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

_INSERT_GENRE = sa.text("INSERT INTO app.genres (id, name_en, name_he) VALUES (:id, :en, :he)")
_INSERT_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
    " VALUES (:tmdb_id, :media_type, :name, :imdb, '{}') RETURNING id"
)
_INSERT_TITLE_GENRE = sa.text(
    "INSERT INTO app.title_genres (title_id, genre_id) VALUES (:title, :genre)"
)
_INSERT_POST = sa.text(
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


def _post(conn, author, title, rating, shared, season=0) -> int:
    return conn.scalar(
        _INSERT_POST,
        {
            "author": author.id,
            "title": title,
            "season": season,
            "rating": rating,
            "shared": shared,
        },
    )


def _title(conn, tmdb_id, name, genres, imdb=None, media_type="movie") -> int:
    title_id = conn.scalar(
        _INSERT_TITLE, {"tmdb_id": tmdb_id, "media_type": media_type, "name": name, "imdb": imdb}
    )
    for genre in genres:
        conn.execute(_INSERT_TITLE_GENRE, {"title": title_id, "genre": genre})
    return title_id


def spec_dataset(engine, people) -> SpecIds:
    """03 section 4, built as postgres (no RLS). `people` cleanup removes the posts; the
    `clean_catalog` fixture removes the titles."""
    n = iter(range(1000, 2000))
    with engine.begin() as conn:
        for genre_id, name_en, name_he in _GENRES:
            conn.execute(_INSERT_GENRE, {"id": genre_id, "en": name_en, "he": name_he})

        def dana(name, genres, rating):
            title = _title(conn, next(n), name, genres)
            return title, _post(conn, DANA, title, rating, False)

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
            _post(conn, GAL, title, 6.5, True)
            comedies.append(title)
        c9, dana_post = dana("C9", [COMEDY], 6)
        _post(conn, GAL, a1, 1.0, False)  # private: must be ignored

        odyssey = _title(conn, next(n), "The Odyssey", [ACTION, ADVENTURE, DRAMA], imdb=8.5)
        odyssey_post = _post(conn, GAL, odyssey, 9.0, True)
        severance = _title(
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
        assert ctx.for_title(SEVERANCE_GENRES, 8.7, None, "en") == Taste(
            fit=79, genres=["Science Fiction", "Mystery"], agreement=None
        )
        stored = title_inputs(conn, spec.severance_title_id)
        assert stored is not None
        assert [g.id for g in stored.genres] == [DRAMA, SCIFI, MYSTERY]
        assert float(stored.imdb_rating) == 8.7
        assert stored.tmdb_rating is None
        assert title_inputs(conn, 999_999) is None


def test_private_ratings_never_move_a_score(spec, engine):
    with as_user(engine, DANA) as conn:
        before = TasteContext.load(conn).for_post(get_post(conn, spec.odyssey_post_id), "en")
    with engine.begin() as conn:  # Gal adds a private rating on a title Dana also rated
        _post(conn, GAL, spec.c9_title_id, 1.0, False)
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
            _post(conn, NOA, title, 5.0, False)
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
        conn.execute(_INSERT_GENRE, {"id": DRAMA, "en": "Drama", "he": None})
        series = insert_series(conn, 4001, (1, 2))
        conn.execute(_INSERT_TITLE_GENRE, {"title": series, "genre": DRAMA})
        _post(conn, NOA, series, 6.0, False, season=1)
        _post(conn, NOA, series, 8.0, False, season=2)
    with as_user(engine, NOA) as conn:
        profile = load_profile(conn)
    assert profile.rated == 1
    assert profile.mean_all == pytest.approx(0.7)
    assert profile.genres[DRAMA] == GenreStat(n=1, mean=pytest.approx(0.7))

    with engine.begin() as conn:  # the whole-series rating wins when it exists
        _post(conn, NOA, series, 9.0, False, season=0)
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
    assert taste.agreement is None
