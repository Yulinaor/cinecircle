import pytest
import sqlalchemy as sa

from tests.integration.conftest import (
    GAL_BIO,
    GAL_PRIVATE_OPINION,
    GAL_SHARED_OPINION,
    TEST_EMAIL_DOMAIN,
)

pytestmark = pytest.mark.integration

CARD_KEYS = {"username", "display_name", "avatar_url", "follow_state"}


def _add_user(engine, username: str, display_name: str) -> None:
    """A profile without details or settings, inserted as postgres (no RLS)."""
    with engine.begin() as conn:
        uid = conn.scalar(
            sa.text(
                "INSERT INTO auth.users (id, email, aud, role)"
                " VALUES (gen_random_uuid(), :email, 'authenticated', 'authenticated')"
                " RETURNING id"
            ),
            {"email": f"{username}@{TEST_EMAIL_DOMAIN}"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO app.profiles (id, username, display_name)"
                " VALUES (:id, :username, :name)"
            ),
            {"id": uid, "username": username, "name": display_name},
        )


def test_search_returns_card_fields_only(api):
    r = api("noa").get("/users/search", params={"q": "gal"})
    assert r.status_code == 200
    assert set(r.json()) == {"results"}
    results = r.json()["results"]
    assert [item["username"] for item in results] == ["gal"]
    assert set(results[0]) == CARD_KEYS
    assert results[0]["follow_state"] == "none"
    assert "bio" not in r.text and GAL_BIO not in r.text


def test_search_follow_states(api):
    def states(who: str, q: str) -> dict[str, str]:
        results = api(who).get("/users/search", params={"q": q}).json()["results"]
        return {i["username"]: i["follow_state"] for i in results}

    assert states("dana", "ga") == {"gal": "following"}
    assert states("ron", "gal") == {"gal": "requested"}
    assert states("gal", "gal") == {"gal": "self"}


def test_search_is_case_insensitive_and_trims(api):
    results = api("noa").get("/users/search", params={"q": " DAN "}).json()["results"]
    assert [i["username"] for i in results] == ["dana"]


def test_search_escapes_wildcards(api, engine):
    _add_user(engine, "a_b", "Underscore")
    _add_user(engine, "axb", "Wildcard Bait")
    _add_user(engine, "pct100", "100% Real")
    client = api("noa")

    def usernames(q: str) -> list[str]:
        r = client.get("/users/search", params={"q": q})
        assert r.status_code == 200
        return [i["username"] for i in r.json()["results"]]

    assert usernames("%%") == []
    assert usernames("__") == []
    assert usernames("a_b") == ["a_b"]
    assert usernames("0% R") == ["pct100"]  # a literal percent sign in a display name
    assert usernames("\\\\") == []  # a backslash is literal too, not an escape character


def test_search_matches_hebrew_display_name(api):
    results = api("gal").get("/users/search", params={"q": "נוע"}).json()["results"]
    assert [(i["username"], i["display_name"], i["follow_state"]) for i in results] == [
        ("noa", "נועה", "none")
    ]


def test_search_username_prefix_matches_come_first(api, engine):
    _add_user(engine, "zed", "Anna")  # only the display name matches
    _add_user(engine, "anna_b", "Bee")  # username prefix
    _add_user(engine, "banna", "Cee")  # username contains it, not as a prefix
    results = api("noa").get("/users/search", params={"q": "ann"}).json()["results"]
    assert [i["username"] for i in results] == ["anna_b", "banna", "zed"]


def test_search_limit_is_20(api, engine):
    for n in range(25):
        _add_user(engine, f"lim_{n:02d}", "Limit")
    results = api("noa").get("/users/search", params={"q": "lim_"}).json()["results"]
    assert [i["username"] for i in results] == [f"lim_{n:02d}" for n in range(20)]


def test_search_query_length_422(api):
    client = api("noa")
    for q in ("g", " g ", "x" * 51):
        assert client.get("/users/search", params={"q": q}).status_code == 422, q
    assert client.get("/users/search").status_code == 422
    assert client.get("/users/search", params={"q": "x" * 50}).status_code == 200


def test_user_profile_by_relation(api, gal_content):
    def view(who: str) -> dict:
        r = api(who).get("/users/gal")
        assert r.status_code == 200
        return r.json()

    details = {"bio": GAL_BIO, "post_count": 1}  # post_count counts shared posts only
    gal = view("gal")
    assert (gal["follow_state"], gal["details"]) == ("self", details)
    assert set(gal) == CARD_KEYS | {"details"}
    assert (gal["username"], gal["display_name"]) == ("gal", "Gal")
    dana = view("dana")
    assert (dana["follow_state"], dana["details"]) == ("following", details)
    noa = view("noa")
    assert (noa["follow_state"], noa["details"]) == ("none", None)
    ron = view("ron")
    assert (ron["follow_state"], ron["details"]) == ("requested", None)


def test_non_follower_response_has_no_bio_or_count(api, gal_content):
    for who in ("noa", "ron"):
        r = api(who).get("/users/gal")
        assert "bio" not in r.text and "post_count" not in r.text, who
        assert GAL_BIO not in r.text, who


def test_followed_user_details_visible_one_way_only(api, gal_content):
    # Gal follows Noa (accepted): Gal sees Noa's details, Noa still sees nothing of Gal's.
    body = api("gal").get("/users/noa").json()
    assert body["follow_state"] == "following"
    assert body["details"] == {"bio": None, "post_count": 0}
    assert api("noa").get("/users/gal").json()["details"] is None


def test_unknown_user_404(api):
    client = api("gal")
    r = client.get("/users/nobody")
    assert (r.status_code, r.json()) == (404, {"detail": "not_found"})
    assert client.get("/users/nobody/posts").status_code == 404
    assert client.get("/users/" + "x" * 80).status_code == 404


def test_uppercase_username_path_resolves(api, gal_content):
    client = api("dana")
    assert client.get("/users/GAL").json() == client.get("/users/gal").json()
    assert client.get("/users/GAL/posts").status_code == 200


def test_posts_by_relation(api, gal_content):
    r = api("gal").get("/users/gal/posts")
    assert r.status_code == 200
    assert set(r.json()) == {"posts"}
    posts = r.json()["posts"]
    # Newest first; both rows share one created_at here, so the higher id leads.
    assert [p["id"] for p in posts] == [gal_content.private_post_id, gal_content.shared_post_id]
    assert [p["is_shared"] for p in posts] == [False, True]
    assert posts[1] == {
        "id": gal_content.shared_post_id,
        "title": {
            "id": gal_content.title_ids[0],
            "media_type": "movie",
            "name": "Title 1",
            "name_lang": "en",
            "poster_url": None,
        },
        "season_number": 0,
        "rating": 9.0,
        "opinion": GAL_SHARED_OPINION,
        "contains_spoilers": False,
        "is_shared": True,
        "created_at": posts[1]["created_at"],
    }
    assert posts[0]["rating"] == 4.5 and posts[0]["opinion"] == GAL_PRIVATE_OPINION

    r = api("dana").get("/users/gal/posts")
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["posts"]] == [gal_content.shared_post_id]
    assert GAL_PRIVATE_OPINION not in r.text

    for who in ("noa", "ron"):
        r = api(who).get("/users/gal/posts")
        assert (r.status_code, r.json()) == (404, {"detail": "not_found"}), who


def test_posts_language_and_poster(api, gal_content, engine):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE app.titles SET name_he = 'כותר', poster_path = '/p.jpg' WHERE id = :id"
            ),
            {"id": gal_content.title_ids[0]},
        )
    client = api("dana")
    title = client.get("/users/gal/posts").json()["posts"][0]["title"]
    assert (title["name"], title["name_lang"]) == ("כותר", "he")
    assert title["poster_url"] == "https://image.tmdb.org/t/p/w342/p.jpg"
    title = client.get("/users/gal/posts", params={"lang": "en"}).json()["posts"][0]["title"]
    assert (title["name"], title["name_lang"]) == ("Title 1", "en")
    assert client.get("/users/gal/posts", params={"lang": "fr"}).status_code == 422
