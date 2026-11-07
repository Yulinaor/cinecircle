from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from cinecircle_api.catalog.parse import GenreRow, SearchResult
from cinecircle_api.catalog.repository import SeasonRow, TitleRow
from cinecircle_api.catalog.service import CachedTitle, CatalogUnavailable, TitleNotFound
from cinecircle_api.db import user_session
from cinecircle_api.main import create_app
from cinecircle_api.routes import titles as titles_route
from tests.tokens import auth_settings, make_token

DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"
SIGNED_IN = {"Authorization": f"Bearer {make_token('6f1c2b6e-0000-4000-8000-000000000001')}"}


def make_row(**overrides) -> TitleRow:
    fields = dict(
        id=7,
        tmdb_id=1368337,
        media_type="movie",
        imdb_id="tt33764258",
        name_en="The Odyssey",
        name_he="האודיסאה",
        overview_en="Plot",
        overview_he="עלילה",
        year_start=2026,
        year_end=None,
        runtime_min=172,
        season_count=None,
        poster_path="/p.jpg",
        imdb_rating=Decimal("8.4"),
        imdb_votes=477953,
        rt_score=94,
        metacritic=88,
        tmdb_rating=Decimal("7.9"),
        raw_tmdb={},
        raw_omdb={},
        fetched_at=datetime(2026, 11, 1, tzinfo=UTC),
        genres=(GenreRow(18, "Drama", "דרמה"), GenreRow(12, "Adventure", None)),
        seasons=(),
    )
    fields.update(overrides)
    return TitleRow(**fields)


class StubService:
    def __init__(self) -> None:
        self.seen: list[tuple] = []
        self.row = make_row()
        self.error: Exception | None = None

    def search(self, query, type_filter, lang):
        self.seen.append((query, type_filter, lang))
        if self.error:
            raise self.error
        return [SearchResult(1368337, "movie", "The Odyssey", 2026, None)]

    def get(self, title_id):
        if self.error:
            raise self.error
        return CachedTitle(self.row, stale=False)

    def get_by_tmdb(self, tmdb_id, media_type):
        return self.get(0)


@pytest.fixture
def stub():
    return StubService()


@pytest.fixture
def client(stub, monkeypatch):
    app = create_app(auth_settings(DEAD))
    app.state.title_service = stub
    # /titles/{id} also reads the viewer's posts and wishlist; these tests are about the
    # catalogue part.
    app.dependency_overrides[user_session] = lambda: None
    monkeypatch.setattr(titles_route.posts_repository, "title_posts", lambda conn, title_id: [])
    monkeypatch.setattr(
        titles_route.wishlist_repository, "in_wishlist", lambda conn, title_id: False
    )
    return TestClient(app, headers=SIGNED_IN)


def test_search_rejects_blank_and_long_queries(client):
    assert client.get("/titles/search", params={"q": "   "}).status_code == 422
    assert client.get("/titles/search", params={"q": "x" * 101}).status_code == 422
    assert client.get("/titles/search", params={"q": "x" * 100}).status_code == 200


def test_search_passes_type_and_lang(client, stub):
    r = client.get("/titles/search", params={"q": " האודיסאה ", "type": "series", "lang": "en"})
    assert r.status_code == 200
    assert stub.seen == [("האודיסאה", "series", "en")]
    assert r.json() == {
        "results": [
            {
                "tmdb_id": 1368337,
                "media_type": "movie",
                "name": "The Odyssey",
                "year": 2026,
                "poster_url": None,
            }
        ]
    }


def test_search_defaults_to_all_and_hebrew(client, stub):
    client.get("/titles/search", params={"q": "x"})
    assert stub.seen == [("x", "all", "he")]


def test_detail_404_and_503(client, stub):
    stub.error = TitleNotFound()
    r = client.get("/titles/7")
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})
    stub.error = CatalogUnavailable()
    r = client.get("/titles/tmdb/movie/1")
    assert (r.status_code, r.json()) == (503, {"detail": "catalog_unavailable"})
    r = client.get("/titles/search", params={"q": "x"})
    assert (r.status_code, r.json()) == (503, {"detail": "catalog_unavailable"})


def test_detail_hebrew_fallback_labelled(client, stub):
    stub.row = make_row(overview_he=None)
    body = client.get("/titles/7", params={"lang": "he"}).json()
    assert (body["overview"], body["overview_lang"]) == ("Plot", "en")
    assert (body["name"], body["name_lang"]) == ("האודיסאה", "he")
    assert body["genres"] == [{"id": 18, "name": "דרמה"}, {"id": 12, "name": "Adventure"}]


def test_detail_shape(client, stub):
    stub.row = make_row(
        media_type="series",
        seasons=(SeasonRow(1, "Season 1", None, "Intro", None, None, None, 9),),
    )
    body = client.get("/titles/7", params={"lang": "en"}).json()
    assert body["posts"] == []
    assert body["ratings"] == {
        "imdb": {"rating": 8.4, "votes": 477953},
        "rotten_tomatoes": 94,
        "metacritic": 88,
        "tmdb": 7.9,
    }
    assert body["seasons"] == [
        {
            "season_number": 1,
            "name": "Season 1",
            "name_lang": "en",
            "overview": "Intro",
            "air_date": None,
            "episode_count": 9,
            "poster_url": None,
        }
    ]
    assert body["stale"] is False and body["id"] == 7 and body["name_lang"] == "en"
    # No Hebrew name: a Hebrew screen gets the English one, labelled as English (A6).
    season = client.get("/titles/7", params={"lang": "he"}).json()["seasons"][0]
    assert (season["name"], season["name_lang"]) == ("Season 1", "en")


def test_poster_url_built_and_null_safe(client, stub):
    body = client.get("/titles/7").json()
    assert body["poster_url"] == "https://image.tmdb.org/t/p/w342/p.jpg"
    stub.row = make_row(poster_path=None, imdb_rating=None)
    body = client.get("/titles/7").json()
    assert body["poster_url"] is None and body["ratings"]["imdb"] is None


def test_titles_503_without_keys(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    client = TestClient(create_app(auth_settings(DEAD)), headers=SIGNED_IN)
    r = client.get("/titles/search", params={"q": "x"})
    assert (r.status_code, r.json()) == (503, {"detail": "catalog_unavailable"})
    assert client.get("/live").status_code == 200
