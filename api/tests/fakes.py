"""Fixture-backed stand-ins for TmdbClient and OmdbClient. They count calls and can be
switched to fail like a down or rate-limited service."""

from collections import Counter

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound
from tests.fixtures import load

ODYSSEY_ID = 1368337
SEVERANCE_ID = 95396
NO_HEBREW_ID = 791523
MATRIX_ID = 603  # the movie the recommendation and review fixtures were recorded for

_DETAILS = {
    ("movie", ODYSSEY_ID): "tmdb/movie_odyssey",
    ("series", SEVERANCE_ID): "tmdb/tv_severance",
    ("movie", NO_HEBREW_ID): "tmdb/movie_no_hebrew",
}


class FakeTmdb:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.fail = False
        self.gone: set[int] = set()  # ids TMDB has deleted or merged since

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
        if name is None or tmdb_id in self.gone:
            raise ExternalNotFound("tmdb", 404)
        return load(name)

    def season_details(self, tmdb_id: int, season_number: int, language: str) -> dict:
        self._call("season_details")
        if (tmdb_id, season_number) != (SEVERANCE_ID, 1):
            raise ExternalNotFound("tmdb", 404)
        return load("tmdb/tv_severance_season_1_he")

    def genre_list(self, kind: str, language: str) -> dict:
        self._call("genre_list")
        return load(f"tmdb/genre_{kind}_{'he' if language == 'he-IL' else 'en'}")

    def trending(self, kind: str, language: str) -> dict:
        self._call("trending")
        return load(f"tmdb/trending_{kind}_{'he' if language == 'he-IL' else 'en'}")

    def top_rated(self, kind: str, language: str) -> dict:
        self._call("top_rated")
        return load(f"tmdb/top_rated_{kind}_{'he' if language == 'he-IL' else 'en'}")

    def recommendations(self, kind: str, tmdb_id: int, language: str) -> dict:
        """The recorded list for any movie id (it was recorded for MATRIX_ID); none for series."""
        self._call("recommendations")
        if kind != "movie":
            return {"page": 1, "results": [], "total_results": 0}
        return load(f"tmdb/recommendations_movie_{'he' if language == 'he-IL' else 'en'}")

    def reviews(self, kind: str, tmdb_id: int) -> dict:
        """The recorded reviews for any movie id (recorded for MATRIX_ID); none for series."""
        self._call("reviews")
        if kind != "movie":
            return {"id": tmdb_id, "page": 1, "results": [], "total_results": 0}
        return load("tmdb/reviews_movie")


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
