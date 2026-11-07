"""Taste Match on the HTTP surface (plan P3, P12): the numbers of spec 03 section 4 on every route
that returns a post card, on the title page and on /me; own posts carry none; and a score uses
only the viewer's own data (plan P5).

The dataset is `spec` from conftest.py: Dana (who follows Gal) has 20 private ratings, Gal shares
a 9.0 on *The Odyssey*, and *Severance* is a series nobody posted on.
"""

import pytest
import sqlalchemy as sa

from tests.integration.conftest import GAL, NOA, RON, SCIFI, insert_post, insert_series

pytestmark = pytest.mark.integration

ODYSSEY_EN = {"fit": 76, "genres": ["Action", "Adventure"], "agreement": 74}
ODYSSEY_HE = {"fit": 76, "genres": ["אקשן", "הרפתקאות"], "agreement": 74}
SEVERANCE_EN = {"fit": 79, "genres": ["Science Fiction", "Mystery"], "agreement": None}


def _card(cards: list[dict], title_id: int) -> dict:
    (card,) = [c for c in cards if c["title"]["id"] == title_id]
    return card


def _odyssey_cards(client, spec, lang: str) -> dict[str, dict]:
    """Gal's Odyssey post as every route that returns post cards shows it to this viewer."""
    params = {"lang": lang}
    return {
        "feed": _card(client.get("/feed", params=params).json()["posts"], spec.odyssey_title_id),
        "post": client.get(f"/posts/{spec.odyssey_post_id}", params=params).json(),
        "profile": _card(
            client.get("/users/gal/posts", params=params).json()["posts"], spec.odyssey_title_id
        ),
        "title": _card(
            client.get(f"/titles/{spec.odyssey_title_id}", params=params).json()["posts"],
            spec.odyssey_title_id,
        ),
    }


def test_feed_card_carries_the_spec_score(api, spec):
    dana = api("dana")
    for route, card in _odyssey_cards(dana, spec, "en").items():
        assert card["taste"] == ODYSSEY_EN, route
    for route, card in _odyssey_cards(dana, spec, "he").items():
        assert card["taste"] == ODYSSEY_HE, route
    # Every card in the feed has the key: Gal's eight comedies are scored too.
    cards = dana.get("/feed").json()["posts"]
    assert len(cards) == 9
    assert all(set(c["taste"]) == {"fit", "genres", "agreement"} for c in cards)


def test_own_posts_have_no_taste(api, spec):
    gal = api("gal")
    for route, card in _odyssey_cards(gal, spec, "en").items():
        assert card["author"]["follow_state"] == "self", route
        assert card["taste"] is None, route
    assert all(c["taste"] is None for c in gal.get("/feed").json()["posts"])
    assert all(c["taste"] is None for c in gal.get("/users/gal/posts").json()["posts"])
    dana = api("dana")  # Dana's own (private) rating, on every route that can show it
    assert dana.get(f"/posts/{spec.dana_post_id}").json()["taste"] is None
    own = dana.get("/users/dana/posts").json()["posts"]
    assert len(own) == 20 and all(c["taste"] is None for c in own)
    page = dana.get(f"/titles/{spec.c9_title_id}").json()
    assert [p["taste"] for p in page["posts"] if p["author"]["follow_state"] == "self"] == [None]


def test_creating_a_post_returns_no_taste(api, spec):
    r = api("dana").post("/posts", json={"title_id": spec.severance_title_id, "rating": 8.0})
    assert r.status_code == 201, r.text
    assert r.json()["taste"] is None


def test_title_taste_uses_only_my_data(api, spec, engine):
    dana = api("dana")
    page = dana.get(f"/titles/{spec.severance_title_id}", params={"lang": "en"}).json()
    assert page["taste"] == SEVERANCE_EN
    assert page["posts"] == []
    he = dana.get(f"/titles/{spec.severance_title_id}", params={"lang": "he"}).json()["taste"]
    assert he == SEVERANCE_EN  # these genres have no Hebrew name in the dataset: name_en

    with engine.begin() as conn:  # Noa: one private rating, so she is scored (cold)
        insert_post(conn, NOA, spec.comedy_title_ids[0], 4.0, False)
    noa = api("noa")
    url = f"/titles/{spec.odyssey_title_id}"
    before = noa.get(url).json()["taste"]
    assert before is not None and before["agreement"] is None

    with engine.begin() as conn:  # Gal shares three more ratings, none of them Noa's business
        for n in range(3):
            title = insert_series(conn, 7000 + n, (1,))
            insert_post(conn, GAL, title, 10.0, True)
    assert noa.get(url).json()["taste"] == before
    # Dana follows Gal and sees his Odyssey post, yet her title score carries no agreement.
    assert dana.get(url).json()["taste"]["agreement"] is None


def test_me_reports_whether_taste_is_unlocked(api, spec):
    assert api("dana").get("/me").json()["taste_unlocked"] is True
    assert api("ron").get("/me").json()["taste_unlocked"] is False
    assert api("fresh").get("/me").json()["taste_unlocked"] is False  # no profile at all


def test_taste_unlocks_with_picks_or_ratings(api, spec, engine):
    with (
        engine.begin() as conn
    ):  # Ron follows Gal, accepted, but has rated nothing and picked nothing
        conn.execute(
            sa.text(
                "UPDATE app.follows SET status = 'accepted'"
                " WHERE follower_id = :a AND followee_id = :b"
            ),
            {"a": RON.id, "b": GAL.id},
        )
    ron = api("ron")
    odyssey, severance = spec.odyssey_title_id, spec.severance_title_id

    def state() -> tuple[bool, dict | None, dict | None]:
        feed = _card(ron.get("/feed").json()["posts"], odyssey)["taste"]
        title = ron.get(f"/titles/{severance}").json()["taste"]
        return ron.get("/me").json()["taste_unlocked"], feed, title

    assert state() == (False, None, None)  # locked: nothing to score with

    with engine.begin() as conn:  # one genre pick unlocks, cold
        conn.execute(
            sa.text("INSERT INTO app.user_genre_prefs (user_id, genre_id) VALUES (:u, :g)"),
            {"u": RON.id, "g": SCIFI},
        )
    unlocked, feed, title = state()
    assert unlocked is True
    assert title is not None and title["agreement"] is None
    assert feed is not None and feed["agreement"] is None

    # Four rated titles Gal also shared (3+ in common): still cold, so no agreement is shown.
    for title_id in spec.comedy_title_ids[:4]:
        r = ron.post("/posts", json={"title_id": title_id, "rating": 6.5, "is_shared": False})
        assert r.status_code == 201, r.text
    unlocked, feed, title = state()
    assert unlocked is True
    assert feed is not None and feed["agreement"] is None
    assert title is not None and title["agreement"] is None

    # The fifth rating makes the profile full: the agreement with Gal (5 common titles) shows.
    r = ron.post("/posts", json={"title_id": spec.comedy_title_ids[4], "rating": 6.5})
    assert r.status_code == 201, r.text
    unlocked, feed, title = state()
    assert unlocked is True
    assert feed is not None and isinstance(feed["agreement"], int)
    assert title is not None and title["agreement"] is None  # never for titles


def test_title_page_without_a_profile_has_no_taste(api, spec):
    r = api("fresh").get(f"/titles/{spec.severance_title_id}")
    assert r.status_code == 200, r.text
    assert r.json()["taste"] is None
