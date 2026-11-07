"""Offline Taste Match evaluation (spec 03 section 7, plan P12): rebuild each fit from the history
before the post, compare it with the rating that followed, on a time split."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from cinecircle_analysis.fakedata import (
    Dataset,
    FakeEvent,
    FakeFollow,
    FakePost,
    FakeTitle,
    FakeUser,
    generate,
)
from cinecircle_analysis.replay import (
    Evaluation,
    Prediction,
    evaluate,
    feed_score,
    fit_line,
    imdb_only,
    mae,
    predictions,
    profile_from,
    save_rate_by_bucket,
    spearman,
    title_score,
    tune_feed,
    tune_title,
)
from cinecircle_api.taste import score

T0 = datetime(2026, 6, 1, tzinfo=UTC)
ACTION, ADVENTURE, DRAMA, MYSTERY, SCIFI, COMEDY = 28, 12, 18, 9648, 878, 35


def at(hours: float) -> datetime:
    return T0 + timedelta(hours=hours)


# ===== profile_from ===============================================================================


def test_profile_from_matches_the_worked_example():
    """Phase 5's spec 03 section 4 dataset: Dana's 20 ratings, no picks."""
    titles = {}
    ratings = []

    def rate(genre, rating, count=1):
        for _ in range(count):
            t = len(titles)
            titles[t] = [genre]
            ratings.append((t, rating))

    rate(ACTION, 10, 2)
    rate(ADVENTURE, 9, 2)
    rate(DRAMA, 7, 4)
    rate(MYSTERY, 9)
    rate(SCIFI, 9.5, 2)
    rate(COMEDY, 5, 8)
    rate(COMEDY, 6)
    profile = profile_from(ratings, titles, [])
    assert profile.rated == 20
    assert profile.mean_all == pytest.approx(0.70)
    assert profile.state == "full"
    assert profile.picked == frozenset()
    assert profile.genres[ACTION].n == 2
    assert profile.genres[ACTION].mean == pytest.approx(1.0)
    assert profile.genres[COMEDY].n == 9
    assert score.affinity(profile, ACTION) == pytest.approx(0.82, abs=0.005)
    assert score.affinity(profile, ADVENTURE) == pytest.approx(0.78, abs=0.005)
    assert score.affinity(profile, DRAMA) == pytest.approx(0.70, abs=0.005)


def test_profile_from_empty_and_multi_genre():
    empty = profile_from([], {}, [ACTION])
    assert (empty.rated, empty.mean_all, empty.state) == (0, None, "cold")
    assert profile_from([], {}, []).state == "locked"
    both = profile_from([(0, 8.0)], {0: [ACTION, DRAMA]}, [])
    assert both.genres[ACTION].mean == pytest.approx(0.8)
    assert both.genres[DRAMA].n == 1


# ===== Metrics ====================================================================================


def test_spearman_known_values():
    assert spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(0.866, abs=0.001)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert math.isnan(spearman([2, 2, 2], [1, 2, 3]))
    assert math.isnan(spearman([1], [1]))


def test_fit_line_and_mae():
    assert fit_line([0, 1, 2, 3], [1, 3, 5, 7]) == pytest.approx((1.0, 2.0))
    assert fit_line([2, 2], [3, 5]) == (4.0, 0.0)  # no spread in x: the mean
    assert mae([1, 2], [2, 4]) == 1.5


# ===== predictions ================================================================================


def _user(n: int, picks: tuple[int, ...] = ()) -> FakeUser:
    return FakeUser(
        n=n,
        id=None,  # type: ignore[arg-type]
        email=f"fake{n:02d}@fake.cinecircle.local",
        username=f"fake_{n}",
        display_name=str(n),
        cluster=0,
        signed_up=T0,
        picks=picks,
    )


def _title(i: int, genres=(ACTION,), imdb=8.0, tmdb=7.0) -> FakeTitle:
    return FakeTitle(i, 2_000_000_000 + i, "movie", f"T{i}", f"T{i}", 2020, genres, imdb, tmdb)


def _post(author: int, title: int, rating: float, hours: float, shared: bool = True) -> FakePost:
    return FakePost(author, title, rating, shared, at(hours))


def _follow(follower: int, followee: int, accepted_at: float | None = -1.0) -> FakeFollow:
    status = "accepted" if accepted_at is not None else "pending"
    return FakeFollow(
        follower,
        followee,
        status,
        at(-2),
        at(accepted_at) if accepted_at is not None else None,
    )


def _dataset(users, follows, posts, titles=8) -> Dataset:
    return Dataset(
        users=tuple(users),
        titles=tuple(_title(i) for i in range(titles)),
        follows=tuple(follows),
        posts=tuple(sorted(posts, key=lambda p: p.created_at)),
        wishes=(),
        events=(),
    )


def test_predictions_use_only_the_past():
    """V (1) rates titles 0-4 (hours 1-5), then 5 (hour 10) and 6 (hour 11). V follows A (2) and
    C (3). A shared title 0 early and title 5 at hour 7, title 6 only at hour 13; C shared
    title 5 at hour 12. So V's title-5 prediction has S from A's post alone (C's is later) and
    the agreement uses only the one title both had rated by then; the title-6 one has no S."""
    posts = [_post(1, t, r, t + 1) for t, r in enumerate([8, 6, 7, 9, 5])]
    posts += [_post(1, 5, 7.0, 10), _post(1, 6, 7.0, 11)]
    posts += [_post(2, 0, 6.0, 0.5), _post(2, 5, 9.0, 7), _post(2, 6, 9.0, 13)]
    posts += [_post(3, 5, 1.0, 12)]
    ds = _dataset([_user(1), _user(2), _user(3)], [_follow(1, 2), _follow(1, 3)], posts)
    by_key = {(p.user, p.title): p for p in predictions(ds)}

    p5 = by_key[(1, 5)]
    assert p5.at == at(10)
    assert p5.actual == 7.0
    assert p5.state == "full"
    assert p5.g == pytest.approx(0.7)  # mean of 8,6,7,9,5 only: title 5 itself is not in it
    assert p5.q == pytest.approx(0.8)
    assert p5.imdb == 8.0
    raw = 1 - 2 / 9  # one common title, gap |8 - 6|
    agree = (raw + 1.5) / 4
    assert p5.s == pytest.approx(agree * 0.9 + (1 - agree) * 0.1)

    p6 = by_key[(1, 6)]
    assert p6.s is None  # A's post on title 6 comes after V's
    assert p6.g == pytest.approx((8 + 6 + 7 + 9 + 5 + 7) / 60)  # now title 5 counts

    # A and C follow nobody; their first posts have no history and are not predicted.
    assert (2, 0) not in by_key
    assert (3, 5) not in by_key
    assert by_key[(2, 5)].s is None


def test_everyone_with_history_is_predicted_and_s_needs_an_approved_follow():
    posts = [_post(1, 0, 8, 1), _post(1, 1, 7, 2), _post(2, 1, 9, 1.5)]
    pending = _dataset([_user(1), _user(2)], [_follow(1, 2, accepted_at=None)], posts)
    (p,) = predictions(pending)
    assert (p.user, p.title) == (1, 1)
    assert p.s is None  # pending is not approved

    late = _dataset([_user(1), _user(2)], [_follow(1, 2, accepted_at=2.5)], posts)
    (p,) = predictions(late)
    assert p.s is None  # accepted after V's rating

    ok = _dataset([_user(1), _user(2)], [_follow(1, 2, accepted_at=1.2)], posts)
    (p,) = predictions(ok)
    assert p.state == "cold"  # one earlier rating, no picks
    assert p.s == pytest.approx(0.5 * 0.9 + 0.5 * 0.1)  # cold: agreement 0.5

    private = _dataset(
        [_user(1), _user(2)],
        [_follow(1, 2, accepted_at=1.2)],
        [_post(1, 0, 8, 1), _post(1, 1, 7, 2), _post(2, 1, 9, 1.5, shared=False)],
    )
    (p,) = predictions(private)
    assert p.s is None  # a private rating is not a signal


def test_locked_posts_are_not_predicted():
    ds = _dataset([_user(1), _user(2, picks=(ACTION,))], [], [_post(1, 0, 8, 1), _post(2, 0, 8, 2)])
    preds = predictions(ds)
    assert [(p.user, p.title, p.state) for p in preds] == [(2, 0, "cold")]


def test_simultaneous_posts_do_not_see_each_other():
    ds = _dataset([_user(1, picks=(ACTION,))], [], [_post(1, 0, 8, 1), _post(1, 1, 6, 1)])
    preds = predictions(ds)
    assert len(preds) == 2
    assert all(p.state == "cold" and p.g == pytest.approx(0.8) for p in preds)  # empty history


def _pred(i: int, g: float = 0.5, actual: float = 5.0, s: float | None = None) -> Prediction:
    return Prediction(1, i, at(i), actual, 7.0, g, 0.7, s, "full")


def test_scores():
    p = Prediction(1, 0, at(0), 8.0, 7.0, 0.5, 0.8, 0.9, "full")
    assert imdb_only(p) == 7.0
    assert title_score(p) == pytest.approx(100 * (0.7 * 0.5 + 0.3 * 0.8))
    assert title_score(p, 0.5, 0.5) == pytest.approx(65.0)
    assert feed_score(p) == pytest.approx(100 * (0.5 * 0.5 + 0.3 * 0.9 + 0.2 * 0.8))
    assert feed_score(_pred(0)) is None


# ===== evaluate / tuning ==========================================================================


def test_evaluate_time_split():
    preds = [_pred(i, g=i / 10, actual=1 + 9 * i / 10) for i in range(10)]
    ev = evaluate(preds, lambda p: p.g * 100, "perfect")
    assert isinstance(ev, Evaluation)
    assert ev.name == "perfect"
    assert ev.n_test == 4
    assert ev.rho == pytest.approx(1.0)
    assert ev.mae == pytest.approx(0.0, abs=1e-9)


def test_evaluate_splits_by_time_not_by_order_and_skips_none():
    preds = [_pred(i, g=i / 10, actual=1 + 9 * i / 10, s=None if i < 5 else 0.5) for i in range(10)]
    shuffled = preds[::-1]
    ev = evaluate(shuffled, feed_score, "feed")
    assert ev.n_test == 2  # five scored; 60 % of them are the train set
    assert ev.name == "feed"


def test_algorithm_beats_noise_on_fake_data(fake7):
    preds = predictions(fake7)
    assert len(preds) > 500
    assert [p.at for p in preds] == sorted(p.at for p in preds)
    ev = evaluate(preds, title_score, "title")
    assert ev.rho > 0
    rows = tune_title(preds)
    assert len(rows) == 7
    assert sorted(w for w, _ in rows) == pytest.approx([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    assert all(isinstance(e, Evaluation) and e.n_test == ev.n_test for _, e in rows)


def test_tune_feed_grid(fake7):
    preds = predictions(fake7)
    rows = tune_feed(preds)
    assert len(rows) == 66
    assert all(sum(w) == pytest.approx(1.0) for w, _ in rows)
    assert len({w for w, _ in rows}) == 66


# ===== Save rate by fit bucket ====================================================================


def _event(kind: str, props: dict, user: int = 1) -> FakeEvent:
    return FakeEvent(user, kind, None, None, props, at(0))  # type: ignore[arg-type]


def test_save_rate_buckets():
    events = [
        _event("post_viewed", {"fit": 30, "surface": "home"}),
        _event("post_viewed", {"fit": 50, "surface": "home"}),
        _event("post_viewed", {"fit": 80, "surface": "home"}),
        _event("saved", {"fit": 80, "source": "post"}),
        _event("discover_opened", {"type": "movie", "genre": None, "fits": [39, 40, 69, 70, 100]}),
        _event("saved", {"fit": 40, "source": "discover"}),
        _event("saved", {"fit": None, "source": "discover"}),  # a locked saver saw no score
        _event("watched", {"via": "post"}),
    ]
    rates = save_rate_by_bucket(events)
    assert rates["home"] == {"0-40": (0, 1), "40-70": (0, 1), "70-100": (1, 1)}
    assert rates["discover"] == {"0-40": (0, 1), "40-70": (1, 2), "70-100": (0, 2)}
    as_rows = [{"event_type": e.event_type, "props": e.props} for e in events]
    assert save_rate_by_bucket(as_rows) == rates


# ===== On the fake data ===========================================================================


@pytest.fixture(scope="module")
def fake7() -> Dataset:
    return generate(7)
