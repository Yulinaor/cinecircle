"""The fake-data generator (plan P7, P10, P11): deterministic, valid against the schema's CHECKs,
and shaped so the notebooks have something honest to find."""

import re
from collections import Counter
from datetime import timedelta

import pytest
import sqlalchemy as sa

from cinecircle_analysis.fakedata import (
    FAKE_DOMAIN,
    FAKE_TMDB_BASE,
    GENRES,
    START,
    WEEKS,
    Dataset,
    generate,
)
from cinecircle_analysis.load import NotLocal, assert_local, load, wipe
from cinecircle_api.db import make_engine

END = START + timedelta(weeks=WEEKS)
USERNAME = re.compile(r"^[a-z0-9_.]{3,30}$")
GENRE_IDS = {28, 12, 16, 35, 80, 99, 18, 10751, 14, 36, 27, 10402, 9648, 10749, 878, 10770, 53}
GENRE_IDS |= {10752, 37}
# Views stay before END; a save follows its view by up to 300 s; "watched" trails its post by 1 s.
MAX_EVENT_DELAY = timedelta(seconds=300)


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return generate(7)


def test_default_sizes(ds):
    assert len(ds.users) == 50
    assert len(ds.titles) == 300
    assert len(ds.posts) == 3000
    assert len(GENRES) == 19
    assert {g[0] for g in GENRES} == GENRE_IDS
    assert all(name_en and name_he for _, name_en, name_he in GENRES)


def test_deterministic(ds):
    assert generate(7) == ds
    assert generate(8) != ds


def test_small_sizes():
    small = generate(1, users=8, titles=30, ratings=150)
    assert (len(small.users), len(small.titles), len(small.posts)) == (8, 30, 150)


def test_markers(ds):
    for user in ds.users:
        assert user.email.endswith("@" + FAKE_DOMAIN)
        assert USERNAME.match(user.username), user.username
    assert len({u.username for u in ds.users}) == len(ds.users)
    assert len({u.id for u in ds.users}) == len(ds.users)
    assert [u.n for u in ds.users] == list(range(1, 51))
    for title in ds.titles:
        assert FAKE_TMDB_BASE <= title.tmdb_id < 2**31
        assert title.genre_ids and set(title.genre_ids) <= GENRE_IDS
        assert 3.0 <= title.imdb_rating <= 9.3
        assert round(title.imdb_rating, 1) == title.imdb_rating
        assert round(title.tmdb_rating, 1) == title.tmdb_rating
    assert len({t.tmdb_id for t in ds.titles}) == len(ds.titles)
    assert [t.i for t in ds.titles] == list(range(300))
    assert len({t.name_en for t in ds.titles}) == len(ds.titles)
    assert {t.media_type for t in ds.titles} == {"movie", "series"}
    assert all(u.cluster in range(4) for u in ds.users)
    assert all(set(u.picks) <= GENRE_IDS and len(u.picks) in (0, 3) for u in ds.users)


def test_ratings_are_valid(ds):
    signed_up = {u.n: u.signed_up for u in ds.users}
    keys = [(p.author, p.title) for p in ds.posts]
    assert len(set(keys)) == len(keys)
    for p in ds.posts:
        assert 1 <= p.rating <= 10 and (p.rating * 2) == int(p.rating * 2)
        assert signed_up[p.author] < p.created_at < END
        assert 0 <= p.title < len(ds.titles)


def test_follows_graph(ds):
    pairs = [(f.follower, f.followee) for f in ds.follows]
    assert len(set(pairs)) == len(pairs)
    assert all(a != b for a, b in pairs)
    out = Counter(a for a, _ in pairs)
    assert all(3 <= out[u.n] <= 15 for u in ds.users)
    accepted = sum(f.status == "accepted" for f in ds.follows) / len(ds.follows)
    assert 0.85 <= accepted <= 0.95
    signed_up = {u.n: u.signed_up for u in ds.users}
    for f in ds.follows:
        assert f.created_at > max(signed_up[f.follower], signed_up[f.followee])
        assert (f.responded_at is None) == (f.status == "pending")
        if f.responded_at:
            assert f.created_at < f.responded_at < END


def _ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    return ranks


def _spearman(xs, ys):
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return cov / (vx * vy) ** 0.5


def test_shape_is_realistic(ds):
    private = sum(not p.is_shared for p in ds.posts) / len(ds.posts)
    assert 0.15 <= private <= 0.25
    mean = sum(p.rating for p in ds.posts) / len(ds.posts)
    assert 6 <= mean <= 8
    weeks = {int((u.signed_up - START) / timedelta(weeks=1)) for u in ds.users}
    assert set(range(13)) <= weeks and max(weeks) <= 12
    imdb = [ds.titles[p.title].imdb_rating for p in ds.posts]
    assert _spearman(imdb, [p.rating for p in ds.posts]) > 0.2
    # About 70 % of users did onboarding; each has exactly three picks.
    assert 28 <= sum(bool(u.picks) for u in ds.users) <= 42


def test_wishes_and_events_reference_existing_rows(ds):
    posts = {(p.author, p.title): p for p in ds.posts}
    assert ds.wishes and ds.events
    wish_keys = [(w.owner, w.title) for w in ds.wishes]
    assert len(set(wish_keys)) == len(wish_keys)
    for w in ds.wishes:
        assert 0 <= w.title < len(ds.titles)
        if w.fit_at_save is not None:
            assert 0 <= w.fit_at_save <= 100
        assert (w.source == "post") == (w.source_post is not None)
        if w.source_post is not None:
            source = posts[w.source_post]
            assert source.title == w.title and source.is_shared
            assert source.created_at <= w.added_at
        if w.status == "watched":
            mine = posts[(w.owner, w.title)]
            assert mine.created_at > w.added_at
            assert w.watched_at == mine.created_at
        else:
            assert w.status == "want" and w.watched_at is None
            assert (w.owner, w.title) not in posts
    assert any(w.status == "watched" for w in ds.wishes)
    assert {w.source for w in ds.wishes} == {"post", "discover"}
    users = {u.n for u in ds.users}
    for e in ds.events:
        assert e.user in users
        assert START <= e.created_at < END + MAX_EVENT_DELAY
        if e.title is not None:
            assert 0 <= e.title < len(ds.titles)
        if e.post is not None:
            assert e.post in posts
        for fit in [e.props.get("fit"), *e.props.get("fits", [])]:
            assert fit is None or 0 <= fit <= 100


def test_events_shapes(ds):
    by_type = Counter(e.event_type for e in ds.events)
    assert set(by_type) == {
        "post_created",
        "post_viewed",
        "saved",
        "watched",
        "discover_opened",
        "onboarding_done",
    }
    assert by_type["post_created"] == len(ds.posts)
    for e in ds.events:
        keys = set(e.props)
        if e.event_type == "post_viewed":
            assert keys == {"fit", "surface"} and e.props["surface"] == "home"
            assert isinstance(e.props["fit"], int) and e.post is not None
            assert e.title == e.post[1]
        elif e.event_type == "saved":
            assert keys == {"fit", "source"} and e.props["source"] in ("post", "discover")
            assert (e.post is not None) == (e.props["source"] == "post")
        elif e.event_type == "discover_opened":
            assert keys == {"type", "genre", "fits"} and e.props["genre"] is None
            assert e.props["type"] in ("movie", "series")
            assert len(e.props["fits"]) <= 10
        elif e.event_type == "watched":
            assert e.props == {"via": "post"}  # a later post on a wished title, as the app logs it
        elif e.event_type == "post_created":
            assert keys == {"shared", "surface"}
            assert e.props["surface"] in ("compose", "onboarding")
        elif e.event_type == "onboarding_done":
            assert keys == {"genres", "ratings"} and e.props["genres"] == 3
    posts = {(p.author, p.title): p for p in ds.posts}
    for e in ds.events:  # an unlocked Discover page shows min(10, unrated titles of the type)
        if e.event_type == "discover_opened" and e.props["fits"]:
            rated = {
                p.title for p in ds.posts if p.author == e.user and p.created_at < e.created_at
            }
            pool = [t for t in ds.titles if t.media_type == e.props["type"] and t.i not in rated]
            assert len(e.props["fits"]) == min(10, len(pool))
    created = [e for e in ds.events if e.event_type == "post_created"]
    for e in created:
        post = posts[e.post]
        assert e.props["shared"] == post.is_shared and e.created_at == post.created_at
        assert e.title == post.title
    assert sum(e.props["surface"] == "compose" for e in created) > 2000
    assert all(e.props["shared"] is False for e in created if e.props["surface"] == "onboarding")
    watched = [e for e in ds.events if e.event_type == "watched"]
    assert len(watched) == sum(w.status == "watched" for w in ds.wishes)


def test_views_only_follow_accepted_follows(ds):
    accepted = {
        (f.follower, f.followee): f.responded_at for f in ds.follows if f.status == "accepted"
    }
    posts = {(p.author, p.title): p for p in ds.posts}
    views = [e for e in ds.events if e.event_type == "post_viewed"]
    assert len(views) > 1000
    for e in views:
        post = posts[e.post]
        assert post.is_shared and post.created_at < e.created_at
        assert accepted[(e.user, post.author)] < post.created_at


def test_saves_follow_the_view_by_seconds_to_minutes(ds):
    """A save is its own moment: 5-300 s after a view (or Discover visit) that prompted it, and
    the wishlist row carries the same time as the `saved` event. (A locked viewer's feed view
    logs no event, so those saves have no view to match.)"""
    views: dict[tuple[int, int | None], list] = {}
    for e in ds.events:
        if e.event_type == "post_viewed":
            views.setdefault((e.user, e.title), []).append(e.created_at)
        elif e.event_type == "discover_opened":
            views.setdefault((e.user, None), []).append(e.created_at)
    added = {(w.owner, w.title): w.added_at for w in ds.wishes}
    saved = [e for e in ds.events if e.event_type == "saved"]
    assert len(saved) == len(ds.wishes)
    matched = 0
    for e in saved:
        assert added[(e.user, e.title)] == e.created_at
        key = (e.user, e.title if e.props["source"] == "post" else None)
        gaps = [e.created_at - t for t in views.get(key, [])]
        if gaps:
            assert any(timedelta(seconds=5) <= g <= timedelta(seconds=300) for g in gaps)
            matched += 1
    assert matched > 0.9 * len(saved)


def test_locked_viewers_have_no_fit(ds):
    """The app logs post_viewed only when a score was shown; a locked viewer (no picks, nothing
    rated yet) sees none, and a Discover page then has no fits."""
    first_post = {}
    for p in sorted(ds.posts, key=lambda p: p.created_at):
        first_post.setdefault(p.author, p.created_at)
    picked = {u.n: bool(u.picks) for u in ds.users}
    opens = [e for e in ds.events if e.event_type == "discover_opened"]
    assert any(e.props["fits"] for e in opens)
    for e in ds.events:
        locked = not picked[e.user] and e.created_at < first_post.get(e.user, END)
        if e.event_type == "post_viewed":
            assert not locked
        if e.event_type == "discover_opened":
            assert (e.props["fits"] == []) == locked


def test_loader_refuses_remote_hosts(ds):
    engine = make_engine("postgresql+psycopg://u:p@db.example.com/x")

    def boom(*args, **kwargs):
        raise AssertionError("a connection was attempted")

    sa.event.listen(engine, "do_connect", boom)
    for call in (
        lambda: assert_local(engine),
        lambda: load(engine, ds),
        lambda: wipe(engine),
    ):
        with pytest.raises(NotLocal):
            call()
    for url in (
        "postgresql+psycopg://u:p@/x",
        "postgresql+psycopg://u:p@127.0.0.1/x?host=db.example.com",
    ):
        with pytest.raises(NotLocal):
            assert_local(make_engine(url))


def test_assert_local_refuses_a_remote_pghostaddr(monkeypatch):
    """libpq lets PGHOSTADDR override the URL's host, so a local-looking URL can still connect
    out. The environment counts like the `hostaddr=` query option."""
    engine = make_engine("postgresql+psycopg://u:p@127.0.0.1:55322/x")
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.9")
    with pytest.raises(NotLocal):
        assert_local(engine)
    for local in ("127.0.0.1", "::1", ""):  # an empty value is "unset" to libpq
        monkeypatch.setenv("PGHOSTADDR", local)
        assert_local(engine)  # does not raise
    monkeypatch.delenv("PGHOSTADDR")
    assert_local(engine)  # does not raise


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_loader_accepts_local_hosts(host):
    assert_local(make_engine(f"postgresql+psycopg://u:p@{host}:55322/x"))  # does not raise
