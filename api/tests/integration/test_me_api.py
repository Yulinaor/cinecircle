from uuid import UUID

import pytest
import sqlalchemy as sa

from cinecircle_api.people import repository
from tests.integration.conftest import GAL_BIO, TEST_EMAIL_DOMAIN, TestUser, as_user

pytestmark = pytest.mark.integration

_PROFILE_ROWS = sa.text(
    "SELECT (SELECT count(*) FROM app.profiles WHERE username = :u),"
    " (SELECT count(*) FROM app.profile_details d JOIN app.profiles p ON p.id = d.user_id"
    "  WHERE p.username = :u),"
    " (SELECT count(*) FROM app.user_settings s JOIN app.profiles p ON p.id = s.user_id"
    "  WHERE p.username = :u)"
)


def test_me_without_profile_returns_null(api):
    r = api("fresh").get("/me")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] is None
    assert body["email"] == "fresh@test.cinecircle.local"
    assert set(body) == {"id", "email", "profile"}


def test_me_with_profile(api, people):
    r = api("gal").get("/me")
    assert r.status_code == 200
    assert r.json() == {
        "id": str(people["gal"].id),
        "email": people["gal"].email,
        "profile": {
            "username": "gal",
            "display_name": "Gal",
            "avatar_url": None,
            "bio": GAL_BIO,
            "locale": "he",
        },
    }


def test_create_profile_then_get(api, engine):
    client = api("fresh")
    body = {"username": " Fresh_1 ", "display_name": " Fresh ", "locale": "en"}
    r = client.post("/me", json=body)
    assert r.status_code == 201
    assert r.json()["profile"] == {
        "username": "fresh_1",
        "display_name": "Fresh",
        "avatar_url": None,
        "bio": None,
        "locale": "en",
    }
    assert client.get("/me").json()["profile"]["username"] == "fresh_1"
    with engine.connect() as conn:
        assert conn.execute(_PROFILE_ROWS, {"u": "fresh_1"}).one() == (1, 1, 1)


def test_create_profile_locale_defaults_to_hebrew(api):
    r = api("fresh").post("/me", json={"username": "fresh_he", "display_name": "Fresh"})
    assert r.status_code == 201
    assert r.json()["profile"]["locale"] == "he"


def test_reserved_and_invalid_usernames_422(api):
    client = api("fresh")
    body = {"display_name": "Fresh"}
    r = client.post("/me", json={**body, "username": "me"})
    assert (r.status_code, r.json()) == (422, {"detail": "username_reserved"})
    r = client.post("/me", json={**body, "username": "Search"})
    assert (r.status_code, r.json()) == (422, {"detail": "username_reserved"})
    r = client.post("/me", json={**body, "username": "a!"})
    assert (r.status_code, r.json()) == (422, {"detail": "username_invalid"})
    r = client.post("/me", json={"username": "fresh_ok", "display_name": "  "})
    assert r.status_code == 422
    r = client.post("/me", json={"username": "fresh_ok", "display_name": "x" * 51})
    assert r.status_code == 422
    r = client.post("/me", json={"username": "fresh_ok", "display_name": "ok", "locale": "fr"})
    assert r.status_code == 422
    assert client.get("/me").json()["profile"] is None  # nothing was created


def test_username_taken_409(api):
    client = api("fresh")
    r = client.post("/me", json={"username": "gal", "display_name": "Imposter"})
    assert (r.status_code, r.json()) == (409, {"detail": "username_taken"})
    r = client.post("/me", json={"username": " GAL ", "display_name": "Imposter"})
    assert (r.status_code, r.json()) == (409, {"detail": "username_taken"})
    assert client.get("/me").json()["profile"] is None  # the failed attempt left nothing behind


def test_profile_exists_409(api):
    client = api("gal")
    r = client.post("/me", json={"username": "gal2", "display_name": "Again"})
    assert (r.status_code, r.json()) == (409, {"detail": "profile_exists"})
    r = client.post("/me", json={"username": "gal", "display_name": "Again"})
    assert (r.status_code, r.json()) == (409, {"detail": "profile_exists"})
    assert client.get("/me").json()["profile"]["display_name"] == "Gal"


def test_avatar_copied_from_google_metadata(api):
    https = api("fresh_https", user_metadata={"avatar_url": "https://lh3.example.com/a.png"})
    r = https.post("/me", json={"username": "fresh_https", "display_name": "A"})
    assert r.json()["profile"]["avatar_url"] == "https://lh3.example.com/a.png"

    ignored = {
        "fresh_http": {"avatar_url": "http://lh3.example.com/a.png"},
        "fresh_num": {"avatar_url": 5},
        "fresh_none": None,
        "fresh_str": "not-a-dict",
    }
    for key, metadata in ignored.items():
        client = api(key, user_metadata=metadata)
        r = client.post("/me", json={"username": key, "display_name": "A"})
        assert r.status_code == 201, key
        assert r.json()["profile"]["avatar_url"] is None, key


def test_patch_bio_and_locale(api):
    client = api("gal")
    r = client.patch("/me", json={"bio": "hi", "locale": "en"})
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert (profile["bio"], profile["locale"], profile["display_name"]) == ("hi", "en", "Gal")
    assert client.get("/me").json()["profile"]["bio"] == "hi"

    assert client.patch("/me", json={"bio": ""}).json()["profile"]["bio"] is None
    assert client.patch("/me", json={"bio": "x" * 300}).status_code == 200
    assert client.patch("/me", json={"bio": "x" * 301}).status_code == 422
    assert client.get("/me").json()["profile"]["bio"] == "x" * 300  # the 422 changed nothing


def test_patch_display_name(api):
    client = api("gal")
    r = client.patch("/me", json={"display_name": "  Gal B  "})
    assert r.json()["profile"]["display_name"] == "Gal B"
    for bad in ("  ", "x" * 51, None):
        assert client.patch("/me", json={"display_name": bad}).status_code == 422


def test_patch_cannot_change_username_or_send_bad_values(api):
    client = api("gal")
    assert client.patch("/me", json={"username": "galgal"}).status_code == 422
    assert client.patch("/me", json={"locale": "fr"}).status_code == 422
    assert client.patch("/me", json={"locale": None}).status_code == 422
    assert client.get("/me").json()["profile"]["username"] == "gal"


def test_patch_empty_body_changes_nothing(api):
    r = api("gal").patch("/me", json={})
    assert r.status_code == 200
    assert r.json()["profile"]["bio"] == GAL_BIO


def test_patch_without_profile_409(api):
    r = api("fresh").patch("/me", json={"bio": "x"})
    assert (r.status_code, r.json()) == (409, {"detail": "profile_required"})


@pytest.mark.usefixtures("clean_catalog")
def test_people_endpoints_require_profile(api):
    client = api("fresh")
    # Later tasks add POST /follows/{username} and /notifications to this list.
    for path in ("/users/search?q=ga", "/users/gal", "/users/gal/posts"):
        r = client.get(path)
        assert (r.status_code, r.json()) == (409, {"detail": "profile_required"}), path
    assert client.get("/titles/search", params={"q": "האודיסאה"}).status_code == 200


def test_create_profile_maps_both_unique_violations_and_keeps_the_transaction_usable(
    engine, people
):
    # The route pre-checks for an existing profile, so the primary-key path is only reachable
    # here (it is what a race between two requests of one user would hit).
    with as_user(engine, people["gal"]) as conn:
        with pytest.raises(repository.ProfileExists):
            repository.create_profile(conn, "gal_new", "Gal", None, "he")
        assert repository.get_my_profile(conn).username == "gal"  # the savepoint rolled back

    newcomer = TestUser("newcomer", UUID(int=0x5E0), "newcomer", f"newcomer@{TEST_EMAIL_DOMAIN}")
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO auth.users (id, email, aud, role) VALUES (:id, :e, 'a', 'a')"),
            {"id": newcomer.id, "e": newcomer.email},
        )
    with as_user(engine, newcomer) as conn:
        with pytest.raises(repository.UsernameTaken):
            repository.create_profile(conn, "dana", "New", None, "he")
        repository.create_profile(
            conn, "newcomer", "New", None, "he"
        )  # same transaction still works
        assert repository.get_my_profile(conn).username == "newcomer"
