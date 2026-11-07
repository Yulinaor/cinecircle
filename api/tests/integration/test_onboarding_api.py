"""The taste quiz (plan P6, P7, P8): 3-5 genre chips and private ratings of pool titles."""

import pytest
import sqlalchemy as sa

from cinecircle_api.catalog.service import TitleService
from tests.fakes import FakeOmdb, FakeTmdb

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

SHAWSHANK, FRIENDS = ("movie", 278), ("series", 1668)
_QUIZZER = "(SELECT id FROM app.profiles WHERE username = 'quizzer')"
_INSERT_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
    " VALUES (:tmdb_id, :media_type, :name, '{}') RETURNING id"
)
_PREFS = sa.text(f"SELECT genre_id FROM app.user_genre_prefs WHERE user_id = {_QUIZZER}")
_QUIZ_POSTS = sa.text(
    "SELECT title_id, season_number, rating, is_shared FROM app.posts"
    f" WHERE author_id = {_QUIZZER} ORDER BY title_id"
)
_EVENTS = sa.text(
    f"SELECT event_type, props FROM app.events WHERE user_id = {_QUIZZER} ORDER BY id"
)


@pytest.fixture
def pool_titles(engine) -> dict[tuple[str, int], int]:
    """Two pool titles already cached (the web loads them through /titles/tmdb first)."""
    with engine.begin() as conn:
        return {
            key: conn.scalar(
                _INSERT_TITLE, {"media_type": key[0], "tmdb_id": key[1], "name": f"T{key[1]}"}
            )
            for key in (SHAWSHANK, FRIENDS)
        }


@pytest.fixture
def quizzer(api):
    """A signed-in user who has just made a profile."""
    client = api("fresh-quizzer")
    r = client.post("/me", json={"username": "quizzer", "display_name": "Quizzer"})
    assert r.status_code == 201, r.text
    return client


def _picks(engine) -> set[int]:
    with engine.connect() as conn:
        return set(conn.execute(_PREFS).scalars())


def _posts(engine) -> list[tuple]:
    with engine.connect() as conn:
        return [(t, s, float(r), shared) for t, s, r, shared in conn.execute(_QUIZ_POSTS)]


def _answers(genres, *ratings) -> dict:
    return {"genres": genres, "ratings": [{"title_id": t, "rating": r} for t, r in ratings]}


def _shown(state: dict) -> dict[tuple[str, int], float | None]:
    return {(q["media_type"], q["tmdb_id"]): q["my_rating"] for q in state["quiz"]}


def test_quiz_stores_picks_and_private_ratings(api, quizzer, pool_titles, engine, people):
    movie, series = pool_titles[SHAWSHANK], pool_titles[FRIENDS]
    assert quizzer.get("/me").json()["taste_unlocked"] is False
    before = quizzer.get("/onboarding").json()
    assert before["done"] is False
    assert len(before["genres"]) == 18 and not any(g["picked"] for g in before["genres"])
    assert [g["key"] for g in before["genres"]][:3] == ["action", "adventure", "animation"]
    assert [(q["media_type"], q["tmdb_id"]) for q in before["quiz"]][:2] == [
        ("movie", 278),
        ("movie", 155),
    ]
    assert len(before["quiz"]) == 10 and all(q["my_rating"] is None for q in before["quiz"])

    answers = _answers(["action", "drama", "comedy"], (movie, 9.5), (series, 7))
    r = quizzer.post("/onboarding", json=answers)
    assert r.status_code == 200, r.text
    state = r.json()
    assert state["done"] is True
    assert {g["key"] for g in state["genres"] if g["picked"]} == {"action", "drama", "comedy"}
    shown = _shown(state)
    assert shown[SHAWSHANK] == 9.5 and shown[FRIENDS] == 7.0
    assert sum(v is not None for v in shown.values()) == 2
    assert _picks(engine) == {28, 10759, 18, 35}
    assert _posts(engine) == [(movie, 0, 9.5, False), (series, 0, 7.0, False)]
    assert quizzer.get("/onboarding").json() == state
    assert quizzer.get("/me").json()["taste_unlocked"] is True

    # Nobody else sees the ratings, not even a follower the quizzer has accepted.
    with engine.begin() as conn:
        pair = {"follower": people["dana"].id, "me": quizzer.get("/me").json()["id"]}
        conn.execute(
            sa.text("INSERT INTO app.follows (follower_id, followee_id) VALUES (:follower, :me)"),
            pair,
        )
        conn.execute(
            sa.text(
                "UPDATE app.follows SET status = 'accepted'"
                " WHERE follower_id = :follower AND followee_id = :me"
            ),
            pair,
        )
    for viewer in ("dana", "noa", "gal"):
        other = api(viewer)
        assert other.get("/feed").json()["posts"] == [], viewer
        profile = other.get("/users/quizzer/posts")
        assert profile.status_code in (200, 404), viewer
        if profile.status_code == 200:
            assert profile.json()["posts"] == [], viewer
        for title_id in (movie, series):
            assert other.get(f"/titles/{title_id}").json()["posts"] == [], (viewer, title_id)


def test_quiz_logs_events_and_marks_watched(quizzer, pool_titles, engine):
    movie = pool_titles[SHAWSHANK]
    saved = quizzer.post("/wishlist", json={"title_id": movie, "source": "discover"})
    assert saved.status_code == 201, saved.text
    r = quizzer.post("/onboarding", json=_answers(["horror", "war", "western"], (movie, 8)))
    assert r.status_code == 200, r.text
    watched = quizzer.get("/wishlist", params={"status": "watched"}).json()["items"]
    assert [item["title"]["id"] for item in watched] == [movie]
    with engine.connect() as conn:
        events = [(e.event_type, e.props) for e in conn.execute(_EVENTS) if e.event_type != "saved"]
    assert events == [
        ("post_created", {"shared": False, "surface": "onboarding"}),
        ("watched", {"via": "post"}),
        ("onboarding_done", {"genres": 3, "ratings": 1}),
    ]


def test_quiz_keeps_existing_posts(quizzer, pool_titles, engine):
    movie = pool_titles[SHAWSHANK]
    created = quizzer.post("/posts", json={"title_id": movie, "rating": 7, "opinion": "mine"})
    assert created.status_code == 201, created.text
    r = quizzer.post("/onboarding", json=_answers(["action", "drama", "comedy"], (movie, 2)))
    assert r.status_code == 200, r.text
    assert _posts(engine) == [(movie, 0, 7.0, True)]
    assert _shown(r.json())[SHAWSHANK] == 7.0
    assert quizzer.get(f"/posts/{created.json()['id']}").json()["opinion"] == "mine"


def test_retake_replaces_picks(quizzer, engine):
    first = quizzer.post("/onboarding", json=_answers(["action", "drama", "comedy"]))
    assert first.status_code == 200, first.text
    second = quizzer.post("/onboarding", json=_answers(["horror", "romance", "scifi"]))
    assert second.status_code == 200, second.text
    assert _picks(engine) == {27, 10749, 878, 10765}
    picked = {g["key"] for g in second.json()["genres"] if g["picked"]}
    assert picked == {"horror", "romance", "scifi"}


def test_unknown_title_stores_nothing(quizzer, pool_titles, engine):
    movie = pool_titles[SHAWSHANK]
    first = quizzer.post("/onboarding", json=_answers(["action", "drama", "comedy"]))
    assert first.status_code == 200, first.text
    answers = _answers(["horror", "war", "western"], (movie, 8), (999999, 8))
    r = quizzer.post("/onboarding", json=answers)
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})
    assert _picks(engine) == {28, 10759, 18, 35}
    assert _posts(engine) == []


def test_invalid_answers_store_nothing(quizzer, engine):
    for body in (
        _answers(["action", "drama"]),
        _answers(["action", "drama", "nonsense"]),
        _answers(["action", "action", "drama"]),
        _answers(["action", "drama", "comedy"], (1, 0)),
    ):
        assert quizzer.post("/onboarding", json=body).status_code == 422
    assert _picks(engine) == set()


def test_genres_unavailable_is_503(quizzer, engine):
    down = FakeTmdb()
    down.fail = True
    quizzer.app.state.title_service = TitleService(engine, down, FakeOmdb())
    r = quizzer.post("/onboarding", json=_answers(["action", "drama", "comedy"]))
    assert (r.status_code, r.json()) == (503, {"detail": "catalog_unavailable"})
    assert _picks(engine) == set()


def test_onboarding_needs_a_profile(api):
    fresh = api("fresh")
    r = fresh.get("/onboarding")
    assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})
    r = fresh.post("/onboarding", json=_answers(["action", "drama", "comedy"]))
    assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})
