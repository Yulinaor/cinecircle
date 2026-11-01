import copy
from decimal import Decimal

from cinecircle_api.catalog.parse import (
    OmdbRatings,
    SearchResult,
    merge_genre_lists,
    parse_omdb,
    parse_search,
    parse_title,
    pick_text,
)
from tests.fixtures import load


def test_parse_omdb_full():
    r = parse_omdb(
        {
            "Response": "True",
            "imdbRating": "8.5",
            "imdbVotes": "1,234,567",
            "Ratings": [
                {"Source": "Rotten Tomatoes", "Value": "92%"},
                {"Source": "Metacritic", "Value": "80/100"},
            ],
        }
    )
    assert r == OmdbRatings(Decimal("8.5"), 1234567, 92, 80)


def test_parse_omdb_na_and_missing_ratings():
    raw = {"Response": "True", "imdbRating": "N/A", "imdbVotes": "N/A"}
    assert parse_omdb(raw) == OmdbRatings(None, None, None, None)


def test_parse_omdb_none():
    assert parse_omdb(None) == OmdbRatings(None, None, None, None)


def test_parse_omdb_from_fixtures():
    assert parse_omdb(load("omdb/odyssey")) == OmdbRatings(Decimal("8.4"), 477953, 94, 88)
    severance = parse_omdb(load("omdb/severance"))
    assert severance.imdb_rating == Decimal("8.6") and severance.rt_score is None


def test_parse_search_drops_people_and_filters_type():
    raw = {
        "results": [
            {"media_type": "person", "name": "Matt Damon", "id": 1},
            {
                "media_type": "movie",
                "id": 2,
                "title": "A",
                "release_date": "2026-07-17",
                "poster_path": "/a.jpg",
            },
            {"media_type": "tv", "id": 3, "name": "B", "first_air_date": ""},
        ]
    }
    assert parse_search(raw, "all") == [
        SearchResult(2, "movie", "A", 2026, "/a.jpg"),
        SearchResult(3, "series", "B", None, None),
    ]
    assert [r.tmdb_id for r in parse_search(raw, "series")] == [3]


def test_hebrew_search_finds_the_odyssey():
    odyssey_id = load("tmdb/movie_odyssey")["id"]
    results = parse_search(load("tmdb/search_odyssey_he"), "movie")
    assert odyssey_id in [r.tmdb_id for r in results]


def test_parse_title_movie_contract():
    t = parse_title(load("tmdb/movie_odyssey"), "movie")
    assert t.media_type == "movie"
    assert t.imdb_id.startswith("tt")
    assert t.name_en
    assert t.genre_ids
    assert t.seasons == ()


def test_parse_title_series_contract():
    t = parse_title(load("tmdb/tv_severance"), "series")
    assert t.media_type == "series"
    assert t.season_count >= 1
    assert all(s.season_number >= 1 for s in t.seasons)
    assert len(t.seasons) <= t.season_count


def test_empty_hebrew_overview_is_missing():
    raw = load("tmdb/movie_no_hebrew")
    assert parse_title(raw, "movie").overview_he is None
    raw = copy.deepcopy(load("tmdb/movie_odyssey"))
    for entry in raw["translations"]["translations"]:
        if entry["iso_639_1"] == "he":
            entry["data"]["overview"] = ""
    assert parse_title(raw, "movie").overview_he is None


def test_localize_falls_back_to_english():
    assert pick_text(None, "Plot", "he") == ("Plot", "en")
    assert pick_text("עלילה", "Plot", "he") == ("עלילה", "he")
    assert pick_text("עלילה", "Plot", "en") == ("Plot", "en")
    assert pick_text(None, None, "he") == (None, None)


def test_year_end_only_when_ended():
    raw = copy.deepcopy(load("tmdb/tv_severance"))
    raw["status"] = "Returning Series"
    assert parse_title(raw, "series").year_end is None
    raw["status"] = "Ended"
    raw["last_air_date"] = "2019-05-19"
    assert parse_title(raw, "series").year_end == 2019


def test_merge_genre_lists_from_fixtures():
    names = ["genre_movie_en", "genre_tv_en", "genre_movie_he", "genre_tv_he"]
    lists = {n: load(f"tmdb/{n}")["genres"] for n in names}
    en = lists["genre_movie_en"] + lists["genre_tv_en"]
    he = lists["genre_movie_he"] + lists["genre_tv_he"]
    rows = merge_genre_lists(en, he)
    assert {r.id for r in rows} == {g["id"] for g in en + he}
    drama = next(r for r in rows if r.id == 18)
    assert drama.name_en == "Drama" and drama.name_he and drama.name_he != "Drama"
