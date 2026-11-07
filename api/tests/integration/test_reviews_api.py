from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from cinecircle_api.catalog.service import TitleService
from cinecircle_api.discover.service import DiscoverService
from tests.fakes import MATRIX_ID, FakeTmdb
from tests.fixtures import load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]
T0 = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = T0 + timedelta(**kwargs)


class World:
    """A signed-in client whose Discover service has a fake clock and a fake TMDB."""

    def __init__(self, client: TestClient, engine, tmdb: FakeTmdb, clock: Clock) -> None:
        self.client, self.engine, self.tmdb, self.clock = client, engine, tmdb, clock

    def add_title(self, media_type: str = "movie", tmdb_id: int = MATRIX_ID) -> int:
        with self.engine.begin() as conn:
            return conn.scalar(
                sa.text(
                    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                    " VALUES (:tmdb_id, :mt, 'T', '{}') RETURNING id"
                ),
                {"tmdb_id": tmdb_id, "mt": media_type},
            )

    def get(self, title_id: int):
        return self.client.get(f"/titles/{title_id}/reviews")

    def fetched_at(self, title_id: int):
        with self.engine.connect() as conn:
            return conn.scalar(
                sa.text("SELECT reviews_fetched_at FROM app.titles WHERE id = :id"),
                {"id": title_id},
            )


@pytest.fixture
def world(api, engine):
    client = api("dana")
    tmdb, clock = FakeTmdb(), Clock()
    titles = TitleService(engine, tmdb, None, now=clock)
    client.app.state.discover_service = DiscoverService(engine, tmdb, titles, now=clock)
    return World(client, engine, tmdb, clock)


def test_reviews_cached_for_seven_days(world):
    title_id = world.add_title()
    first = world.get(title_id)
    assert first.status_code == 200
    reviews = first.json()["reviews"]
    assert 1 <= len(reviews) <= 5
    assert all(r["source"] == "tmdb" for r in reviews)
    assert world.tmdb.calls["reviews"] == 1
    assert world.fetched_at(title_id) == T0

    world.clock.advance(days=6, hours=23)
    assert world.get(title_id).json() == first.json()
    assert world.tmdb.calls["reviews"] == 1

    world.clock.advance(days=8)
    assert world.get(title_id).json() == first.json()  # same reviews: upserted, not duplicated
    assert world.tmdb.calls["reviews"] == 2
    assert world.fetched_at(title_id) == world.clock.now
    with world.engine.connect() as conn:
        count = conn.scalar(sa.text("SELECT count(*) FROM app.external_reviews"))
    assert count == len(reviews)


def test_zero_reviews_are_remembered(world):
    title_id = world.add_title("series", 7)  # the fake has no reviews for series
    assert world.get(title_id).json() == {"reviews": []}
    assert world.fetched_at(title_id) == T0
    assert world.get(title_id).json() == {"reviews": []}
    assert world.tmdb.calls["reviews"] == 1


def test_tmdb_down_with_nothing_cached_is_an_empty_list(world):
    title_id = world.add_title()
    world.tmdb.fail = True
    r = world.get(title_id)
    assert r.status_code == 200 and r.json() == {"reviews": []}
    assert world.fetched_at(title_id) is None  # retried on the next visit


def test_tmdb_down_keeps_cached_reviews(world):
    title_id = world.add_title()
    cached = world.get(title_id).json()
    assert cached["reviews"]
    world.clock.advance(days=8)
    world.tmdb.fail = True
    assert world.get(title_id).json() == cached
    assert world.fetched_at(title_id) == T0  # not touched: the refresh is retried


def test_at_most_five_newest_reviews(world):
    raw = load("tmdb/reviews_movie")
    template = raw["results"][0]
    raw["results"] = [
        {**template, "id": f"r{n}", "url": f"https://www.themoviedb.org/review/r{n}"}
        for n in range(7)
    ]
    world.tmdb.reviews = lambda kind, tmdb_id: raw
    title_id = world.add_title()
    assert len(world.get(title_id).json()["reviews"]) == 5
    with world.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM app.external_reviews")) == 5


def test_review_excerpts(world):
    hostile = (
        "**Bold** claim <script>alert(1)</script> with [a link](http://evil.example) &amp; "
        + "wordy " * 1000
    )
    raw = load("tmdb/reviews_movie")
    raw["results"] = [{**raw["results"][0], "content": hostile}]
    world.tmdb.reviews = lambda kind, tmdb_id: raw
    title_id = world.add_title()
    review = world.get(title_id).json()["reviews"][0]
    assert len(review["excerpt"]) <= 300 and review["excerpt"].endswith("…")
    assert review["excerpt"].startswith("Bold claim ")
    assert "<" not in review["excerpt"] and "evil.example" not in review["excerpt"]
    assert "a link & wordy" in review["excerpt"]  # plain text, not HTML-escaped
    assert review["source"] == "tmdb" and review["url"].startswith("https://")
    with world.engine.connect() as conn:
        stored = conn.scalar(sa.text("SELECT excerpt FROM app.external_reviews"))
    assert stored == review["excerpt"]


def test_review_fields_are_attributed(world):
    title_id = world.add_title()
    review = world.get(title_id).json()["reviews"][0]
    assert set(review) == {"author_name", "excerpt", "url", "author_rating", "source"}
    assert review["author_name"] and review["url"].startswith("https://www.themoviedb.org/")


def test_reviews_unknown_title_404(world):
    r = world.get(999999)
    assert r.status_code == 404 and r.json() == {"detail": "not_found"}
    assert world.client.get("/titles/abc/reviews").status_code == 404
    assert world.tmdb.calls["reviews"] == 0


def test_reviews_need_sign_in_but_no_profile(api, world):
    title_id = world.add_title()
    assert TestClient(world.client.app).get(f"/titles/{title_id}/reviews").status_code == 401
    # A signed-in user without a profile still gets them: catalogue data, no user transaction.
    fresh = api("fresh-reviewer")
    fresh.app.state.discover_service = world.client.app.state.discover_service
    assert fresh.get(f"/titles/{title_id}/reviews").status_code == 200
