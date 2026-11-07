"""GET /discover (plan P1-P5, P9, P10): sections of external titles, the viewer's own seeds and
Taste, the `discover_opened` event, and the proof that no CineCircle user content reaches it.

Fixture lists (tests/fixtures/tmdb): six movies per movie list, six series per tv list;
`recommendations_movie_*` is served for any movie id and is empty for series.
"""

from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from cinecircle_api.catalog.parse import GenreRow
from cinecircle_api.db import in_user_transaction, user_transaction
from cinecircle_api.taste.context import TasteContext
from tests.fakes import ODYSSEY_ID
from tests.integration.conftest import (
    DANA,
    GAL,
    GAL_PRIVATE_OPINION,
    GAL_SHARED_OPINION,
    NOA,
    as_user,
    claims_for,
    insert_post,
)
from tests.integration.test_privacy_matrix_api import SECRETS

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

RESIDENT_EVIL_ID = 1423191  # second-listed trending movie in the fixture
FIRST_RECOMMENDATION_ID = 87101  # Terminator Genisys: first of recommendations_movie_en
ACTION = 28

_INSERT_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
    " VALUES (:tmdb_id, :media_type, :name, :imdb, '{}') RETURNING id"
)
_DISCOVER_EVENTS = sa.text(
    "SELECT user_id, title_id, post_id, props FROM app.events"
    " WHERE event_type = 'discover_opened' ORDER BY id"
)


def _title(engine, tmdb_id, name, media_type="movie", imdb=None) -> int:
    with engine.begin() as conn:
        return conn.scalar(
            _INSERT_TITLE,
            {"tmdb_id": tmdb_id, "media_type": media_type, "name": name, "imdb": imdb},
        )


def _rate(engine, author, title_id, rating, shared=False) -> int:
    with engine.begin() as conn:
        return insert_post(conn, author, title_id, rating, shared)


def _sections(body: dict, key: str) -> list[dict]:
    return [s for s in body["sections"] if s["key"] == key]


def _items(body: dict) -> list[dict]:
    return [item for section in body["sections"] for item in section["items"]]


def _without(node, *keys):
    """`node` with every key in `keys` removed, at any depth."""
    if isinstance(node, dict):
        return {k: _without(v, *keys) for k, v in node.items() if k not in keys}
    if isinstance(node, list):
        return [_without(v, *keys) for v in node]
    return node


def _all_keys(node) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _all_keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _all_keys(v)}
    return set()


def _tmdb(client):
    return client.app.state.discover_service._tmdb


# ===== Sections =====


def test_discover_sections(api):
    body = api("dana").get("/discover", params={"lang": "en"}).json()
    assert body["type"] == "movie" and body["stale"] is False and body["fetched_at"]
    assert [s["key"] for s in body["sections"]] == ["trending", "top_rated"]
    assert all(s["seed"] is None for s in body["sections"])
    trending, top_rated = body["sections"]
    assert len(trending["items"]) == len(top_rated["items"]) == 6
    assert {"name": "The Odyssey", "tmdb_id": ODYSSEY_ID} == {
        k: trending["items"][1][k] for k in ("name", "tmdb_id")
    }
    for item in _items(body):
        assert set(item) == {
            "tmdb_id",
            "media_type",
            "name",
            "name_lang",
            "poster_url",
            "year",
            "genres",
            "tmdb_rating",
            "imdb_rating",
            "taste",
        }
        assert item["media_type"] == "movie" and item["name_lang"] == "en"
        assert item["tmdb_rating"] is not None
        assert item["genres"] and all(g["name"] for g in item["genres"])
        assert item["imdb_rating"] is None  # nothing is cached in app.titles
        assert item["taste"] is None  # Dana has rated nothing: locked
    odyssey = trending["items"][1]
    assert odyssey["genres"] == [
        {"id": 12, "name": "Adventure"},
        {"id": 28, "name": "Action"},
        {"id": 14, "name": "Fantasy"},
    ]
    assert odyssey["poster_url"].startswith("https://image.tmdb.org/t/p/")
    assert [g["id"] for g in body["genres"]] == sorted(
        {g["id"] for i in _items(body) for g in i["genres"]}
    )


def test_series_use_the_tv_lists(api):
    body = api("dana").get("/discover", params={"type": "series", "lang": "en"}).json()
    assert body["type"] == "series"
    assert [s["key"] for s in body["sections"]] == ["trending", "top_rated"]
    assert all(i["media_type"] == "series" for i in _items(body))
    assert 247718 in {i["tmdb_id"] for i in _items(body)}  # trending_tv_en


def test_hebrew_names_and_genres(api):
    body = api("dana").get("/discover").json()  # lang defaults to he
    odyssey = next(i for i in _items(body) if i["tmdb_id"] == ODYSSEY_ID)
    assert odyssey["name"] == "האודיסאה" and odyssey["name_lang"] == "he"
    assert {g["name"] for g in odyssey["genres"]} == {"הרפתקאות", "אקשן", "פנטזיה"}


def test_section_parameter(api):
    dana = api("dana")
    only = dana.get("/discover", params={"section": "top_rated", "lang": "en"}).json()
    assert [s["key"] for s in only["sections"]] == ["top_rated"]
    # No seeds, so "because" alone is an empty page, not an error and not a TMDB call.
    none = dana.get("/discover", params={"section": "because", "lang": "en"})
    assert none.status_code == 200 and none.json()["sections"] == []
    assert none.json()["fetched_at"] is None and none.json()["stale"] is False
    assert dana.get("/discover", params={"section": "nope"}).status_code == 422
    assert dana.get("/discover", params={"type": "game"}).status_code == 422
    assert dana.get("/discover", params={"genre": 0}).status_code == 422


def test_cached_titles_show_their_imdb_rating(api, engine):
    _title(engine, ODYSSEY_ID, "The Odyssey", imdb=8.4)
    body = api("dana").get("/discover", params={"lang": "en"}).json()
    ratings = {i["tmdb_id"]: i["imdb_rating"] for i in _items(body)}
    assert ratings[ODYSSEY_ID] == 8.4
    assert ratings[RESIDENT_EVIL_ID] is None


def test_genre_filter(api):
    dana = api("dana")
    full = dana.get("/discover", params={"lang": "en"}).json()
    body = dana.get("/discover", params={"lang": "en", "genre": ACTION}).json()
    items = _items(body)
    assert items and len(items) < len(_items(full))
    assert all(ACTION in {g["id"] for g in i["genres"]} for i in items)
    assert body["genres"] == full["genres"]  # the chips come from all items, not the filtered
    assert ACTION in {g["id"] for g in body["genres"]}
    # A genre nothing has: no items, the page is still fine.
    none = dana.get("/discover", params={"genre": 999999, "lang": "en"}).json()
    assert _items(none) == [] and none["genres"] == full["genres"]


def test_discover_without_profile(api, engine):
    r = api("fresh").get("/discover", params={"lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert [s["key"] for s in body["sections"]] == ["trending", "top_rated"]
    assert all(i["taste"] is None for i in _items(body))
    with engine.connect() as conn:
        assert conn.execute(_DISCOVER_EVENTS).all() == []


def test_discover_unavailable(api):
    client = api("dana")
    _tmdb(client).fail = True
    r = client.get("/discover", params={"lang": "en"})
    assert (r.status_code, r.json()) == (503, {"detail": "discover_unavailable"})


def test_stale_page_when_tmdb_goes_down(api, engine):
    client = api("dana")
    first = client.get("/discover", params={"lang": "en"}).json()
    with engine.begin() as conn:  # the cache is 7 hours old
        conn.execute(sa.text("UPDATE app.discover_cache SET fetched_at = now() - interval '7 h'"))
    _tmdb(client).fail = True
    body = client.get("/discover", params={"lang": "en"}).json()
    assert body["stale"] is True and body["fetched_at"] < first["fetched_at"]
    assert body["sections"] == first["sections"]


# ===== No user content =====


def test_discover_has_no_user_content(api, gal_content, engine):
    # Two trending titles are cached; Dana has rated something (so her Taste is on), under 8.
    odyssey = _title(engine, ODYSSEY_ID, "The Odyssey", imdb=8.4)
    resident_evil = _title(engine, RESIDENT_EVIL_ID, "Resident Evil")
    other = _title(engine, 7001, "Dana's own movie")
    _rate(engine, DANA, other, 6.0)
    with engine.begin() as conn:  # state A: Dana does not follow Gal
        conn.execute(
            sa.text("DELETE FROM app.follows WHERE follower_id = :a AND followee_id = :b"),
            {"a": DANA.id, "b": GAL.id},
        )
    dana, noa = api("dana"), api("noa")

    def fetch(client) -> dict:
        r = client.get("/discover", params={"lang": "en"})
        assert r.status_code == 200
        assert not any(secret in r.text for secret in SECRETS)
        assert not _all_keys(r.json()) & {
            "posts",
            "author",
            "username",
            "follow_state",
            "in_wishlist",
            "display_name",
        }
        return r.json()

    not_following = fetch(dana)
    assert any(i["taste"] for i in _items(not_following))  # the score exists, so it was compared

    pair = {"a": DANA.id, "b": GAL.id}
    with engine.begin() as conn:  # state B: Dana follows Gal (insert, then accept, as in real use)
        conn.execute(
            sa.text("INSERT INTO app.follows (follower_id, followee_id) VALUES (:a, :b)"), pair
        )
        conn.execute(
            sa.text(
                "UPDATE app.follows SET status = 'accepted'"
                " WHERE follower_id = :a AND followee_id = :b"
            ),
            pair,
        )
    following = fetch(dana)

    # State C: Gal shares an opinion on the trending Odyssey and rates Resident Evil privately.
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO app.posts (author_id, title_id, rating, opinion, is_shared)"
                " VALUES (:gal, :title, :rating, :opinion, :shared)"
            ),
            [
                {
                    "gal": GAL.id,
                    "title": odyssey,
                    "rating": 9.0,
                    "opinion": GAL_SHARED_OPINION,
                    "shared": True,
                },
                {
                    "gal": GAL.id,
                    "title": resident_evil,
                    "rating": 2.0,
                    "opinion": GAL_PRIVATE_OPINION,
                    "shared": False,
                },
            ],
        )
    after_posts = fetch(dana)

    # Positive control: the same data is visible to Dana elsewhere, so a leak could have shown.
    with_posts = dana.get(f"/titles/{odyssey}")
    assert GAL_SHARED_OPINION in with_posts.text
    assert GAL_PRIVATE_OPINION not in with_posts.text

    assert _without(not_following, "taste") == _without(following, "taste")
    assert _without(not_following, "taste") == _without(after_posts, "taste")
    assert not_following == following == after_posts  # her Taste uses only her own ratings

    # A stranger's page is the same except for what is personal.
    def public(body):
        return _without(
            {**body, "sections": [s for s in body["sections"] if s["key"] != "because"]}, "taste"
        )

    assert public(fetch(noa)) == public(after_posts)


# ===== Taste, seeds, events =====


def test_taste_on_discover_uses_only_my_data(api, spec, engine):
    dana = api("dana")
    body = dana.get("/discover", params={"lang": "en"}).json()
    trending = _sections(body, "trending")[0]["items"]
    odyssey = next(i for i in trending if i["tmdb_id"] == ODYSSEY_ID)
    # Adventure .78, Action .82, Fantasy .70 (unrated) -> G .767; Q = 8.0 / 10 -> 77.67 -> 78.
    assert odyssey["taste"] == {"fit": 78, "genres": ["Action", "Adventure"], "agreement": None}

    with as_user(engine, DANA) as conn:
        ctx = TasteContext.load(conn)
        for item in _items(body):
            genres = [GenreRow(g["id"], g["name"], None) for g in item["genres"]]
            expected = ctx.for_title(genres, item["imdb_rating"], item["tmdb_rating"], "en")
            assert expected is not None
            assert item["taste"] == expected.model_dump(), item["tmdb_id"]
    assert all(i["taste"]["agreement"] is None for i in _items(body))

    # Noa has rated nothing: locked, no scores at all. Same items though.
    noa = api("noa").get("/discover", params={"lang": "en"}).json()
    assert all(i["taste"] is None for i in _items(noa))
    external = [s for s in body["sections"] if s["key"] != "because"]  # Dana also has seeds
    assert [i["tmdb_id"] for i in _items(noa)] == [
        i["tmdb_id"] for s in external for i in s["items"]
    ]


def test_seeds_are_the_viewers_own(api, engine):
    dune = _title(engine, 5001, "Dana Nine")
    gal_ten = _title(engine, 5002, "Gal Ten")
    rated_rec = _title(engine, FIRST_RECOMMENDATION_ID, "Terminator Genisys")
    series = _title(engine, 5003, "Dana's Series", media_type="series")
    low = _title(engine, 5004, "Dana Seven")
    _rate(engine, DANA, dune, 9.0)
    _rate(engine, DANA, rated_rec, 5.0)  # rated low: not a seed, but dropped from her recs
    _rate(engine, DANA, series, 9.5)  # a series: not a seed on the movie page
    _rate(engine, DANA, low, 7.5)  # under 8: not a seed
    _rate(engine, GAL, gal_ten, 10.0, shared=True)  # Dana follows Gal: still not her seed
    dana = api("dana")

    body = dana.get("/discover", params={"lang": "en"}).json()
    assert [s["key"] for s in body["sections"]] == ["trending", "top_rated", "because"]
    because = body["sections"][2]
    assert because["seed"] == {
        "title_id": dune,
        "name": "Dana Nine",
        "name_lang": "en",
        "rating": 9.0,
    }
    ids = [i["tmdb_id"] for i in because["items"]]
    assert ids and FIRST_RECOMMENDATION_ID not in ids  # she rated it
    assert len(ids) == 5  # the other five of the recorded six
    assert all(i["taste"] for i in because["items"])  # she has rated titles: unlocked

    # Gal's 10 is a seed for Gal only; Noa (nothing rated) has no section.
    gal = api("gal").get("/discover", params={"lang": "en"}).json()
    assert [s["seed"]["name"] for s in _sections(gal, "because")] == ["Gal Ten"]
    noa = api("noa").get("/discover", params={"lang": "en"}).json()
    assert _sections(noa, "because") == []

    # Series page: the series is the seed; the fake has no recommendations for tv, so no section.
    tv = dana.get("/discover", params={"type": "series", "lang": "en"}).json()
    assert _sections(tv, "because") == []

    # Lowering the only rating >= 8 below 8 removes the section.
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE app.posts SET rating = 7.5 WHERE author_id = :a AND title_id = :t"),
            {"a": DANA.id, "t": dune},
        )
    again = dana.get("/discover", params={"lang": "en"}).json()
    assert [s["key"] for s in again["sections"]] == ["trending", "top_rated"]


def test_seeds_are_the_top_two_by_rating_then_newest(api, engine):
    ids = {
        name: _title(engine, 6000 + n, name)
        for n, name in enumerate(["nine-old", "eight", "ten", "nine-new"])
    }
    for name, rating in [("nine-old", 9.0), ("eight", 8.0), ("ten", 10.0), ("nine-new", 9.0)]:
        _rate(engine, DANA, ids[name], rating)  # inserted in this order: nine-new is the newest 9
    body = api("dana").get("/discover", params={"lang": "en"}).json()
    seeds = [(s["seed"]["name"], s["seed"]["rating"]) for s in _sections(body, "because")]
    assert seeds == [("ten", 10.0), ("nine-new", 9.0)]


def test_a_series_rating_counts_once_per_title(api, engine):
    # Whole-series rating 9 plus two low season ratings: one rating per title, the whole-series one.
    series = _title(engine, 5100, "Mixed", media_type="series")
    with engine.begin() as conn:
        for season in (1, 2):
            conn.execute(
                sa.text("INSERT INTO app.title_seasons (title_id, season_number) VALUES (:t, :s)"),
                {"t": series, "s": season},
            )
        insert_post(conn, DANA, series, 9.0, False, season=0)
        insert_post(conn, DANA, series, 4.0, False, season=1)
        insert_post(conn, DANA, series, 5.0, False, season=2)
    client = api("dana")
    _tmdb(client).calls.clear()
    client.get("/discover", params={"type": "series", "lang": "en"})
    assert _tmdb(client).calls["recommendations"] == 1  # one seed, asked once per locale used


def test_discover_opened_event(api, spec, engine):
    dana = api("dana")
    first = dana.get("/discover", params={"lang": "en"}).json()
    second = dana.get("/discover", params={"lang": "en", "genre": ACTION, "type": "movie"}).json()
    with engine.connect() as conn:
        rows = conn.execute(_DISCOVER_EVENTS).all()
    assert len(rows) == 2  # one per request
    assert {r.user_id for r in rows} == {DANA.id}
    assert all(r.title_id is None and r.post_id is None for r in rows)
    fits = lambda body: [i["taste"]["fit"] for i in _items(body) if i["taste"]]  # noqa: E731
    assert rows[0].props == {"type": "movie", "genre": None, "fits": fits(first)}
    assert rows[1].props == {"type": "movie", "genre": ACTION, "fits": fits(second)}
    assert rows[0].props["fits"] and len(rows[1].props["fits"]) < len(rows[0].props["fits"])

    with as_user(engine, DANA) as conn:
        assert len(conn.execute(_DISCOVER_EVENTS).all()) == 2
    with as_user(engine, NOA) as conn:  # owner-only
        assert conn.execute(_DISCOVER_EVENTS).all() == []


def test_a_locked_viewer_logs_no_fits(api, engine):
    api("noa").get("/discover", params={"lang": "en"})
    with engine.connect() as conn:
        (row,) = conn.execute(_DISCOVER_EVENTS).all()
    assert row.props == {"type": "movie", "genre": None, "fits": []}


# ===== TMDB never runs inside a user transaction =====


def _record_transactions(tmdb) -> list[tuple[str, bool]]:
    seen: list[tuple[str, bool]] = []

    def wrap(name):
        original = getattr(tmdb, name)

        def recorded(*args, **kwargs):
            seen.append((name, in_user_transaction()))
            return original(*args, **kwargs)

        setattr(tmdb, name, recorded)

    for name in (
        "search_multi",
        "title_details",
        "season_details",
        "genre_list",
        "trending",
        "top_rated",
        "recommendations",
        "reviews",
    ):
        wrap(name)
    return seen


def test_no_tmdb_call_inside_a_user_transaction(api, spec):
    dana = api("dana")  # the spec Dana has rated 9s and 10s: she has seeds
    seen = _record_transactions(_tmdb(dana))

    r = dana.get("/discover")  # cold cache, lang he: both locales are fetched
    assert r.status_code == 200 and _sections(r.json(), "because")
    r = dana.get(f"/titles/{spec.odyssey_title_id}/reviews")
    assert r.status_code == 200 and r.json()["reviews"]

    called = {name for name, _ in seen}
    assert {"trending", "top_rated", "recommendations", "genre_list", "reviews"} <= called
    assert [call for call in seen if call[1]] == []


def test_the_recorder_sees_a_user_transaction(engine):
    # Positive control for the test above: the flag is up exactly while the transaction is open.
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    claims = SimpleNamespace(raw=claims_for(DANA))
    assert in_user_transaction() is False
    with user_transaction(request, claims) as conn:
        assert in_user_transaction() is True
        assert conn.scalar(sa.text("SELECT auth.uid()")) == DANA.id
    assert in_user_transaction() is False
    with pytest.raises(RuntimeError):
        with user_transaction(request, claims):
            raise RuntimeError("boom")
    assert in_user_transaction() is False


def test_chips_come_only_from_items_that_are_shown(api, engine):
    # WarGames (860) is the only recommendation with Drama (18) and the only one Dana rated, so it
    # is dropped from her "because" section; Drama must not stay behind as a chip.
    seed = _title(engine, 7001, "Seed Nine")
    wargames = _title(engine, 860, "WarGames")
    _rate(engine, DANA, seed, 9.0)
    _rate(engine, DANA, wargames, 5.0)
    dana = api("dana")
    body = dana.get("/discover", params={"lang": "en", "section": "because"}).json()
    assert [s["key"] for s in body["sections"]] == ["because"]
    assert 860 not in [i["tmdb_id"] for i in _items(body)]
    drama = 18
    assert drama not in {g["id"] for i in _items(body) for g in i["genres"]}
    assert drama not in {g["id"] for g in body["genres"]}
    assert {g["id"] for g in body["genres"]} == {g["id"] for i in _items(body) for g in i["genres"]}
