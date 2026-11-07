"""R3 end to end: the wishlist state on cards and title pages is the viewer's own, saving tells
nobody anything, nobody reaches another list, and posting marks a wanted title watched."""

import pytest

from tests.fakes import NO_HEBREW_ID, ODYSSEY_ID, SEVERANCE_ID
from tests.integration.conftest import GAL_WISHLIST_TITLE

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

NOT_FOUND = (404, {"detail": "not_found"})


def _cache(client, media_type: str, tmdb_id: int) -> dict:
    r = client.get(f"/titles/tmdb/{media_type}/{tmdb_id}", params={"lang": "he"})
    assert r.status_code == 200, r.text
    return r.json()


def _items(client, status: str = "want") -> list[dict]:
    r = client.get("/wishlist", params={"status": status})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _flag_on_title(client, title_id: int) -> bool:
    r = client.get(f"/titles/{title_id}")
    assert r.status_code == 200, r.text
    return r.json()["in_wishlist"]


def test_in_wishlist_is_the_viewers_own(api, gal_content):
    first, second = gal_content.title_ids
    shared = gal_content.shared_post_id
    # Gal's fixture item is on the second title: only Gal's own title page says so.
    assert _flag_on_title(api("gal"), second) is True
    for who in ("dana", "noa", "ron"):
        assert _flag_on_title(api(who), second) is False, who
    assert _flag_on_title(api("fresh"), second) is False  # no profile, no list

    dana, gal = api("dana"), api("gal")
    assert dana.get(f"/posts/{shared}").json()["in_wishlist"] is False
    r = dana.post("/wishlist", json={"title_id": first, "source": "post", "source_post_id": shared})
    assert r.status_code == 201, r.text

    assert dana.get(f"/posts/{shared}").json()["in_wishlist"] is True
    assert [p["in_wishlist"] for p in dana.get("/feed").json()["posts"]] == [True]
    title_posts = dana.get(f"/titles/{first}").json()
    assert title_posts["in_wishlist"] is True
    assert [p["in_wishlist"] for p in title_posts["posts"]] == [True]
    # Gal's view of the same post and title is untouched by Dana's list.
    assert gal.get(f"/posts/{shared}").json()["in_wishlist"] is False
    assert _flag_on_title(gal, first) is False
    assert [p["in_wishlist"] for p in gal.get("/feed").json()["posts"]] == [False]


def test_saving_tells_the_author_nothing(api, gal_content):
    shared = gal_content.shared_post_id
    gal = api("gal")

    def snapshot() -> list[dict]:
        paths = ("/notifications", "/users/gal", f"/posts/{shared}", "/feed")
        return [gal.get(path).json() for path in paths]

    before = snapshot()
    r = api("dana").post(
        "/wishlist",
        json={"title_id": gal_content.title_ids[0], "source": "post", "source_post_id": shared},
    )
    assert r.status_code == 201, r.text
    assert snapshot() == before


def test_cannot_touch_someone_elses_wishlist(api, gal_content):
    second = gal_content.title_ids[1]
    dana, gal = api("dana"), api("gal")

    r = dana.patch(f"/wishlist/{second}", json={"status": "watched"})
    assert (r.status_code, r.json()) == NOT_FOUND
    r = dana.delete(f"/wishlist/{second}")
    assert (r.status_code, r.json()) == NOT_FOUND
    (item,) = _items(gal)
    assert (item["title"]["id"], item["status"], item["source"]) == (second, "want", "discover")

    # Saving the same title is her own, new item: Gal's row is not hers to find or change.
    r = dana.post("/wishlist", json={"title_id": second, "source": "search"})
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "search"
    (hers,) = _items(dana)
    assert (hers["title"]["id"], hers["source"]) == (second, "search")
    (item,) = _items(gal)
    assert (item["title"]["id"], item["status"], item["source"]) == (second, "want", "discover")


@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_no_route_reads_another_wishlist(viewer, api, gal_content, gal_wish):
    client = api(viewer)
    r = client.get("/users/gal/wishlist")
    assert (r.status_code, r.json()) == NOT_FOUND
    # An owner parameter is not part of the API: it is ignored, never honoured.
    r = client.get("/wishlist", params={"owner": "gal"})
    assert r.status_code == 200, r.text
    names = [item["title"]["name"] for item in r.json()["items"]]
    if viewer == "gal":
        assert GAL_WISHLIST_TITLE in names
    else:
        assert r.json()["items"] == []
        assert GAL_WISHLIST_TITLE not in r.text


def test_posting_marks_a_wanted_title_watched(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)
    severance = _cache(dana, "series", SEVERANCE_ID)
    unlisted = _cache(dana, "movie", NO_HEBREW_ID)
    for title in (odyssey, severance):
        r = dana.post("/wishlist", json={"title_id": title["id"], "source": "search"})
        assert r.status_code == 201, r.text
    # Severance is already watched, with a clock that must not move.
    r = dana.patch(f"/wishlist/{severance['id']}", json={"status": "watched"})
    assert r.status_code == 200, r.text
    watched_at = r.json()["watched_at"]
    assert watched_at is not None

    for title in (odyssey, severance, unlisted):
        r = dana.post("/posts", json={"title_id": title["id"], "rating": 8.5})
        assert r.status_code == 201, r.text

    watched = {item["title"]["id"]: item for item in _items(dana, "watched")}
    assert set(watched) == {odyssey["id"], severance["id"]}
    assert watched[odyssey["id"]]["watched_at"] is not None
    assert watched[odyssey["id"]]["my_post"]["rating"] == 8.5
    assert watched[severance["id"]]["watched_at"] == watched_at
    assert _items(dana, "want") == []  # the unlisted title stayed off the list


def test_a_failed_post_leaves_a_wanted_title_wanted(api):
    dana = api("dana")
    odyssey = _cache(dana, "movie", ODYSSEY_ID)
    severance = _cache(dana, "series", SEVERANCE_ID)
    r = dana.post("/posts", json={"title_id": odyssey["id"], "rating": 7})
    assert r.status_code == 201, r.text
    for title in (odyssey, severance):
        r = dana.post("/wishlist", json={"title_id": title["id"], "source": "search"})
        assert r.status_code in (200, 201), r.text
    r = dana.patch(f"/wishlist/{odyssey['id']}", json={"status": "want"})
    assert r.status_code == 200, r.text
    assert {i["title"]["id"] for i in _items(dana)} == {odyssey["id"], severance["id"]}

    # 409: the title already has a post of Dana's. 422: the series has no season 99.
    r = dana.post("/posts", json={"title_id": odyssey["id"], "rating": 3})
    assert (r.status_code, r.json()["detail"]) == (409, "post_exists")
    r = dana.post("/posts", json={"title_id": severance["id"], "season_number": 99, "rating": 3})
    assert (r.status_code, r.json()) == (422, {"detail": "season_invalid"})

    assert {i["title"]["id"] for i in _items(dana)} == {odyssey["id"], severance["id"]}
    assert _items(dana, "watched") == []
