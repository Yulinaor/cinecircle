"""OMDb HTTP client (IMDb, Rotten Tomatoes and Metacritic ratings). HTTP only."""

import httpx

from cinecircle_api.catalog._http import get_json

BASE_URL = "https://www.omdbapi.com/"


class OmdbClient:
    def __init__(self, api_key: str, http: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http or httpx.Client()

    def by_imdb_id(self, imdb_id: str) -> dict | None:
        """The OMDb record, or None when OMDb answers `"Response": "False"`."""
        body = get_json(self._http, "omdb", BASE_URL, {"i": imdb_id, "apikey": self._api_key})
        return None if body.get("Response") == "False" else body
