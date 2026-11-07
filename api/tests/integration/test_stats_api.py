"""GET /me/stats (plan P1-P3): the owner's own numbers, and agreement from what RLS shows."""

from types import SimpleNamespace
from uuid import UUID

import pytest
import sqlalchemy as sa

from cinecircle_api.taste.score import agreement, round_half_up
from tests.integration.conftest import (
    DANA,
    GAL,
    INSERT_GENRE,
    INSERT_TITLE_GENRE,
    NOA,
    RON,
    TEST_EMAIL_DOMAIN,
    insert_post,
    insert_series,
)

pytestmark = pytest.mark.integration

BUCKETS = list(range(1, 11))
IMDB_KEYS = ["much_lower", "lower", "same", "higher", "much_higher"]
_INSERT_TITLE = sa.text(
    "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
    " VALUES (:tmdb_id, 'movie', :name, :imdb, '{}') RETURNING id"
)


def _titles(engine, count, imdb=None, first=100) -> list[int]:
    """`count` cached movies (tmdb ids first, first+1, ...), as postgres. `imdb` is one catalogue
    rating per title, or None for none."""
    with engine.begin() as conn:
        return [
            conn.scalar(
                _INSERT_TITLE,
                {"tmdb_id": first + i, "name": f"T{first + i}", "imdb": imdb[i] if imdb else None},
            )
            for i in range(count)
        ]


def _rate(engine, author, title, rating, shared=True, season=0):
    with engine.begin() as conn:
        insert_post(conn, author, title, rating, shared, season)


def _genre(engine, genre_id, name_en, name_he, titles):
    with engine.begin() as conn:
        conn.execute(INSERT_GENRE, {"id": genre_id, "en": name_en, "he": name_he})
        for title in titles:
            conn.execute(INSERT_TITLE_GENRE, {"title": title, "genre": genre_id})


def _counts(body):
    return [b["count"] for b in body["distribution"]]


def _stats(api, who="dana", **params):
    r = api(who).get("/me/stats", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_empty_stats(api, people):
    assert _stats(api) == {
        "rated": 0,
        "distribution": [{"rating": n, "count": 0} for n in BUCKETS],
        "genres": [],
        "imdb": {
            "compared": 0,
            "mean_gap": None,
            "buckets": [{"key": k, "count": 0} for k in IMDB_KEYS],
        },
        "agreement": [],
    }


def test_one_rating_per_title_and_buckets(api, people, clean_catalog, engine):
    with engine.begin() as conn:
        series = insert_series(conn, 500, (1, 2))
    movie_a, movie_b = _titles(engine, 2)
    _rate(engine, DANA, series, 7.0, season=1)
    _rate(engine, DANA, series, 8.0, season=2)  # no season 0: the average, 7.5
    _rate(engine, DANA, movie_a, 10.0, shared=False)
    _rate(engine, DANA, movie_b, 9.5)
    body = _stats(api)
    assert body["rated"] == 3
    assert [b["rating"] for b in body["distribution"]] == BUCKETS
    assert dict(zip(BUCKETS, _counts(body), strict=True)) == {
        1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 1, 8: 0, 9: 1, 10: 1,
    }  # fmt: skip


def test_whole_series_rating_wins_over_seasons(api, people, clean_catalog, engine):
    with engine.begin() as conn:
        series = insert_series(conn, 500, (1,))
    _rate(engine, DANA, series, 3.0, season=1)
    _rate(engine, DANA, series, 9.0, season=0)
    body = _stats(api)
    assert body["rated"] == 1
    assert _counts(body)[8] == 1  # bucket 9


def test_top_genres_order_and_mean(api, people, clean_catalog, engine):
    titles = _titles(engine, 6)
    for title, rating in zip(titles, (8.0, 8.0, 7.5, 7.0, 6.0, 6.0), strict=True):
        _rate(engine, DANA, title, rating)
    t0, t1, t2, t3, t4, t5 = titles
    # Counts 3,3,2,2,1,1; a tie on count goes to the higher mean, then to the lower id.
    _genre(engine, 10, "Alpha", "אלפא", [t0, t1, t5])  # n3, mean (8+8+6)/3 = 7.33
    _genre(engine, 11, "Beta", None, [t0, t1, t2])  # n3, mean (8+8+7.5)/3 = 7.83 -> 7.8
    _genre(engine, 12, "Gamma", None, [t2, t3])  # n2, mean 7.25
    _genre(engine, 13, "Delta", None, [t3, t4])  # n2, mean 6.5
    _genre(engine, 14, "Epsilon", None, [t4])  # n1, mean 6.0
    _genre(engine, 15, "Zeta", None, [t5])  # n1, mean 6.0: cut, Epsilon has the lower id
    genres = _stats(api, lang="en")["genres"]
    assert [g["id"] for g in genres] == [11, 10, 12, 13, 14]
    assert genres[0] == {"id": 11, "name": "Beta", "count": 3, "mean": 7.8}
    assert genres[1] == {"id": 10, "name": "Alpha", "count": 3, "mean": 7.3}
    assert [g["count"] for g in genres] == [3, 3, 2, 2, 1]


def test_genre_names_are_localised(api, people, clean_catalog, engine):
    (title,) = _titles(engine, 1)
    _rate(engine, DANA, title, 8.0)
    _genre(engine, 10, "Alpha", "אלפא", [title])
    _genre(engine, 11, "Beta", None, [title])
    assert {g["id"]: g["name"] for g in _stats(api, lang="he")["genres"]} == {
        10: "אלפא",
        11: "Beta",  # no Hebrew name: English
    }
    assert {g["id"]: g["name"] for g in _stats(api, lang="en")["genres"]} == {
        10: "Alpha",
        11: "Beta",
    }
    assert _stats(api)["genres"][0]["name"] == "אלפא"  # he is the default


def test_you_vs_imdb(api, people, clean_catalog, engine):
    titles = _titles(engine, 5, imdb=[7.5, 6.0, 5.0, 4.0, 3.0])
    for title, rating in zip(titles, (5.0, 5.0, 5.0, 5.0, 6.0), strict=True):
        _rate(engine, DANA, title, rating)  # gaps -2.5, -1, 0, 1, 3
    (without_imdb,) = _titles(engine, 1, first=200)
    _rate(engine, DANA, without_imdb, 9.0)  # no IMDb rating: skipped
    body = _stats(api)
    assert body["rated"] == 6
    assert body["imdb"] == {
        "compared": 5,
        "mean_gap": 0.1,
        "buckets": [{"key": k, "count": 1} for k in IMDB_KEYS],
    }


def test_private_ratings_count_for_the_owner(api, people, clean_catalog, engine):
    (title,) = _titles(engine, 1)
    _rate(engine, GAL, title, 4.5, shared=False)
    body = _stats(api, "gal")
    assert body["rated"] == 1
    assert _counts(body)[3] == 1


def _gal_and_viewer(engine, viewer):
    """Gal shared 9, 8, 7 on t1..t3 and rated t4 privately (2); `viewer` rated all four."""
    t1, t2, t3, t4 = _titles(engine, 4)
    for title, rating in zip((t1, t2, t3), (9.0, 8.0, 7.0), strict=True):
        _rate(engine, GAL, title, rating)
    _rate(engine, GAL, t4, 2.0, shared=False)
    for title, rating in zip((t1, t2, t3, t4), (8.0, 8.0, 5.0, 10.0), strict=True):
        _rate(engine, viewer, title, rating)


def test_agreement_uses_only_visible_shared_posts(api, people, clean_catalog, engine):
    _gal_and_viewer(engine, DANA)
    # Gap on the three shared titles: |8-9|, |8-8|, |5-7|; the private t4 (|10-2|) is not seen.
    expected = round_half_up(100 * agreement(3, (1 + 0 + 2) / 3))
    assert _stats(api, "dana")["agreement"] == [
        {
            "username": "gal",
            "display_name": "Gal",
            "avatar_url": None,
            "agreement": expected,
            "common": 3,
        }
    ]
    assert _stats(api, "gal")["agreement"] == []  # Gal does not follow Dana


@pytest.mark.parametrize("viewer", [NOA, RON])  # a stranger; a pending follow request
def test_agreement_never_lists_gal_without_approval(viewer, api, people, clean_catalog, engine):
    _gal_and_viewer(engine, viewer)
    assert _stats(api, viewer.key)["agreement"] == []


def test_agreement_needs_three_common(api, people, clean_catalog, engine):
    t1, t2, t3 = _titles(engine, 3)
    for title in (t1, t2):
        _rate(engine, GAL, title, 8.0)
    _rate(engine, GAL, t3, 8.0, shared=False)  # a third title, but private
    for title in (t1, t2, t3):
        _rate(engine, DANA, title, 8.0)
    assert _stats(api)["agreement"] == []


def test_agreement_drops_after_removal(api, people, clean_catalog, engine):
    _gal_and_viewer(engine, DANA)
    assert [row["username"] for row in _stats(api)["agreement"]] == ["gal"]
    assert api("gal").delete("/followers/dana").status_code == 204
    assert _stats(api)["agreement"] == []


def _followed_account(engine, n) -> SimpleNamespace:
    """Account `fan{n}` (with a profile), followed by Dana with an approved follow."""
    uid = UUID(f"00000000-0000-4000-8000-0000000001{n:02d}")
    with engine.begin() as conn:  # the `people` cleanup deletes it by e-mail domain
        conn.execute(
            sa.text(
                "INSERT INTO auth.users (id, email, aud, role)"
                " VALUES (:id, :email, 'authenticated', 'authenticated')"
            ),
            {"id": uid, "email": f"fan{n}@{TEST_EMAIL_DOMAIN}"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO app.profiles (id, username, display_name)"
                " VALUES (:id, :username, :name)"
            ),
            {"id": uid, "username": f"fan{n}", "name": f"User {n}"},
        )
        pair = {"a": DANA.id, "b": uid}
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
    return SimpleNamespace(id=uid)


def test_agreement_top_five_order(api, people, clean_catalog, engine):
    titles = _titles(engine, 4)
    for title in titles:
        _rate(engine, DANA, title, 8.0)
    accounts = [_followed_account(engine, n) for n in range(6)]
    for account, ratings in zip(
        accounts,
        [
            (7.0, 7.0, 7.0),  # fan0: gap 1, 3 common -> 69%
            (8.0, 8.0, 8.0),  # fan1: gap 0, 3 common -> 75%, the best
            (6.5, 6.5, 9.5, 9.5),  # fan2: gap 1.5, 4 common -> also 69%, ahead of fan0 on common
            (9.0, 9.0, 9.0),  # fan3: same as fan0, so the username decides
            (5.0, 5.0, 5.0),  # fan4: gap 3 -> 58%
            (2.0, 2.0, 2.0),  # fan5: gap 6 -> 42%, sixth: cut
        ],
        strict=True,
    ):
        for title, rating in zip(titles, ratings, strict=False):
            _rate(engine, account, title, rating)
    rows = _stats(api)["agreement"]
    assert [row["username"] for row in rows] == ["fan1", "fan2", "fan0", "fan3", "fan4"]
    assert [row["common"] for row in rows] == [3, 4, 3, 3, 3]
    assert [row["agreement"] for row in rows] == [75, 69, 69, 69, 58]


def test_stats_needs_a_profile(api):
    r = api("fresh").get("/me/stats")
    assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})
