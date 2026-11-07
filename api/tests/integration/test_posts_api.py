"""Compose, read, edit and delete posts through the API (fake catalogue, real database)."""

import pytest

from tests.fakes import ODYSSEY_ID, SEVERANCE_ID

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]

NOT_FOUND = (404, {"detail": "not_found"})


def _cache(client, media_type: str, tmdb_id: int) -> dict:
    r = client.get(f"/titles/tmdb/{media_type}/{tmdb_id}", params={"lang": "he"})
    assert r.status_code == 200, r.text
    return r.json()


def test_compose_movie_and_read_back(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)

    r = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 9.0, "opinion": "Epic"})
    assert r.status_code == 201, r.text
    card = r.json()
    assert set(card) == {
        "id",
        "author",
        "title",
        "season",
        "rating",
        "opinion",
        "contains_spoilers",
        "is_shared",
        "created_at",
        "updated_at",
        "edited",
        "in_wishlist",
    }
    assert card["author"] == {
        "username": "gal",
        "display_name": "Gal",
        "avatar_url": None,
        "follow_state": "self",
    }
    assert card["title"] == {
        "id": odyssey["id"],
        "media_type": "movie",
        "name": "האודיסאה",
        "name_lang": "he",
        "poster_url": odyssey["poster_url"],
        "year_start": odyssey["year_start"],
        "runtime_min": odyssey["runtime_min"],
        "genres": [g["name"] for g in odyssey["genres"]],
        "overview": odyssey["overview"],
        "overview_lang": odyssey["overview_lang"],
        "imdb_rating": odyssey["ratings"]["imdb"]["rating"],
        "tmdb_rating": odyssey["ratings"]["tmdb"],
    }
    assert card["title"]["imdb_rating"] is not None and card["title"]["genres"]
    assert card["title"]["year_start"] == 2026 and card["title"]["runtime_min"] == 173
    assert card["season"] is None
    assert (card["rating"], card["opinion"]) == (9.0, "Epic")
    assert (card["contains_spoilers"], card["is_shared"], card["edited"]) == (False, True, False)
    assert card["in_wishlist"] is False

    r = gal.get(f"/posts/{card['id']}")
    assert (r.status_code, r.json()) == (200, card)
    en = gal.get(f"/posts/{card['id']}", params={"lang": "en"}).json()
    assert en["title"]["name_lang"] == "en" and en["title"]["name"] != "האודיסאה"

    # Dana follows Gal: she reads the same post, with Gal as someone she follows.
    r = api("dana").get(f"/posts/{card['id']}")
    assert r.status_code == 200
    assert r.json()["author"]["follow_state"] == "following"


def test_season_rules(api):
    gal = api("gal")
    severance = _cache(gal, "series", SEVERANCE_ID)
    odyssey = _cache(gal, "movie", ODYSSEY_ID)

    r = gal.post("/posts", json={"title_id": severance["id"], "season_number": 1, "rating": 8})
    assert r.status_code == 201, r.text
    season = r.json()["season"]
    assert season["number"] == 1
    assert (season["name"], season["name_lang"]) == ("עונה 1", "he")  # filled from TMDB he-IL
    en = gal.get(f"/posts/{r.json()['id']}", params={"lang": "en"}).json()["season"]
    assert en["name_lang"] == "en"

    # The whole series and one of its seasons are separate posts.
    r = gal.post("/posts", json={"title_id": severance["id"], "season_number": 0, "rating": 7})
    assert r.status_code == 201, r.text
    assert r.json()["season"] is None

    for title_id, season_number in ((odyssey["id"], 1), (severance["id"], 99)):
        r = gal.post(
            "/posts", json={"title_id": title_id, "season_number": season_number, "rating": 5}
        )
        assert (r.status_code, r.json()) == (422, {"detail": "season_invalid"}), season_number
    r = gal.post("/posts", json={"title_id": severance["id"], "season_number": -1, "rating": 5})
    assert r.status_code == 422


def test_title_seasons_name_their_language(api):
    gal = api("gal")
    severance = _cache(gal, "series", SEVERANCE_ID)
    first = next(s for s in severance["seasons"] if s["season_number"] == 1)
    assert first["name_lang"] == "en"  # no Hebrew name until someone posts the season (P8)

    r = gal.post("/posts", json={"title_id": severance["id"], "season_number": 1, "rating": 8})
    assert r.status_code == 201, r.text
    for lang in ("he", "en"):
        seasons = gal.get(f"/titles/{severance['id']}", params={"lang": lang}).json()["seasons"]
        first = next(s for s in seasons if s["season_number"] == 1)
        assert (first["name"] is not None, first["name_lang"]) == (True, lang)


def test_season_text_is_filled_before_the_request_transaction(api):
    """The TMDB call must not hold the request's pooled connection open while it waits."""
    gal = api("gal")
    severance = _cache(gal, "series", SEVERANCE_ID)
    state = gal.app.state
    fill = state.title_service.fill_season_text
    checked_out = []

    def recording_fill(title_id: int, season_number: int) -> None:
        checked_out.append(state.engine.pool.checkedout())
        fill(title_id, season_number)

    state.title_service.fill_season_text = recording_fill
    r = gal.post("/posts", json={"title_id": severance["id"], "season_number": 1, "rating": 8})
    assert r.status_code == 201, r.text
    assert checked_out == [0]
    assert r.json()["season"]["name_lang"] == "he"  # still filled before the insert


def test_duplicate_is_409_with_post_id(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    first = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 9})
    assert first.status_code == 201
    r = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 3, "is_shared": False})
    expected = {"detail": "post_exists", "post_id": first.json()["id"]}
    assert (r.status_code, r.json()) == (409, expected)
    # The request transaction survived the violation: the first post is untouched.
    assert gal.get(f"/posts/{first.json()['id']}").json()["rating"] == 9.0

    # Someone else may post the same title.
    r = api("dana").post("/posts", json={"title_id": odyssey["id"], "rating": 6})
    assert r.status_code == 201


def test_unknown_title_404(api):
    r = api("gal").post("/posts", json={"title_id": 999999, "rating": 5})
    assert (r.status_code, r.json()) == NOT_FOUND


def test_bad_bodies_422(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    for body in (
        {"title_id": odyssey["id"], "rating": "9.5"},
        {"title_id": odyssey["id"], "rating": 9.25},
        {"title_id": odyssey["id"], "rating": True},
        {"title_id": odyssey["id"], "rating": 5, "opinion": "א" * 501},
        {"rating": 5},
    ):
        assert gal.post("/posts", json=body).status_code == 422, body


def test_edit_marks_edited_and_keeps_position(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    card = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 9, "opinion": "Epic"})
    card = card.json()

    r = gal.patch(f"/posts/{card['id']}", json={})
    assert (r.status_code, r.json()) == (200, card)  # nothing sent, nothing changed

    r = gal.patch(f"/posts/{card['id']}", json={"rating": 8.5, "opinion": ""})
    assert r.status_code == 200, r.text
    edited = r.json()
    assert (edited["rating"], edited["opinion"], edited["edited"]) == (8.5, None, True)
    assert edited["created_at"] == card["created_at"]
    assert (edited["contains_spoilers"], edited["is_shared"]) == (False, True)  # not sent
    assert gal.get(f"/posts/{card['id']}").json() == edited

    r = gal.patch(f"/posts/{card['id']}", json={"contains_spoilers": True, "is_shared": False})
    assert (r.json()["contains_spoilers"], r.json()["is_shared"]) == (True, False)
    assert r.json()["rating"] == 8.5

    for body in ({"title_id": 2}, {"season_number": 1}, {"rating": None}, {"rating": 0.5}):
        assert gal.patch(f"/posts/{card['id']}", json=body).status_code == 422, body
    assert (gal.patch("/posts/999999", json={"rating": 5}).status_code) == 404


def test_delete_then_404(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    post_id = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 9}).json()["id"]
    r = gal.delete(f"/posts/{post_id}")
    assert (r.status_code, r.content) == (204, b"")
    r = gal.get(f"/posts/{post_id}")
    assert (r.status_code, r.json()) == NOT_FOUND
    r = gal.delete(f"/posts/{post_id}")
    assert (r.status_code, r.json()) == NOT_FOUND
    # Deleted means it can be posted again.
    assert gal.post("/posts", json={"title_id": odyssey["id"], "rating": 9}).status_code == 201


def test_private_post_visible_to_owner_only(api):
    gal = api("gal")
    odyssey = _cache(gal, "movie", ODYSSEY_ID)
    r = gal.post("/posts", json={"title_id": odyssey["id"], "rating": 4, "is_shared": False})
    assert r.status_code == 201 and r.json()["is_shared"] is False
    post_id = r.json()["id"]
    assert gal.get(f"/posts/{post_id}").status_code == 200
    for viewer in ("dana", "noa", "ron"):
        r = api(viewer).get(f"/posts/{post_id}")
        assert (r.status_code, r.json()) == NOT_FOUND, viewer


def test_malformed_post_id_404(api):
    gal = api("gal")
    for path in ("/posts/abc", "/posts/0", "/posts/99999999999999999999"):
        r = gal.get(path)
        assert (r.status_code, r.json()) == NOT_FOUND, path


def test_posts_need_a_profile(api):
    client = api("fresh")
    expected = (409, {"detail": "profile_required"})
    r = client.post("/posts", json={"title_id": 1, "rating": 5})
    assert (r.status_code, r.json()) == expected
    for method, body in (("GET", None), ("PATCH", {"rating": 5}), ("DELETE", None)):
        r = client.request(method, "/posts/1", json=body)
        assert (r.status_code, r.json()) == expected, method
