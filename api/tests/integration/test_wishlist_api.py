"""The private wishlist through the API: save, list, status, via links (fake catalogue)."""

import pytest
import sqlalchemy as sa

from cinecircle_api.wishlist import repository
from tests.fakes import ODYSSEY_ID, SEVERANCE_ID
from tests.integration.conftest import DANA, as_user

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

NOT_FOUND = (404, {"detail": "not_found"})
INVALID_CURSOR = (422, {"detail": "invalid_cursor"})


def _cache(client, media_type: str, tmdb_id: int) -> dict:
    r = client.get(f"/titles/tmdb/{media_type}/{tmdb_id}", params={"lang": "he"})
    assert r.status_code == 200, r.text
    return r.json()


def _save(client, title_id: int, source: str = "search", **extra):
    return client.post("/wishlist", json={"title_id": title_id, "source": source, **extra})


def _items(client, status: str | None = None) -> list[dict]:
    r = client.get("/wishlist", params={"status": status} if status else {})
    assert r.status_code == 200, r.text
    return r.json()["items"]


@pytest.fixture
def twenty_five_titles(people, engine) -> list[int]:
    with engine.begin() as conn:
        return [
            conn.scalar(
                sa.text(
                    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                    " VALUES (:n, 'movie', :name, '{}') RETURNING id"
                ),
                {"n": n, "name": f"Movie {n}"},
            )
            for n in range(1, 26)
        ]


def test_save_list_and_remove(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)

    r = _save(dana, odyssey["id"])
    assert r.status_code == 201, r.text
    item = r.json()
    assert set(item) == {"title", "status", "source", "via", "added_at", "watched_at", "my_post"}
    assert item["title"]["id"] == odyssey["id"]
    assert item["title"]["name"] == "האודיסאה"
    assert item["title"]["media_type"] == "movie"
    assert item["title"]["poster_url"] == odyssey["poster_url"]
    assert item["title"]["genres"] == [g["name"] for g in odyssey["genres"]]
    assert (item["status"], item["source"], item["via"]) == ("want", "search", None)
    assert (item["watched_at"], item["my_post"]) == (None, None)

    r = dana.get("/wishlist")
    assert r.status_code == 200
    assert r.json() == {"items": [item], "next_cursor": None}
    en = dana.get("/wishlist", params={"lang": "en"}).json()["items"][0]["title"]
    assert en["name_lang"] == "en" and en["name"] != "האודיסאה"

    assert dana.delete(f"/wishlist/{odyssey['id']}").status_code == 204
    assert _items(dana) == []
    r = dana.delete(f"/wishlist/{odyssey['id']}")
    assert (r.status_code, r.json()) == NOT_FOUND


def test_save_is_idempotent(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)

    first = _save(dana, odyssey["id"], "search")
    assert first.status_code == 201
    again = _save(dana, odyssey["id"], "discover")
    assert again.status_code == 200
    assert again.json() == first.json()  # the first source stays
    assert again.json()["source"] == "search"
    assert len(_items(dana)) == 1


def test_status_transitions(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)
    _save(dana, odyssey["id"])
    path = f"/wishlist/{odyssey['id']}"

    r = dana.patch(path, json={"status": "watched"})
    assert r.status_code == 200, r.text
    watched = r.json()
    assert watched["status"] == "watched" and watched["watched_at"] is not None
    assert _items(dana, "want") == []
    assert _items(dana) == []  # the default tab is Want
    assert _items(dana, "watched") == [watched]

    again = dana.patch(path, json={"status": "watched"}).json()
    assert again["watched_at"] == watched["watched_at"]  # the clock does not restart

    back = dana.patch(path, json={"status": "want"}).json()
    assert (back["status"], back["watched_at"]) == ("want", None)
    assert _items(dana, "watched") == []
    assert len(_items(dana, "want")) == 1

    for body in ({"status": "dropped"}, {"status": "x"}, {}, {"status": None}):
        assert dana.patch(path, json=body).status_code == 422, body
    assert dana.get("/wishlist", params={"status": "dropped"}).status_code == 422

    r = dana.patch("/wishlist/999999", json={"status": "watched"})
    assert (r.status_code, r.json()) == NOT_FOUND
    r = dana.patch("/wishlist/0", json={"status": "watched"})
    assert (r.status_code, r.json()) == NOT_FOUND
    assert dana.delete(f"/wishlist/{2**63}").status_code == 404


def test_save_from_post_shows_via(api, gal_content):
    dana = api("dana")
    r = _save(dana, gal_content.title_ids[0], "post", source_post_id=gal_content.shared_post_id)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["source"] == "post"
    assert item["via"] == {
        "post_id": gal_content.shared_post_id,
        "author": {
            "username": "gal",
            "display_name": "Gal",
            "avatar_url": None,
            "follow_state": "following",
        },
    }
    assert _items(dana) == [item]


def test_save_from_post_needs_a_visible_post_on_the_title(api, gal_content):
    shared, private = gal_content.shared_post_id, gal_content.private_post_id
    first, second = gal_content.title_ids
    noa, dana = api("noa"), api("dana")

    attempts = [
        (noa, first, shared),  # not a follower: the post is hidden
        (noa, first, 999_999_999),  # no such post
        (dana, second, private),  # Gal's private rating
        (dana, second, shared),  # a visible post, but on another title
    ]
    answers = []
    for client, title_id, post_id in attempts:
        r = _save(client, title_id, "post", source_post_id=post_id)
        answers.append((r.status_code, r.json()))
    assert answers == [NOT_FOUND] * 4  # identical bodies: nothing says which case it was
    assert _items(dana) == [] and _items(noa) == []


def test_unknown_title_404(api):
    r = _save(api("dana"), 999_999)
    assert (r.status_code, r.json()) == NOT_FOUND
    assert _save(api("dana"), 0).status_code == 422


def test_via_follows_post_visibility(api, gal_content):
    gal, dana = api("gal"), api("dana")
    post_id, title_id = gal_content.shared_post_id, gal_content.title_ids[0]
    assert _save(dana, title_id, "post", source_post_id=post_id).status_code == 201

    def via() -> dict | None:
        (item,) = _items(dana)
        assert item["source"] == "post"
        return item["via"]

    assert via()["post_id"] == post_id

    assert gal.patch(f"/posts/{post_id}", json={"is_shared": False}).status_code == 200
    assert via() is None  # the item stays, the link does not
    assert gal.patch(f"/posts/{post_id}", json={"is_shared": True}).status_code == 200
    assert via()["author"]["username"] == "gal"

    assert gal.delete("/followers/dana").status_code == 204
    assert via() is None
    assert dana.post("/follows/gal").status_code == 200
    assert gal.post("/follow-requests/dana/accept").status_code == 200
    assert via()["post_id"] == post_id

    assert gal.delete(f"/posts/{post_id}").status_code == 204
    assert via() is None  # the post is gone, the item stays (its source is still "post")
    assert len(_items(dana)) == 1


def test_resaving_with_a_hidden_source_post_is_404_and_changes_nothing(api, gal_content):
    gal, dana = api("gal"), api("dana")
    post_id, title_id = gal_content.shared_post_id, gal_content.title_ids[0]
    saved = _save(dana, title_id, "post", source_post_id=post_id)
    assert saved.status_code == 201
    assert gal.patch(f"/posts/{post_id}", json={"is_shared": False}).status_code == 200

    # The source is checked even though the title is already saved: the same 404 as anywhere.
    r = _save(dana, title_id, "post", source_post_id=post_id)
    assert (r.status_code, r.json()) == NOT_FOUND
    (item,) = _items(dana)
    assert (item["source"], item["status"]) == ("post", "want")
    assert item["via"] is None  # still hidden; the item itself is unchanged
    assert {k: v for k, v in item.items() if k != "via"} == {
        k: v for k, v in saved.json().items() if k != "via"
    }


def test_my_post_and_rate_loop(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)
    _save(dana, odyssey["id"])
    assert dana.patch(f"/wishlist/{odyssey['id']}", json={"status": "watched"}).status_code == 200
    assert _items(dana, "watched")[0]["my_post"] is None  # watched, not rated yet

    post = dana.post("/posts", json={"title_id": odyssey["id"], "rating": 8.5})
    assert post.status_code == 201, post.text
    (item,) = _items(dana, "watched")
    assert item["my_post"] == {"id": post.json()["id"], "rating": 8.5}


def test_my_post_is_the_newest_on_the_title_any_season(api):
    dana = api("dana")
    severance = _cache(dana, "series", SEVERANCE_ID)
    _save(dana, severance["id"])
    whole = dana.post("/posts", json={"title_id": severance["id"], "rating": 7})
    season = dana.post(
        "/posts", json={"title_id": severance["id"], "season_number": 1, "rating": 9.5}
    )
    assert whole.status_code == season.status_code == 201
    (item,) = _items(dana, "watched")  # the first post marked the wanted title watched
    assert item["my_post"] == {"id": season.json()["id"], "rating": 9.5}


@pytest.mark.parametrize("status", ["want", "watched"])
def test_wishlist_pages_ties_without_gaps(api, engine, twenty_five_titles, status):
    with engine.begin() as conn:  # ONE transaction: every row ties on added_at / watched_at
        for title_id in twenty_five_titles:
            conn.execute(
                sa.text(
                    "INSERT INTO app.wishlist_items (owner_id, title_id, source, status)"
                    " VALUES (:owner, :title, 'search', :status)"
                ),
                {"owner": DANA.id, "title": title_id, "status": status},
            )
        assert conn.scalar(sa.text("SELECT count(DISTINCT added_at) FROM app.wishlist_items")) == 1

    dana = api("dana")
    first = dana.get("/wishlist", params={"status": status}).json()
    assert len(first["items"]) == 20 and first["next_cursor"]
    second = dana.get("/wishlist", params={"status": status, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 5 and second["next_cursor"] is None

    ids = [i["title"]["id"] for i in first["items"] + second["items"]]
    assert len(set(ids)) == 25  # no repeats
    assert set(ids) == set(twenty_five_titles)  # no gaps
    assert ids == sorted(twenty_five_titles, reverse=True)  # ties break on the title id

    other = "watched" if status == "want" else "want"
    assert _items(dana, other) == []

    r = dana.get("/wishlist", params={"cursor": "garbage"})
    assert (r.status_code, r.json()) == INVALID_CURSOR


def test_wishlist_is_private(api, gal_content):
    # Gal's own item (inserted by the fixture) is invisible to everyone else.
    gal_title = gal_content.title_ids[1]
    for who in ("dana", "noa", "ron"):
        assert _items(api(who)) == []
        r = api(who).delete(f"/wishlist/{gal_title}")
        assert (r.status_code, r.json()) == NOT_FOUND
        r = api(who).patch(f"/wishlist/{gal_title}", json={"status": "watched"})
        assert (r.status_code, r.json()) == NOT_FOUND
    assert len(_items(api("gal"))) == 1


def test_wishlist_needs_a_profile(api):
    fresh = api("fresh")
    for r in (fresh.get("/wishlist"), _save(fresh, 1)):
        assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})


def test_mark_watched_on_post_and_in_wishlist_sql(api, engine):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)
    severance = _cache(dana, "series", SEVERANCE_ID)
    _save(dana, odyssey["id"])
    in_wishlist = sa.text("SELECT " + repository.IN_WISHLIST_SQL.format(title=":title"))
    with as_user(engine, DANA) as conn:
        assert conn.scalar(in_wishlist, {"title": odyssey["id"]}) is True
        assert conn.scalar(in_wishlist, {"title": severance["id"]}) is False
        # The inner alias must not capture an outer column that is itself called `w`.
        outer = sa.text(
            "SELECT w.title_id FROM (VALUES (:odyssey), (:severance)) AS w(title_id)"
            " WHERE " + repository.IN_WISHLIST_SQL.format(title="w.title_id")
        )
        rows = conn.execute(outer, {"odyssey": odyssey["id"], "severance": severance["id"]})
        assert [r.title_id for r in rows] == [odyssey["id"]]

        repository.mark_watched_on_post(conn, severance["id"])  # not on the list: a no-op
        assert repository.get_item(conn, severance["id"]) is None
        repository.mark_watched_on_post(conn, odyssey["id"])
        item = repository.get_item(conn, odyssey["id"])
        assert item is not None and item.status == "watched" and item.watched_at is not None
        repository.mark_watched_on_post(conn, odyssey["id"])  # already watched: unchanged
        again = repository.get_item(conn, odyssey["id"])
        assert again is not None and again.watched_at == item.watched_at
