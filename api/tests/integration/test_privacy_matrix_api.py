"""The API privacy matrix (rule 00 R5): four people, one set of endpoints, sentinel strings
planted in Gal's private data. Later phases add their endpoints to ENDPOINTS."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import GAL_BIO, GAL_PRIVATE_OPINION, GAL_SHARED_OPINION

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
]
EXPECT = {  # (viewer, path) -> status; every pair not listed is 200
    ("noa", "/users/gal/posts"): 404,
    ("ron", "/users/gal/posts"): 404,
}
SECRETS = {  # sentinel -> viewers allowed to receive it in any response body
    GAL_BIO: {"gal", "dana"},
    GAL_SHARED_OPINION: {"gal", "dana"},
    GAL_PRIVATE_OPINION: {"gal"},
}
CARD_KEYS = {"username", "display_name", "avatar_url", "follow_state"}


@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_api_matrix(viewer, api, gal_content):
    client = api(viewer)
    for path in ENDPOINTS:
        r = client.get(path.format(title_id=gal_content.title_ids[0]))
        assert r.status_code == EXPECT.get((viewer, path), 200), (viewer, path, r.text)
        for secret, allowed in SECRETS.items():
            assert (secret in r.text) <= (viewer in allowed), (viewer, path, secret)
        assert r.status_code != 403, (viewer, path)


def test_unauthenticated_gets_nothing(api, gal_content):
    # Same app as a signed-in client, but a request carrying no Authorization header.
    anonymous = TestClient(api("gal").app)
    for path in ENDPOINTS:
        r = anonymous.get(path.format(title_id=gal_content.title_ids[0]))
        assert r.status_code == 401, path
        assert not any(secret in r.text for secret in SECRETS), path


@pytest.mark.parametrize("viewer", ["noa", "ron"])
def test_details_shape_for_strangers(viewer, api, gal_content):
    body = api(viewer).get("/users/gal").json()
    assert set(body) == CARD_KEYS | {"details"}
    assert body["details"] is None
