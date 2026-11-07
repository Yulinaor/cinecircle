"""Posts on a title page: what each viewer may see of the people they follow."""

import pytest

from tests.fakes import ODYSSEY_ID

pytestmark = [pytest.mark.integration]


def _posts(client, title_id: int) -> list[dict]:
    r = client.get(f"/titles/{title_id}")
    assert r.status_code == 200, r.text
    return r.json()["posts"]


def test_title_page_posts(api, gal_content):
    first, second = gal_content.title_ids
    for who in ("gal", "dana"):
        posts = _posts(api(who), first)
        assert [p["id"] for p in posts] == [gal_content.shared_post_id], who
        assert posts[0]["author"]["username"] == "gal"
    for who in ("noa", "ron"):
        assert _posts(api(who), first) == [], who

    own = _posts(api("gal"), second)
    assert [(p["id"], p["is_shared"]) for p in own] == [(gal_content.private_post_id, False)]
    for who in ("dana", "noa", "ron"):
        assert _posts(api(who), second) == [], who


def test_title_page_keeps_the_title_detail(api, gal_content):
    body = api("dana").get(f"/titles/{gal_content.title_ids[0]}").json()
    assert body["id"] == gal_content.title_ids[0] and body["name"] == "Title 1"
    assert {"tmdb_id", "ratings", "seasons", "stale", "posts", "in_wishlist", "taste"} <= set(body)


def test_title_page_without_profile(api, gal_content):
    r = api("fresh").get(f"/titles/{gal_content.title_ids[0]}")
    assert r.status_code == 200, r.text
    assert r.json()["posts"] == []


def test_unknown_title_is_still_404(api, gal_content):
    r = api("dana").get("/titles/999999")
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})


def test_tmdb_route_stays_a_plain_title_detail(api, gal_content):
    r = api("dana").get(f"/titles/tmdb/movie/{ODYSSEY_ID}")
    assert r.status_code == 200 and "posts" not in r.json()
