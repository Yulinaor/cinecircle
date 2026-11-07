import pytest

pytestmark = pytest.mark.integration

CARD_KEYS = {"username", "display_name", "avatar_url", "follow_state"}


def _usernames(r) -> list[str]:
    assert r.status_code == 200
    return [u["username"] for u in r.json()["users"]]


def _from(items: list[dict], username: str, type_: str) -> list[dict]:
    return [i for i in items if i["actor"]["username"] == username and i["type"] == type_]


# Fixture `people`: Dana -> Gal accepted, Ron -> Gal pending. `gal_content` adds Gal's posts and
# Gal -> Noa accepted (a follow_request to Noa, then a follow_accepted to Gal).


def test_request_accept_lifecycle(api, gal_content):
    noa, gal = api("noa"), api("gal")
    assert noa.get("/users/gal").json()["details"] is None

    r = noa.post("/follows/gal")
    assert (r.status_code, r.json()) == (200, {"follow_state": "requested"})
    assert noa.get("/users/gal").json()["follow_state"] == "requested"

    body = gal.get("/notifications").json()
    assert set(body) == {"items", "unread_count", "next_cursor"}
    # Unread for Gal: follow_request from Dana, Ron and Noa, plus follow_accepted from Noa (the
    # `gal_content` follow).
    assert body["unread_count"] == 4
    newest = body["items"][0]
    assert newest["type"] == "follow_request"
    assert newest["actor"]["username"] == "noa"
    assert newest["request_pending"] is True
    assert newest["read"] is False
    assert set(newest["actor"]) == CARD_KEYS
    assert newest["actor"]["follow_state"] == "following"  # Gal follows Noa

    accepted = gal.post("/follow-requests/noa/accept")
    assert accepted.status_code == 200
    assert set(accepted.json()) == CARD_KEYS
    assert accepted.json()["username"] == "noa"

    noa_items = noa.get("/notifications").json()["items"]
    assert noa_items[0]["type"] == "follow_accepted"
    assert noa_items[0]["actor"]["username"] == "gal"
    # Noa also still has the notification of Gal's own (already accepted) request: nothing pending.
    assert all(i["request_pending"] is False for i in noa_items)

    # The request notification stays, but is no longer actionable.
    after = _from(gal.get("/notifications").json()["items"], "noa", "follow_request")
    assert [i["request_pending"] for i in after] == [False]

    assert noa.get("/users/gal").json()["details"] is not None
    posts = noa.get("/users/gal/posts")
    assert posts.status_code == 200
    assert len(posts.json()["posts"]) == 1


def test_accept_twice_is_a_noop(api):
    gal = api("gal")
    first = gal.post("/follow-requests/ron/accept")
    assert (first.status_code, first.json()["username"]) == (200, "ron")
    before = api("ron").get("/notifications").json()["items"]
    assert len(before) == 1
    assert gal.post("/follow-requests/ron/accept").status_code == 200
    assert api("ron").get("/notifications").json()["items"] == before

    # Dana was accepted before the test began: accepting again is fine and sends nothing new.
    dana_before = api("dana").get("/notifications").json()["items"]
    assert gal.post("/follow-requests/dana/accept").status_code == 200
    assert api("dana").get("/notifications").json()["items"] == dana_before


def test_request_is_idempotent(api):
    noa, gal = api("noa"), api("gal")
    assert noa.post("/follows/gal").json() == {"follow_state": "requested"}
    assert noa.post("/follows/gal").json() == {"follow_state": "requested"}

    assert _usernames(gal.get("/me/follow-requests")).count("noa") == 1
    assert len(_from(gal.get("/notifications").json()["items"], "noa", "follow_request")) == 1

    r = api("dana").post("/follows/gal")
    assert (r.status_code, r.json()) == (200, {"follow_state": "following"})
    assert len(_from(gal.get("/notifications").json()["items"], "dana", "follow_request")) == 1


def test_follow_self_422_and_unknown_404(api):
    gal = api("gal")
    r = gal.post("/follows/gal")
    assert (r.status_code, r.json()) == (422, {"detail": "cannot_follow_self"})
    assert gal.delete("/follows/gal").status_code == 204  # nothing to remove, and not an error
    for method, path in (
        ("POST", "/follows/nobody"),
        ("DELETE", "/follows/nobody"),
        ("POST", "/follow-requests/nobody/accept"),
        ("DELETE", "/follow-requests/nobody"),
        ("DELETE", "/followers/nobody"),
        ("POST", "/follows/" + "x" * 31),
    ):
        r = gal.request(method, path)
        assert (r.status_code, r.json()) == (404, {"detail": "not_found"}), (method, path)


def test_username_in_path_is_case_insensitive(api):
    r = api("noa").post("/follows/GAL")
    assert (r.status_code, r.json()) == (200, {"follow_state": "requested"})


def test_cancel_removes_request_and_notification(api):
    ron, gal = api("ron"), api("gal")
    assert _from(gal.get("/notifications").json()["items"], "ron", "follow_request")

    assert ron.delete("/follows/gal").status_code == 204
    items = gal.get("/notifications").json()["items"]
    assert not [i for i in items if i["actor"]["username"] == "ron"]
    assert gal.get("/me/follow-requests").json() == {"users": []}
    assert ron.delete("/follows/gal").status_code == 204  # nothing left: still 204


def test_decline_is_silent_and_can_request_again(api):
    ron, gal = api("ron"), api("gal")
    assert gal.delete("/follow-requests/ron").status_code == 204

    assert ron.get("/notifications").json() == {"items": [], "unread_count": 0, "next_cursor": None}
    assert ron.get("/users/gal").json()["follow_state"] == "none"
    assert ron.post("/follows/gal").json() == {"follow_state": "requested"}


def test_remove_follower_hides_content_again(api, gal_content):
    dana = api("dana")
    assert dana.get("/users/gal/posts").status_code == 200

    assert api("gal").delete("/followers/dana").status_code == 204
    assert dana.get("/users/gal").json()["details"] is None
    assert dana.get("/users/gal/posts").status_code == 404
    assert dana.get("/users/gal").json()["follow_state"] == "none"


def test_unfollow(api, gal_content):
    dana = api("dana")
    assert dana.delete("/follows/gal").status_code == 204
    assert dana.get("/users/gal").json()["details"] is None
    assert dana.get("/users/gal/posts").status_code == 404


def test_wrong_state_actions_404(api):
    gal = api("gal")
    for method, path in (
        ("POST", "/follow-requests/noa/accept"),  # Noa never asked
        ("DELETE", "/follow-requests/noa"),
        ("DELETE", "/follow-requests/dana"),  # Dana's request is already accepted
        ("DELETE", "/followers/ron"),  # Ron is only pending
        ("DELETE", "/followers/noa"),
        ("POST", "/follow-requests/gal/accept"),  # oneself
    ):
        r = gal.request(method, path)
        assert (r.status_code, r.json()) == (404, {"detail": "not_found"}), (method, path)
    # Nothing above changed anything.
    assert _usernames(gal.get("/me/followers")) == ["dana"]
    assert _usernames(gal.get("/me/follow-requests")) == ["ron"]


def test_a_follower_cannot_accept_their_own_request(api):
    # Ron is pending towards Gal; only Gal may accept. Ron "accepting" Gal finds no request.
    assert api("ron").post("/follow-requests/gal/accept").status_code == 404
    assert _usernames(api("gal").get("/me/follow-requests")) == ["ron"]


def test_lists(api):
    gal = api("gal")
    assert _usernames(gal.get("/me/followers")) == ["dana"]
    assert _usernames(gal.get("/me/follow-requests")) == ["ron"]
    assert _usernames(gal.get("/me/following")) == []

    ron_following = api("ron").get("/me/following").json()["users"]
    assert [(u["username"], u["follow_state"]) for u in ron_following] == [("gal", "requested")]
    dana_following = api("dana").get("/me/following").json()["users"]
    assert [(u["username"], u["follow_state"]) for u in dana_following] == [("gal", "following")]
    assert all(set(u) == CARD_KEYS for u in ron_following + dana_following)

    # A pending follower is not in the followers list; it only appears under requests.
    assert api("ron").get("/me/followers").json() == {"users": []}
    assert api("noa").get("/me/follow-requests").json() == {"users": []}


def test_following_includes_both_states_and_requests_are_newest_first(api, gal_content):
    gal = api("gal")
    assert _usernames(gal.get("/me/following")) == ["noa"]
    api("noa").post("/follows/gal")
    gal.post("/follows/ron")  # Gal asks Ron: pending
    states = {u["username"]: u["follow_state"] for u in gal.get("/me/following").json()["users"]}
    assert states == {"noa": "following", "ron": "requested"}
    assert _usernames(gal.get("/me/follow-requests")) == ["noa", "ron"]


def test_no_route_to_someone_elses_lists(api):
    noa = api("noa")
    assert noa.get("/users/gal/followers").status_code == 404
    assert noa.get("/users/gal/following").status_code == 404
