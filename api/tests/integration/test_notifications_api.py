import pytest
import sqlalchemy as sa

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
