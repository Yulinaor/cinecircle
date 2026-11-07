import pytest
import sqlalchemy as sa

from tests.integration.conftest import TEST_EMAIL_DOMAIN

pytestmark = pytest.mark.integration

ITEM_KEYS = {"id", "type", "actor", "created_at", "read", "request_pending"}


def test_notifications_shape_and_order(api):
    # Fixture `people` only: Gal has follow_requests from Dana and Ron.
    body = api("gal").get("/notifications").json()
    assert body["unread_count"] == 2
    items = body["items"]
    assert [i["actor"]["username"] for i in items] == ["ron", "dana"]  # newest first
    assert all(set(i) == ITEM_KEYS for i in items)
    assert all(i["type"] == "follow_request" and i["read"] is False for i in items)
    by_actor = {i["actor"]["username"]: i["request_pending"] for i in items}
    assert by_actor == {"ron": True, "dana": False}  # Dana's request was accepted

    dana = api("dana").get("/notifications").json()
    assert dana["unread_count"] == 1
    assert [(i["type"], i["actor"]["username"]) for i in dana["items"]] == [
        ("follow_accepted", "gal")
    ]
    assert dana["items"][0]["request_pending"] is False


def test_notifications_mark_read(api):
    gal = api("gal")
    assert gal.post("/notifications/read").status_code == 204
    body = gal.get("/notifications").json()
    assert body["unread_count"] == 0
    assert body["items"] and all(i["read"] is True for i in body["items"])
    assert gal.post("/notifications/read").status_code == 204  # idempotent

    # A new notification is unread again.
    api("noa").post("/follows/gal")
    after = gal.get("/notifications").json()
    assert after["unread_count"] == 1
    assert after["items"][0]["actor"]["username"] == "noa"
    assert after["items"][0]["read"] is False


def test_mark_read_only_touches_my_notifications(api):
    assert api("gal").post("/notifications/read").status_code == 204
    assert api("dana").get("/notifications").json()["unread_count"] == 1


def test_notifications_only_mine(api, engine):
    with engine.connect() as conn:  # as postgres: the ground truth
        gal_ids = {
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT n.id FROM app.notifications n JOIN app.profiles p"
                    " ON p.id = n.recipient_id WHERE p.username = 'gal'"
                )
            )
        }
    assert gal_ids
    for who in ("dana", "noa", "ron"):
        seen = {i["id"] for i in api(who).get("/notifications").json()["items"]}
        assert not (seen & gal_ids), who
    assert {i["id"] for i in api("gal").get("/notifications").json()["items"]} == gal_ids


def test_notifications_paged(api, engine):
    # Gal already has follow requests from Dana and Ron; 25 more users ask in one transaction,
    # so many notifications share one created_at and the cursor must break ties by id.
    with engine.begin() as conn:
        for n in range(25):
            uid = conn.scalar(
                sa.text(
                    "INSERT INTO auth.users (id, email, aud, role)"
                    " VALUES (gen_random_uuid(), :email, 'authenticated', 'authenticated')"
                    " RETURNING id"
                ),
                {"email": f"pager_{n:02d}@{TEST_EMAIL_DOMAIN}"},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO app.profiles (id, username, display_name)"
                    " VALUES (:id, :username, 'Pager')"
                ),
                {"id": uid, "username": f"pager_{n:02d}"},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO app.follows (follower_id, followee_id)"
                    " SELECT :id, id FROM app.profiles WHERE username = 'gal'"
                ),
                {"id": uid},
            )
        truth = [
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT n.id FROM app.notifications n JOIN app.profiles p"
                    " ON p.id = n.recipient_id WHERE p.username = 'gal'"
                    " ORDER BY n.created_at DESC, n.id DESC"
                )
            )
        ]
    assert len(truth) == 27

    gal = api("gal")
    first = gal.get("/notifications").json()
    assert set(first) == {"items", "unread_count", "next_cursor"}
    assert [i["id"] for i in first["items"]] == truth[:20]
    assert first["next_cursor"] is not None
    assert first["unread_count"] == 27  # counts every unread, not just this page

    second = gal.get("/notifications", params={"cursor": first["next_cursor"]}).json()
    assert [i["id"] for i in second["items"]] == truth[20:]  # no gap, no repeat
    assert second["next_cursor"] is None
    assert second["unread_count"] == 27

    r = gal.get("/notifications", params={"cursor": "garbage"})
    assert (r.status_code, r.json()) == (422, {"detail": "invalid_cursor"})
