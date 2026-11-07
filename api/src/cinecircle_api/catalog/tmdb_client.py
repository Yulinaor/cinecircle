"""TMDB HTTP client. HTTP only: no users, no database."""

from typing import Literal

import httpx

from cinecircle_api.catalog._http import get_json

BASE_URL = "https://api.themoviedb.org/3"
TmdbLanguage = Literal["he-IL", "en-US"]


class TmdbClient:
    def __init__(self, api_key: str, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client()
        self._params: dict[str, str] = {}
        self._headers: dict[str, str] = {}
        # A v4 read token is a JWT ("eyJ…") and goes in the header; a v3 key goes in the query.
        if api_key.startswith("eyJ"):
            self._headers["Authorization"] = f"Bearer {api_key}"
        else:
            self._params["api_key"] = api_key

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, **params: str) -> dict:
        url = f"{BASE_URL}/{path}"
        return get_json(self._http, "tmdb", url, {**self._params, **params}, self._headers)

    def search_multi(self, query: str, language: TmdbLanguage) -> dict:
        return self._get(
            "search/multi", query=query, language=language, include_adult="false", page="1"
        )

    def title_details(self, tmdb_id: int, media_type: Literal["movie", "series"]) -> dict:
        kind = "tv" if media_type == "series" else "movie"
        # One call per title (P1): Hebrew text comes from the `translations` entry.
        return self._get(
            f"{kind}/{tmdb_id}", language="en-US", append_to_response="external_ids,translations"
        )

    def season_details(self, tmdb_id: int, season_number: int, language: TmdbLanguage) -> dict:
        return self._get(f"tv/{tmdb_id}/season/{season_number}", language=language)

    def genre_list(self, kind: Literal["movie", "tv"], language: TmdbLanguage) -> dict:
        return self._get(f"genre/{kind}/list", language=language)
