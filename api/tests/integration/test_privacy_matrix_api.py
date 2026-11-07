"""The API privacy matrix (rule 00 R5): four people, one set of endpoints, sentinel strings
planted in Gal's private data. Later phases add their endpoints to ENDPOINTS."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import (
    GAL_BIO,
    GAL_PRIVATE_OPINION,
    GAL_SHARED_OPINION,
    GAL_WISHLIST_TITLE,
)

pytestmark = pytest.mark.integration

ENDPOINTS = [
    "/users/gal",
    "/users/gal/posts",
    "/users/search?q=gal",
    "/me",
    "/me/followers",
    "/me/following",
    "/me/follow-requests",
    "/notifications",
    "/titles/{title_id}",
    "/titles/{title2}",
    "/feed",
    "/feed?type=movie",
    "/posts/{shared}",
    "/posts/{private}",
    "/wishlist",
    "/wishlist?status=watched",
    "/onboarding",
]
EXPECT = {  # (viewer, path) -> status; every pair not listed is 200
    ("noa", "/users/gal/posts"): 404,
    ("ron", "/users/gal/posts"): 404,
    ("dana", "/posts/{private}"): 404,
    ("noa", "/posts/{shared}"): 404,
    ("noa", "/posts/{private}"): 404,
    ("ron", "/posts/{shared}"): 404,
    ("ron", "/posts/{private}"): 404,
}
SECRETS = {  # sentinel -> viewers allowed to receive it in any response body
    GAL_BIO: {"gal", "dana"},
    GAL_SHARED_OPINION: {"gal", "dana"},
    GAL_PRIVATE_OPINION: {"gal"},
    GAL_WISHLIST_TITLE: {"gal"},
}
CARD_KEYS = {"username", "display_name", "avatar_url", "follow_state"}


def _url(path: str, content) -> str:
    return path.format(
        title_id=content.title_ids[0],
        title2=content.title_ids[1],
        shared=content.shared_post_id,
        private=content.private_post_id,
    )


@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_api_matrix(viewer, api, gal_content, gal_wish):
    client = api(viewer)
    bodies = []
    for path in ENDPOINTS:
        r = client.get(_url(path, gal_content))
        assert r.status_code == EXPECT.get((viewer, path), 200), (viewer, path, r.text)
        for secret, allowed in SECRETS.items():
            assert (secret in r.text) <= (viewer in allowed), (viewer, path, secret)
        assert r.status_code != 403, (viewer, path)
        bodies.append(r.text)
    # Positive control: absence alone would also pass if the data were empty or hidden from all.
    seen = {s for s in SECRETS if any(s in body for body in bodies)}
    assert seen == {s for s, allowed in SECRETS.items() if viewer in allowed}, viewer


def test_unauthenticated_gets_nothing(api, gal_content, gal_wish):
    # Same app as a signed-in client, but a request carrying no Authorization header.
    anonymous = TestClient(api("gal").app)
    for path in ENDPOINTS:
        r = anonymous.get(_url(path, gal_content))
        assert r.status_code == 401, path
        assert not any(secret in r.text for secret in SECRETS), path


@pytest.mark.parametrize("viewer", ["noa", "ron"])
def test_details_shape_for_strangers(viewer, api, gal_content):
    body = api(viewer).get("/users/gal").json()
    assert set(body) == CARD_KEYS | {"details"}
    assert body["details"] is None


@pytest.mark.parametrize("viewer", ["dana", "noa", "ron"])
def test_cannot_edit_or_delete_someone_elses_post(viewer, api, gal_content):
    client = api(viewer)
    posts = (gal_content.shared_post_id, gal_content.private_post_id)
    before = {post_id: api("gal").get(f"/posts/{post_id}").json() for post_id in posts}
    for post_id in posts:
        r = client.patch(f"/posts/{post_id}", json={"rating": 1})
        assert (r.status_code, r.json()) == (404, {"detail": "not_found"}), (viewer, post_id)
        r = client.delete(f"/posts/{post_id}")
        assert (r.status_code, r.json()) == (404, {"detail": "not_found"}), (viewer, post_id)
    gal = api("gal")
    for post_id in posts:
        r = gal.get(f"/posts/{post_id}")
        assert r.status_code == 200, post_id
        assert r.json() == before[post_id], post_id
