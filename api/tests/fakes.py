"""Fixture-backed stand-ins for TmdbClient and OmdbClient. They count calls and can be
switched to fail like a down or rate-limited service."""

from collections import Counter

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound
from tests.fixtures import load

ODYSSEY_ID = 1368337
SEVERANCE_ID = 95396
NO_HEBREW_ID = 791523

_DETAILS = {
    ("movie", ODYSSEY_ID): "tmdb/movie_odyssey",
    ("series", SEVERANCE_ID): "tmdb/tv_severance",
    ("movie", NO_HEBREW_ID): "tmdb/movie_no_hebrew",
}


class FakeTmdb:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.fail = False

    def _call(self, name: str) -> None:
        self.calls[name] += 1
        if self.fail:
            raise ExternalApiError("tmdb", 503)

    def search_multi(self, query: str, language: str) -> dict:
        self._call("search_multi")
        return load("tmdb/search_odyssey_he" if language == "he-IL" else "tmdb/search_odyssey_en")

    def title_details(self, tmdb_id: int, media_type: str) -> dict:
        self._call("title_details")
        name = _DETAILS.get((media_type, tmdb_id))
        if name is None:
            raise ExternalNotFound("tmdb", 404)
        return load(name)

    def genre_list(self, kind: str, language: str) -> dict:
        self._call("genre_list")
        return load(f"tmdb/genre_{kind}_{'he' if language == 'he-IL' else 'en'}")


class FakeOmdb:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self._by_id = {
            load("tmdb/movie_odyssey")["external_ids"]["imdb_id"]: "omdb/odyssey",
            load("tmdb/tv_severance")["external_ids"]["imdb_id"]: "omdb/severance",
        }

    def by_imdb_id(self, imdb_id: str) -> dict | None:
        self.calls += 1
        if self.fail:
            raise ExternalApiError("omdb", 503)
        name = self._by_id.get(imdb_id)
        return load(name) if name else None
