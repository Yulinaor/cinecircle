import pytest

from tests.fixtures import FIXTURE_DIR, load

NAMES = [
    "tmdb/search_odyssey_en",
    "tmdb/search_odyssey_he",
    "tmdb/movie_odyssey",
    "tmdb/movie_no_hebrew",
    "tmdb/tv_severance",
    "tmdb/genre_movie_en",
    "tmdb/genre_movie_he",
    "tmdb/genre_tv_en",
    "tmdb/genre_tv_he",
    "omdb/odyssey",
    "omdb/severance",
    "omdb/not_found",
]


@pytest.mark.parametrize("name", NAMES)
def test_fixture_loads(name):
    assert isinstance(load(name), dict)


def test_fixtures_hold_no_credentials():
    for path in FIXTURE_DIR.rglob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        assert "api_key" not in text and "apikey" not in text, path
