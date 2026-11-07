"""Events (plan P9, R3.4): what Dana does leaves owner-only rows in `app.events` with exactly the
P9 types and props, never reaches anyone else, and never becomes a notification.

The dataset is `spec` from conftest.py: Dana (who follows Gal) has 20 private ratings, Gal shares
a 9.0 on *The Odyssey* and eight comedies, and *Severance* is a series nobody posted on.
"""

import pytest
import sqlalchemy as sa

from tests.integration.conftest import DANA, GAL, NOA, RON, as_user

pytestmark = pytest.mark.integration

_EVENTS = sa.text(
    "SELECT event_type, title_id, post_id, props FROM app.events WHERE user_id = :user ORDER BY id"
)


def _events(engine, user) -> list[tuple]:
    """The user's event rows as postgres (no RLS), oldest first."""
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(_EVENTS, {"user": user.id})]


def _of_type(events: list[tuple], event_type: str) -> list[tuple]:
    return [(e[1], e[2], e[3]) for e in events if e[0] == event_type]


def test_events_are_owner_only_and_never_notify(api, engine, spec):
    gal, dana, noa = api("gal"), api("dana"), api("noa")
    before = {"gal": gal.get("/notifications").json(), "noa": noa.get("/notifications").json()}

    odyssey = spec.odyssey_title_id
    body = {"title_id": odyssey, "source": "post", "source_post_id": spec.odyssey_post_id}
    assert dana.post("/wishlist", json=body).status_code == 201
    for _ in range(2):  # the second, repeated PATCH logs nothing
        r = dana.patch(f"/wishlist/{odyssey}", json={"status": "watched"})
        assert r.status_code == 200, r.text
    body = {"title_id": spec.severance_title_id, "source": "search"}
    assert dana.post("/wishlist", json=body).status_code == 201
    feed = dana.get("/feed")
    assert feed.status_code == 200
    assert dana.get(f"/titles/{odyssey}").status_code == 200
    r = dana.post("/posts", json={"title_id": spec.severance_title_id, "rating": 8.0})
    assert r.status_code == 201, r.text
    severance_post_id = r.json()["id"]

    events = _events(engine, DANA)
    assert {e[0] for e in events} == {
        "saved",
        "watched",
        "post_created",
        "post_viewed",
        "title_viewed",
    }
    assert _of_type(events, "saved") == [
        (odyssey, spec.odyssey_post_id, {"fit": 76, "source": "post"}),
        (spec.severance_title_id, None, {"fit": 79, "source": "search"}),
    ]
    assert _of_type(events, "watched") == [
        (odyssey, None, {"via": "wishlist"}),
        (spec.severance_title_id, None, {"via": "post"}),
    ]
    assert _of_type(events, "post_created") == [
        (spec.severance_title_id, severance_post_id, {"shared": True, "surface": "compose"})
    ]
    # One post_viewed per scored card of the feed (the Odyssey and the eight comedies).
    cards = feed.json()["posts"]
    viewed = _of_type(events, "post_viewed")
    assert len(cards) == 9 and len(viewed) == 9
    by_post = {post_id: (title_id, props) for title_id, post_id, props in viewed}
    for card in cards:
        assert by_post[card["id"]] == (
            card["title"]["id"],
            {"fit": card["taste"]["fit"], "surface": "home"},
        )
    assert by_post[spec.odyssey_post_id][1] == {"fit": 76, "surface": "home"}
    assert _of_type(events, "title_viewed") == [(odyssey, None, {"fit": 79, "surface": "title"})]

    # Nobody else reads a row of Dana's, Gal (whom she follows) included.
    for other in (GAL, NOA, RON):
        with as_user(engine, other) as conn:
            assert conn.scalar(sa.text("SELECT count(*) FROM app.events")) == 0
    with as_user(engine, DANA) as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM app.events")) == len(events)

    # No event ever becomes a notification (R3.4).
    assert gal.get("/notifications").json() == before["gal"]
    assert noa.get("/notifications").json() == before["noa"]


def test_nothing_is_logged_when_nothing_happened(api, engine, spec):
    dana = api("dana")
    body = {"title_id": 987654, "source": "search"}
    assert dana.post("/wishlist", json=body).status_code == 404  # unknown title
    assert dana.patch("/wishlist/987654", json={"status": "watched"}).status_code == 404
    r = dana.post("/posts", json={"title_id": spec.c9_title_id, "rating": 7.0})
    assert r.status_code == 409  # already rated
    assert dana.get(f"/posts/{spec.odyssey_post_id}").status_code == 200  # a post page
    assert _events(engine, DANA) == []

    # Saving twice logs one `saved`; a private post logs shared False and, with no `want` item
    # on the title, no `watched`.
    body = {"title_id": spec.severance_title_id, "source": "discover"}
    assert dana.post("/wishlist", json=body).status_code == 201
    assert dana.post("/wishlist", json=body).status_code == 200
    r = dana.post(
        "/posts", json={"title_id": spec.odyssey_title_id, "rating": 6.0, "is_shared": False}
    )
    assert r.status_code == 201, r.text
    events = _events(engine, DANA)
    assert [e[0] for e in events] == ["saved", "post_created"]
    assert events[1][3] == {"shared": False, "surface": "compose"}


def test_a_locked_viewer_logs_no_view_events(api, engine, spec):
    ron = api("ron")  # no ratings, no picks: nothing is scored, so no score was shown
    assert ron.get("/feed").status_code == 200
    assert ron.get(f"/titles/{spec.odyssey_title_id}").status_code == 200
    assert _events(engine, RON) == []
    body = {"title_id": spec.odyssey_title_id, "source": "search"}
    assert ron.post("/wishlist", json=body).status_code == 201
    assert _events(engine, RON) == [
        ("saved", spec.odyssey_title_id, None, {"fit": None, "source": "search"})
    ]
