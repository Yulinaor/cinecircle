"""Home feed, paged profile posts and visibility changing under a reader (fake catalogue)."""

import pytest
import sqlalchemy as sa

from tests.fakes import ODYSSEY_ID, SEVERANCE_ID
from tests.integration.conftest import GAL

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

NOT_FOUND = (404, {"detail": "not_found"})
INVALID_CURSOR = (422, {"detail": "invalid_cursor"})


def _ids(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [post["id"] for post in response.json()["posts"]]


def _cache(client, media_type: str, tmdb_id: int) -> dict:
    r = client.get(f"/titles/tmdb/{media_type}/{tmdb_id}", params={"lang": "he"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def twenty_five_posts(people, engine) -> list[int]:
    """25 movies and 25 shared Gal posts, all inserted in ONE transaction: one created_at."""
    with engine.begin() as conn:
        title_ids = [
            conn.scalar(
                sa.text(
                    "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                    " VALUES (:n, 'movie', :name, '{}') RETURNING id"
                ),
                {"n": n, "name": f"Movie {n}"},
            )
            for n in range(1, 26)
        ]
        post_ids = [
            conn.scalar(
                sa.text(
                    "INSERT INTO app.posts (author_id, title_id, rating, is_shared)"
                    " VALUES (:gal, :title, 7, true) RETURNING id"
                ),
                {"gal": GAL.id, "title": title_id},
            )
            for title_id in title_ids
        ]
        stamps = conn.scalar(sa.text("SELECT count(DISTINCT created_at) FROM app.posts"))
    assert stamps == 1  # the premise: every post ties on created_at
    return post_ids


def test_feed_is_own_and_followees_shared_posts(api, gal_content):
    shared = gal_content.shared_post_id
    assert _ids(api("dana").get("/feed")) == [shared]
    assert _ids(api("gal").get("/feed")) == [shared]  # her private rating is not on Home
    assert _ids(api("noa").get("/feed")) == []
    assert _ids(api("ron").get("/feed")) == []  # a pending request shows nothing
    body = api("dana").get("/feed").json()
    assert set(body) == {"posts", "next_cursor"} and body["next_cursor"] is None
    assert body["posts"][0]["author"]["follow_state"] == "following"


def test_feed_needs_a_profile(api, gal_content):
    r = api("fresh").get("/feed")
    assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})


def test_feed_type_filter(api):
    gal, dana = api("gal"), api("dana")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    severance = _cache(gal, "series", SEVERANCE_ID)
    movie_post = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 8}).json()["id"]
    series_post = gal.post("/posts", json={"title_id": severance["id"], "rating": 9}).json()["id"]

    assert _ids(dana.get("/feed")) == [series_post, movie_post]
    assert _ids(dana.get("/feed", params={"type": "all"})) == [series_post, movie_post]
    assert _ids(dana.get("/feed", params={"type": "series"})) == [series_post]
    assert _ids(dana.get("/feed", params={"type": "movie"})) == [movie_post]
    assert dana.get("/feed", params={"type": "book"}).status_code == 422


def test_feed_language(api, gal_content):
    he = api("dana").get("/feed").json()["posts"][0]["title"]
    en = api("dana").get("/feed", params={"lang": "en"}).json()["posts"][0]["title"]
    assert (he["name"], he["name_lang"]) == ("Title 1", "en")  # no Hebrew name: English fallback
    assert en["name_lang"] == "en"
    assert api("dana").get("/feed", params={"lang": "fr"}).status_code == 422


def test_feed_pages_ties_without_gaps(api, twenty_five_posts):
    dana = api("dana")
    first = dana.get("/feed").json()
    assert len(first["posts"]) == 20 and first["next_cursor"]
    second = dana.get("/feed", params={"cursor": first["next_cursor"]}).json()
    assert len(second["posts"]) == 5 and second["next_cursor"] is None

    ids = [p["id"] for p in first["posts"] + second["posts"]]
    assert len(set(ids)) == 25  # no repeats
    assert set(ids) == set(twenty_five_posts)  # no gaps
    assert ids == sorted(twenty_five_posts, reverse=True)  # ties break on id, newest first

    typed = dana.get("/feed", params={"type": "movie", "cursor": first["next_cursor"]}).json()
    assert [p["id"] for p in typed["posts"]] == ids[20:] and typed["next_cursor"] is None
    series = dana.get("/feed", params={"type": "series", "cursor": first["next_cursor"]})
    assert _ids(series) == []

    for junk in ("garbage", "!!!", first["next_cursor"][:-6]):
        r = dana.get("/feed", params={"cursor": junk})
        assert (r.status_code, r.json()) == INVALID_CURSOR, junk


def test_profile_posts_paged(api, twenty_five_posts):
    def pages(client) -> list[int]:
        first = client.get("/users/gal/posts").json()
        assert len(first["posts"]) == 20 and first["next_cursor"]
        second = client.get("/users/gal/posts", params={"cursor": first["next_cursor"]}).json()
        assert len(second["posts"]) == 5 and second["next_cursor"] is None
        return [p["id"] for p in first["posts"] + second["posts"]]

    owner, follower = pages(api("gal")), pages(api("dana"))
    assert owner == follower  # same order for both viewers
    assert len(set(owner)) == 25 and set(owner) == set(twenty_five_posts)  # no gaps, no repeats
    assert owner == sorted(twenty_five_posts, reverse=True)

    r = api("dana").get("/users/gal/posts", params={"cursor": "garbage"})
    assert (r.status_code, r.json()) == INVALID_CURSOR
    r = api("noa").get("/users/gal/posts")
    assert (r.status_code, r.json()) == NOT_FOUND


def test_visibility_follows_share_and_follow_changes(api, gal_content):
    gal, dana = api("gal"), api("dana")
    post_id, title_id = gal_content.shared_post_id, gal_content.title_ids[0]

    def dana_sees() -> tuple[bool, bool, bool, bool]:
        title_posts = [p["id"] for p in dana.get(f"/titles/{title_id}").json()["posts"]]
        return (
            _ids(dana.get("/feed")) == [post_id],
            _ids(dana.get("/users/gal/posts")) == [post_id],
            title_posts == [post_id],
            dana.get(f"/posts/{post_id}").status_code == 200,
        )

    assert dana_sees() == (True, True, True, True)

    assert gal.patch(f"/posts/{post_id}", json={"is_shared": False}).status_code == 200
    r = dana.get(f"/posts/{post_id}")
    assert (r.status_code, r.json()) == NOT_FOUND
    assert _ids(dana.get("/feed")) == []
    assert _ids(dana.get("/users/gal/posts")) == []
    assert dana.get(f"/titles/{title_id}").json()["posts"] == []

    assert gal.patch(f"/posts/{post_id}", json={"is_shared": True}).status_code == 200
    assert dana_sees() == (True, True, True, True)

    assert gal.delete("/followers/dana").status_code == 204
    assert _ids(dana.get("/feed")) == []
    r = dana.get("/users/gal/posts")
    assert (r.status_code, r.json()) == NOT_FOUND
    assert dana.get(f"/titles/{title_id}").json()["posts"] == []
    r = dana.get(f"/posts/{post_id}")
    assert (r.status_code, r.json()) == NOT_FOUND
