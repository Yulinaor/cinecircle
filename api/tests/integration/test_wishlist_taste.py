"""Wishlist and Taste Match (plan P10, P11): `fit_at_save` is the score the saver saw, every item
carries the title formula, and `sort=fit` orders and pages by match.

The dataset is `spec` from conftest.py (see test_taste_api.py).
"""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from tests.integration.conftest import (
    ACTION,
    ADVENTURE,
    COMEDY,
    DANA,
    DRAMA,
    INSERT_TITLE_GENRE,
    MYSTERY,
    RON,
    SCIFI,
)

pytestmark = pytest.mark.integration

INVALID_CURSOR = (422, {"detail": "invalid_cursor"})
_FIT_AT_SAVE = sa.text(
    "SELECT fit_at_save FROM app.wishlist_items WHERE owner_id = :owner AND title_id = :title"
)


def _save(client, title_id: int, source: str = "search", **extra):
    return client.post("/wishlist", json={"title_id": title_id, "source": source, **extra})


def _fit_at_save(engine, owner, title_id: int) -> int | None:
    with engine.connect() as conn:  # as postgres
        return conn.scalar(_FIT_AT_SAVE, {"owner": owner.id, "title": title_id})


def test_fit_at_save_is_what_the_saver_saw(api, engine, spec):
    dana = api("dana")
    # From Gal's post: the feed formula for that post (76), not the title formula (79).
    r = _save(dana, spec.odyssey_title_id, "post", source_post_id=spec.odyssey_post_id)
    assert r.status_code == 201, r.text
    assert _fit_at_save(engine, DANA, spec.odyssey_title_id) == 76
    # From a search: the title formula.
    assert _save(dana, spec.severance_title_id, "search").status_code == 201
    assert _fit_at_save(engine, DANA, spec.severance_title_id) == 79

    # Saving the Odyssey again (200) changes nothing.
    assert _save(dana, spec.odyssey_title_id, "discover").status_code == 200
    assert _fit_at_save(engine, DANA, spec.odyssey_title_id) == 76

    # A locked viewer saw no score, so none is stored.
    ron = api("ron")
    assert _save(ron, spec.odyssey_title_id, "search").status_code == 201
    assert _fit_at_save(engine, RON, spec.odyssey_title_id) is None


def test_wishlist_items_carry_title_taste(api, spec):
    dana, ron = api("dana"), api("ron")
    expected = {"fit": 79, "genres": ["Action", "Adventure"], "agreement": None}
    body = {"title_id": spec.odyssey_title_id, "source": "post"}
    body["source_post_id"] = spec.odyssey_post_id
    saved = dana.post("/wishlist", json=body, params={"lang": "en"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["taste"] == expected  # even saved from a post: the title formula
    assert _save(ron, spec.odyssey_title_id).json()["taste"] is None

    for sort in ("recent", "fit"):
        (item,) = dana.get("/wishlist", params={"sort": sort, "lang": "en"}).json()["items"]
        assert item["taste"] == expected, sort
        (item,) = dana.get("/wishlist", params={"sort": sort, "lang": "he"}).json()["items"]
        assert item["taste"]["genres"] == ["אקשן", "הרפתקאות"], sort
        (item,) = ron.get("/wishlist", params={"sort": sort}).json()["items"]
        assert item["taste"] is None, sort
    for client, taste in ((dana, expected), (ron, None)):
        r = client.patch(
            f"/wishlist/{spec.odyssey_title_id}", json={"status": "watched"}, params={"lang": "en"}
        )
        assert r.json()["taste"] == taste


@pytest.fixture
def twenty_five_wishes(spec, engine) -> list[int]:
    """25 titles on Dana's list. Genres and ratings are chosen so that fits tie in groups; the
    last three have neither genres nor ratings. `added_at` is distinct except for four titles that
    share one stamp, so every tie-break level is used."""
    pools = [
        ([ACTION], 8.0),
        ([ACTION, ADVENTURE], 7.0),
        ([COMEDY], 9.0),
        ([DRAMA, MYSTERY], 6.0),
        ([SCIFI], None),
    ]
    base = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    ids = []
    with engine.begin() as conn:
        for n in range(25):
            genres, imdb = pools[n % 5] if n < 22 else ([], None)
            title = conn.scalar(
                sa.text(
                    "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
                    " VALUES (:n, 'movie', :name, :imdb, '{}') RETURNING id"
                ),
                {"n": 5000 + n, "name": f"Wish {n}", "imdb": imdb},
            )
            for genre in genres:
                conn.execute(INSERT_TITLE_GENRE, {"title": title, "genre": genre})
            stamp = base - timedelta(minutes=0 if n in (0, 3, 4, 5) else n)
            conn.execute(
                sa.text(
                    "INSERT INTO app.wishlist_items (owner_id, title_id, source, added_at)"
                    " VALUES (:owner, :title, 'search', :at)"
                ),
                {"owner": DANA.id, "title": title, "at": stamp},
            )
            ids.append(title)
    return ids


def _expected_order(items: list[dict]) -> list[int]:
    """Title ids by (fit desc, nulls last, added_at desc, title id desc), worked out here from
    the newest-first listing rather than by the code under test."""

    def key(item: dict):
        fit = item["taste"]["fit"] if item["taste"] else None
        return (fit is None, -(fit or 0), -datetime.fromisoformat(item["added_at"]).timestamp())

    # Title id desc is the last tie-break: sort by it first, the stable sort below keeps it.
    items = sorted(items, key=lambda i: i["title"]["id"], reverse=True)
    return [i["title"]["id"] for i in sorted(items, key=key)]


def _all_recent(client, status: str = "want") -> list[dict]:
    items, cursor = [], None
    while True:
        params = {"status": status, **({"cursor": cursor} if cursor else {})}
        page = client.get("/wishlist", params=params).json()
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return items


def test_wishlist_sorts_by_match_and_pages(api, engine, spec, twenty_five_wishes):
    dana = api("dana")
    recent = _all_recent(dana)
    assert len(recent) == 25
    fits = [i["taste"]["fit"] for i in recent]
    assert 3 <= len(set(fits)) < 25  # several values, with ties
    expected = _expected_order(recent)

    r1 = dana.get("/wishlist", params={"sort": "fit"})
    assert r1.status_code == 200, r1.text
    page1 = r1.json()
    assert len(page1["items"]) == 20 and page1["next_cursor"] == "20"
    page2 = dana.get("/wishlist", params={"sort": "fit", "cursor": "20"}).json()
    assert len(page2["items"]) == 5 and page2["next_cursor"] is None

    items = page1["items"] + page2["items"]
    got = [i["title"]["id"] for i in items]
    assert got == expected
    assert len(set(got)) == 25 and set(got) == set(twenty_five_wishes)  # no gap, no repeat
    got_fits = [i["taste"]["fit"] for i in items]
    assert got_fits == sorted(got_fits, reverse=True)

    # Past the end: an empty page.
    past = dana.get("/wishlist", params={"sort": "fit", "cursor": "25"}).json()
    assert past == {"items": [], "next_cursor": None}

    for cursor in ("x", "-1", "", " 20", "1.5", "1234567890", "20; DROP", "+5"):
        r = dana.get("/wishlist", params={"sort": "fit", "cursor": cursor})
        assert (r.status_code, r.json()) == INVALID_CURSOR, cursor
    # A fit cursor is no cursor for the newest-first list, and the other way round.
    r = dana.get("/wishlist", params={"cursor": "20"})
    assert (r.status_code, r.json()) == INVALID_CURSOR
    next_recent = dana.get("/wishlist").json()["next_cursor"]
    r = dana.get("/wishlist", params={"sort": "fit", "cursor": next_recent})
    assert (r.status_code, r.json()) == INVALID_CURSOR

    assert dana.get("/wishlist", params={"sort": "bogus"}).status_code == 422
    assert dana.get("/wishlist", params={"sort": "fit", "status": "dropped"}).status_code == 422

    # Watched works the same way.
    for title_id in twenty_five_wishes[:3]:
        assert dana.patch(f"/wishlist/{title_id}", json={"status": "watched"}).status_code == 200
    watched = dana.get("/wishlist", params={"sort": "fit", "status": "watched"}).json()
    assert watched["next_cursor"] is None
    assert {i["title"]["id"] for i in watched["items"]} == set(twenty_five_wishes[:3])
    assert all(i["status"] == "watched" for i in watched["items"])
    wants = dana.get("/wishlist", params={"sort": "fit", "cursor": "20"}).json()
    assert len(wants["items"]) == 2 and wants["next_cursor"] is None  # 22 want items now


def test_locked_viewer_sorts_by_added_then_title(api, engine, spec, twenty_five_wishes):
    with engine.begin() as conn:  # the same 25 titles on Ron's list; Ron is locked: every fit null
        conn.execute(
            sa.text(
                "INSERT INTO app.wishlist_items (owner_id, title_id, source, added_at)"
                " SELECT :ron, title_id, source, added_at FROM app.wishlist_items"
                " WHERE owner_id = :dana"
            ),
            {"ron": RON.id, "dana": DANA.id},
        )
    ron = api("ron")
    recent = _all_recent(ron)
    assert len(recent) == 25 and all(i["taste"] is None for i in recent)
    first = ron.get("/wishlist", params={"sort": "fit"}).json()
    second = ron.get("/wishlist", params={"sort": "fit", "cursor": first["next_cursor"]}).json()
    assert first["next_cursor"] == "20" and second["next_cursor"] is None
    got = [i["title"]["id"] for i in first["items"] + second["items"]]
    assert got == _expected_order(recent)
    assert len(set(got)) == 25
