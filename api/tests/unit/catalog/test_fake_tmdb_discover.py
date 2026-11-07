import pytest

from cinecircle_api.catalog.errors import ExternalApiError
from cinecircle_api.catalog.parse import parse_list, parse_reviews
from tests.fakes import MATRIX_ID, FakeTmdb


def test_fake_serves_the_recorded_discover_calls_and_counts_them():
    tmdb = FakeTmdb()
    he = parse_list(tmdb.trending("movie", "he-IL"), "movie")
    en = parse_list(tmdb.trending("movie", "en-US"), "movie")
    assert [i.tmdb_id for i in he] == [i.tmdb_id for i in en]
    assert parse_list(tmdb.top_rated("tv", "en-US"), "series")
    assert parse_list(tmdb.recommendations("movie", MATRIX_ID, "he-IL"), "movie")
    assert parse_reviews(tmdb.reviews("movie", MATRIX_ID))
    assert tmdb.recommendations("tv", 1, "en-US")["results"] == []
    assert tmdb.reviews("tv", 1)["results"] == []
    assert tmdb.calls["trending"] == 2 and tmdb.calls["reviews"] == 2


@pytest.mark.parametrize(
    "call",
    [
        lambda t: t.trending("movie", "en-US"),
        lambda t: t.top_rated("movie", "en-US"),
        lambda t: t.recommendations("movie", MATRIX_ID, "en-US"),
        lambda t: t.reviews("movie", MATRIX_ID),
    ],
)
def test_fake_fails_like_a_down_tmdb(call):
    tmdb = FakeTmdb()
    tmdb.fail = True
    with pytest.raises(ExternalApiError):
        call(tmdb)
