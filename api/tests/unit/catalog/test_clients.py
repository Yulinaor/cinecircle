import logging

import httpx
import pytest

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound
from cinecircle_api.catalog.omdb_client import OmdbClient
from cinecircle_api.catalog.tmdb_client import TmdbClient
from tests.fixtures import load

KEY = "k3y-s3cret-123"


def recording(status: int = 200, body: dict | None = None, exc: Exception | None = None):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if exc is not None:
            raise exc
        return httpx.Response(status, json=body if body is not None else {})

    return seen, httpx.Client(transport=httpx.MockTransport(handler))


def test_tmdb_v3_key_goes_in_query():
    seen, http = recording()
    TmdbClient(KEY, http).genre_list("movie", "en-US")
    assert seen[0].url.params["api_key"] == KEY
    assert "authorization" not in seen[0].headers


def test_tmdb_v4_token_goes_in_header():
    seen, http = recording()
    TmdbClient("eyJabc", http).genre_list("tv", "he-IL")
    assert seen[0].headers["authorization"] == "Bearer eyJabc"
    assert "api_key" not in seen[0].url.params


def test_search_query_is_encoded():
    seen, http = recording()
    client = TmdbClient(KEY, http)
    client.search_multi("Tom & Jerry #1 100%", "en-US")
    client.search_multi("האודיסאה", "he-IL")
    assert seen[0].url.params["query"] == "Tom & Jerry #1 100%"
    assert seen[1].url.params["query"] == "האודיסאה"
    assert seen[0].url.params["include_adult"] == "false"
    assert seen[1].url.params["language"] == "he-IL"


def test_title_details_series_uses_tv_path():
    seen, http = recording()
    TmdbClient(KEY, http).title_details(95396, "series")
    assert seen[0].url.path == "/3/tv/95396"
    assert seen[0].url.params["append_to_response"] == "external_ids,translations"
    assert seen[0].url.params["language"] == "en-US"


def test_season_details_url_and_language():
    seen, http = recording()
    TmdbClient(KEY, http).season_details(95396, 1, "he-IL")
    assert seen[0].url.path == "/3/tv/95396/season/1"
    assert seen[0].url.params["language"] == "he-IL"


def test_404_raises_not_found():
    _, http = recording(status=404)
    with pytest.raises(ExternalNotFound):
        TmdbClient(KEY, http).title_details(1, "movie")


@pytest.mark.parametrize("status", [429, 500])
def test_429_and_500_raise_external_error(status):
    _, http = recording(status=status)
    with pytest.raises(ExternalApiError) as info:
        TmdbClient(KEY, http).search_multi("x", "en-US")
    assert info.value.status == status
    assert info.value.source == "tmdb"


def test_timeout_raises_external_error():
    _, http = recording(exc=httpx.ReadTimeout("timed out"))
    with pytest.raises(ExternalApiError) as info:
        TmdbClient(KEY, http).search_multi("x", "en-US")
    assert info.value.status is None


@pytest.mark.parametrize(
    ("status", "exc"),
    [(500, None), (200, httpx.ConnectError(f"cannot reach https://www.omdbapi.com/?apikey={KEY}"))],
)
def test_error_message_never_contains_key(status, exc):
    _, http = recording(status=status, exc=exc)
    with pytest.raises(ExternalApiError) as info:
        OmdbClient(KEY, http).by_imdb_id("tt1234567")
    err = info.value
    assert KEY not in str(err) and KEY not in repr(err)
    assert err.__cause__ is None and err.__suppress_context__ is True
    assert err.source == "omdb"


def test_omdb_response_false_returns_none():
    _, http = recording(body=load("omdb/not_found"))
    assert OmdbClient(KEY, http).by_imdb_id("tt0000000") is None


def test_omdb_sends_imdb_id_and_key():
    seen, http = recording(body=load("omdb/odyssey"))
    assert OmdbClient(KEY, http).by_imdb_id("tt1234567")["Title"] == "The Odyssey"
    assert seen[0].url.params["i"] == "tt1234567"
    assert seen[0].url.params["apikey"] == KEY


def test_logs_never_contain_key(caplog):

    caplog.set_level(logging.DEBUG)
    _, http = recording(body=load("omdb/odyssey"))
    OmdbClient(KEY, http).by_imdb_id("tt1234567")
    assert caplog.records and all(KEY not in r.getMessage() for r in caplog.records)
    assert logging.getLogger("httpx").level == logging.WARNING


def test_json_array_body_is_external_error():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="[]")))
    with pytest.raises(ExternalApiError) as info:
        TmdbClient(KEY, http).genre_list("movie", "en-US")
    assert info.value.status == 200


def test_discover_calls_use_the_right_paths():
    seen, http = recording()
    client = TmdbClient(KEY, http)
    client.trending("movie", "he-IL")
    client.trending("tv", "en-US")
    client.top_rated("tv", "he-IL")
    client.recommendations("movie", 603, "en-US")
    client.reviews("movie", 603)
    paths = [r.url.path for r in seen]
    assert paths == [
        "/3/trending/movie/week",
        "/3/trending/tv/week",
        "/3/tv/top_rated",
        "/3/movie/603/recommendations",
        "/3/movie/603/reviews",
    ]
    assert seen[0].url.params["language"] == "he-IL"
    assert seen[2].url.params["language"] == "he-IL"
    assert seen[3].url.params["language"] == "en-US"
    assert "language" not in seen[4].url.params  # reviews come in every language
    assert all(r.url.params["page"] == "1" for r in seen)
