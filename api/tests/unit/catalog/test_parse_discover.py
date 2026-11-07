import copy

from cinecircle_api.catalog.parse import ListItem, ReviewRecord, excerpt, parse_list, parse_reviews
from tests.fixtures import load


def test_parse_list_movie_and_tv():
    movies = parse_list(load("tmdb/trending_movie_en"), "movie")
    assert len(movies) == 6
    assert movies[1] == ListItem(
        tmdb_id=1368337,
        media_type="movie",
        name="The Odyssey",
        poster_path=movies[1].poster_path,
        year=2026,
        genre_ids=(12, 28, 14),
        vote_average=8.0,
    )
    assert movies[1].poster_path and movies[1].poster_path.startswith("/")
    assert all(m.media_type == "movie" and m.year for m in movies)

    series = parse_list(load("tmdb/trending_tv_en"), "series")
    assert series[0].tmdb_id == 247718
    assert series[0].media_type == "series"
    assert series[0].name == "MobLand"
    assert series[0].year == 2025  # first_air_date, not release_date
    assert series[0].genre_ids == (80, 18)
    assert series[0].vote_average == 8.618


def test_parse_list_keeps_the_non_hebrew_name_of_a_hebrew_request():
    names = [i.name for i in parse_list(load("tmdb/trending_movie_he"), "movie")]
    assert "Model Citizen" in names  # TMDB falls back to a non-Hebrew name: the parser keeps it
    assert any(n and "א" <= n[0] <= "ת" for n in names)


def test_parse_list_skips_broken_items():
    raw = copy.deepcopy(load("tmdb/trending_movie_en"))
    raw["results"][0].pop("id")
    raw["results"][1]["vote_average"] = 0
    raw["results"][2]["title"] = ""
    raw["results"][3]["release_date"] = ""
    raw["results"][4]["poster_path"] = None
    raw["results"][5].pop("genre_ids")
    raw["results"].append("garbage")
    items = parse_list(raw, "movie")
    assert [i.tmdb_id for i in items] == [r["id"] for r in raw["results"][1:6]]
    by_id = {i.tmdb_id: i for i in items}
    assert by_id[raw["results"][1]["id"]].vote_average is None  # 0 = nobody voted
    assert by_id[raw["results"][2]["id"]].name is None
    assert by_id[raw["results"][3]["id"]].year is None
    assert by_id[raw["results"][4]["id"]].poster_path is None
    assert by_id[raw["results"][5]["id"]].genre_ids == ()


def test_parse_list_without_results():
    assert parse_list({}, "movie") == []
    assert parse_list({"results": None}, "series") == []


def test_excerpt_cuts_on_a_word():
    text = " ".join(f"word{n}" for n in range(1000))
    assert len(text) > 5000
    out = excerpt(text)
    assert len(out) <= 300
    assert out.endswith("…")
    last_word = out[:-1].split(" ")[-1]
    assert last_word in text.split(" ")  # no half word
    assert text.startswith(out[:-1].rstrip())


def test_excerpt_short_text_is_untouched_and_has_no_ellipsis():
    assert excerpt("A fine film.") == "A fine film."
    assert excerpt("x" * 300) == "x" * 300
    assert excerpt("a b", limit=3) == "a b"


def test_excerpt_with_one_giant_word_still_fits():
    out = excerpt("x" * 5000)
    assert len(out) <= 300 and out.endswith("…")


def test_excerpt_strips_markup():
    assert excerpt("<b>Great</b> **film**") == "Great film"
    assert excerpt("__Bold__ and *italic* and _under_") == "Bold and italic and under"
    assert excerpt("See [the trailer](https://example.com/x) now") == "See the trailer now"
    assert excerpt("a<br/>b <a href='https://x.test'>link</a>\r\n\r\n  end") == "a b link end"
    assert excerpt("<p>one</p><p>two</p> Tom &amp; Jerry") == "one two Tom & Jerry"
    assert excerpt("1 < 2 and 4 > 3") == "1 < 2 and 4 > 3"
    assert excerpt("snake_case_name stays") == "snake_case_name stays"
    assert excerpt("2 * 3 = 6") == "2 * 3 = 6"


def test_excerpt_counts_the_ellipsis_in_the_limit():
    out = excerpt("aaaa bbbb cccc dddd", limit=10)
    assert out == "aaaa bbbb…"
    assert len(out) <= 10


def test_excerpt_hebrew_and_markup_cut():
    text = "**" + " ".join(["שלום עולם"] * 100) + "**"
    out = excerpt(text, limit=50)
    assert len(out) <= 50 and out.endswith("…") and "*" not in out


def test_parse_reviews():
    reviews = parse_reviews(load("tmdb/reviews_movie"))
    assert len(reviews) == 3
    first = reviews[0]
    assert isinstance(first, ReviewRecord)
    assert first.source_review_id == "51ea49fe760ee35ab1463677"
    assert first.author_name == "NeoBrowser"
    assert first.url == "https://www.themoviedb.org/review/51ea49fe760ee35ab1463677"
    assert first.author_rating == 10.0
    assert first.language is None
    assert first.excerpt.startswith("Get this: what if all we know as reality")
    assert len(first.excerpt) <= 300 and first.excerpt.endswith("…")  # the 4,000-char one
    assert reviews[1].author_rating == 9.5


def test_parse_reviews_edge_cases():
    raw = copy.deepcopy(load("tmdb/reviews_movie"))
    r = raw["results"]
    r[0]["author_details"]["rating"] = None
    r[1]["url"] = "http://www.themoviedb.org/review/insecure"
    r[2]["content"] = "<p>  </p>"
    r.append(
        {
            "id": "x1",
            "author": "",
            "author_details": {"username": "bob"},
            "content": "hi",
            "url": "https://www.themoviedb.org/x",
        }
    )
    r.append({"id": "x0", "author": " ", "content": "no name", "url": "https://t.test/n"})
    r.append(
        {
            "id": "x2",
            "author": "Ann",
            "content": "ok",
            "url": "https://t.test/x",
            "iso_639_1": "he",
        }
    )
    r.append({"author": "NoId", "content": "hi", "url": "https://t.test/y"})
    out = parse_reviews(raw)
    assert [x.source_review_id for x in out] == ["51ea49fe760ee35ab1463677", "x1", "x2"]
    assert out[0].author_rating is None
    assert out[1].author_name == "bob"  # author_details.username when `author` is empty
    assert out[1].author_rating is None
    assert out[2].language == "he"
    assert parse_reviews({}) == []
