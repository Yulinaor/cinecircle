"""Offline evaluation of Taste Match (spec 03 section 7, plan P12): pure Python, no I/O.

For every post a user made, rebuild the score they would have been shown for that title from the
history they had strictly before it, then compare it with the rating they then gave. The
components are exactly the app's (`cinecircle_api.taste.score`); nothing is re-derived here, and
`tests/integration/test_analysis_frames.py` pins the profile and the title fit against the
database. Metrics use a time split so the weights are not judged on the data that picked them.
"""

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cinecircle_analysis.fakedata import Dataset, FakeEvent, FakePost
from cinecircle_api.taste import score
from cinecircle_api.taste.score import GenreStat, State, TasteProfile

# ===== Profiles ===================================================================================


def profile_from(
    ratings: Sequence[tuple[int, float]],
    genres: Mapping[int, Sequence[int]],
    picks: Iterable[int],
) -> TasteProfile:
    """A viewer's `TasteProfile` from (title, rating 1-10) pairs, the genres of each title and
    the genres picked in onboarding. One rating per title: the caller passes season-0 ratings
    (fake data has no seasons). Same arithmetic as `taste.repository.load_profile`."""
    total = 0.0
    sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    for title, rating in ratings:
        r = rating / 10
        total += r
        for genre in dict.fromkeys(genres.get(title, ())):
            sums[genre] = sums.get(genre, 0.0) + r
            counts[genre] = counts.get(genre, 0) + 1
    n = len(ratings)
    return TasteProfile(
        rated=n,
        mean_all=total / n if n else None,
        genres={g: GenreStat(c, sums[g] / c) for g, c in counts.items()},
        picked=frozenset(picks),
    )


# ===== Predictions ================================================================================


@dataclass(frozen=True)
class Prediction:
    """What the app would have shown `user` for `title` just before they rated it `actual`."""

    user: int
    title: int
    at: datetime
    actual: float  # the rating they then gave, 1-10
    imdb: float  # the title's IMDb rating, 1-10 (the baseline)
    g: float  # genre affinity, 0-1
    q: float  # catalogue quality, 0-1
    s: float | None  # followed-account signal, 0-1; None when no followee had posted the title
    state: State


def title_score(p: Prediction, wg: float = 0.7, wq: float = 0.3) -> float:
    """The Discover formula, x100 and unrounded."""
    return 100 * (wg * p.g + wq * p.q)


def feed_score(p: Prediction, wg: float = 0.5, ws: float = 0.3, wq: float = 0.2) -> float | None:
    """The Home formula, x100 and unrounded; None when there was no followed-account signal."""
    if p.s is None:
        return None
    return 100 * (wg * p.g + ws * p.s + wq * p.q)


def imdb_only(p: Prediction) -> float:
    """The baseline Taste Match has to beat: the title's IMDb rating alone."""
    return p.imdb


def predictions(dataset: Dataset) -> list[Prediction]:
    """One prediction per post whose author had an earlier rating or onboarding picks (so the
    app would have shown a score), in time order (plan P12).

    The history is strictly before the post: posts at the same instant do not see each other.
    The feed signal S comes from the latest earlier shared post on the same title by someone the
    author followed and who had accepted them by then; agreement is over the titles both had
    rated by then (the author's own ratings, the followee's shared ones), as in the app."""
    titles = {t.i: t for t in dataset.titles}
    genres = {i: t.genre_ids for i, t in titles.items()}
    picks = {u.n: u.picks for u in dataset.users}
    followees: dict[int, list[tuple[int, datetime]]] = {}
    for follow in dataset.follows:
        if follow.status == "accepted" and follow.responded_at is not None:
            followees.setdefault(follow.follower, []).append((follow.followee, follow.responded_at))

    rated: dict[int, dict[int, float]] = {}  # user -> title -> rating (all their posts so far)
    shared: dict[int, dict[int, tuple[float, datetime]]] = {}  # user -> title -> (rating, when)
    out: list[Prediction] = []

    ordered = sorted(dataset.posts, key=lambda p: (p.created_at, p.author, p.title))
    start = 0
    while start < len(ordered):
        stop = start
        while stop < len(ordered) and ordered[stop].created_at == ordered[start].created_at:
            stop += 1
        batch = ordered[start:stop]
        for post in batch:  # predict from the history before this instant ...
            mine = rated.get(post.author, {})
            profile = profile_from(list(mine.items()), genres, picks[post.author])
            if profile.state == "locked":
                continue
            title = titles[post.title]
            signal = _signal(profile, mine, post, followees, shared)
            out.append(
                Prediction(
                    user=post.author,
                    title=post.title,
                    at=post.created_at,
                    actual=post.rating,
                    imdb=title.imdb_rating,
                    g=score.genre_fit(profile, title.genre_ids),
                    q=score.quality(title.imdb_rating, title.tmdb_rating),
                    s=signal,
                    state=profile.state,
                )
            )
        for post in batch:  # ... then let the batch count
            rated.setdefault(post.author, {})[post.title] = post.rating
            if post.is_shared:
                shared.setdefault(post.author, {})[post.title] = (post.rating, post.created_at)
        start = stop
    return out


def _signal(
    profile: TasteProfile,
    mine: Mapping[int, float],
    post: FakePost,
    followees: Mapping[int, list[tuple[int, datetime]]],
    shared: Mapping[int, Mapping[int, tuple[float, datetime]]],
) -> float | None:
    best: tuple[datetime, int, float] | None = None
    for followee, accepted_at in followees.get(post.author, ()):
        if accepted_at >= post.created_at:
            continue
        theirs = shared.get(followee, {}).get(post.title)
        if theirs is None:
            continue
        candidate = (theirs[1], followee, theirs[0])
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None:
        return None
    _, author, rating = best
    agree = 0.5  # cold start: agreement is neutral until the full formula applies
    if profile.state == "full":
        gaps = [abs(mine[t] - r) for t, (r, _) in shared[author].items() if t in mine]
        agree = score.agreement(len(gaps), sum(gaps) / len(gaps) if gaps else None)
    return score.signal(agree, rating)


# ===== Metrics ====================================================================================


def _ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks, ties sharing the average of the ranks they span."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman's rho: Pearson correlation of the average ranks. NaN when either side is
    constant or there are fewer than two points."""
    if len(xs) != len(ys):
        raise ValueError("spearman needs two sequences of the same length")
    if len(xs) < 2:
        return math.nan
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return math.nan
    return sxy / math.sqrt(sxx * syy)


def fit_line(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    """Least squares `y = a + b*x`, returned as (a, b). With no spread in x the line is the mean
    of y; with no points it is (NaN, NaN)."""
    if len(xs) != len(ys):
        raise ValueError("fit_line needs two sequences of the same length")
    if not xs:
        return math.nan, math.nan
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return my - b * mx, b


def mae(pred: Sequence[float], actual: Sequence[float]) -> float:
    """Mean absolute error; NaN for no points."""
    if len(pred) != len(actual):
        raise ValueError("mae needs two sequences of the same length")
    if not pred:
        return math.nan
    return sum(abs(p - a) for p, a in zip(pred, actual, strict=True)) / len(pred)


# ===== Evaluation =================================================================================


@dataclass(frozen=True)
class Evaluation:
    """A score judged on the test part of the time split."""

    name: str
    n_test: int
    rho: float  # Spearman of the score against the rating
    mae: float  # after calibrating `rating ~ a + b * score` on the train part


ScoreFn = Callable[[Prediction], float | None]


def _evaluate(
    preds: Sequence[Prediction], score_fn: ScoreFn, name: str, train_share: float
) -> tuple[float, Evaluation]:
    """(Spearman on the train part, the test-part evaluation)."""
    scored = [(p, s) for p in sorted(preds, key=lambda p: p.at) if (s := score_fn(p)) is not None]
    n_train = math.floor(len(scored) * train_share + 1e-9)
    train, test = scored[:n_train], scored[n_train:]
    train_x, train_y = [s for _, s in train], [p.actual for p, _ in train]
    test_x, test_y = [s for _, s in test], [p.actual for p, _ in test]
    a, b = fit_line(train_x, train_y)
    return spearman(train_x, train_y), Evaluation(
        name=name,
        n_test=len(test),
        rho=spearman(test_x, test_y),
        mae=mae([a + b * x for x in test_x], test_y),
    )


def evaluate(
    preds: Sequence[Prediction], score_fn: ScoreFn, name: str, train_share: float = 0.6
) -> Evaluation:
    """Judge `score_fn` on the later part of the predictions in time (plan P12): the first
    `train_share` of them calibrate the rating line, the rest give rho and MAE. Predictions the
    function scores `None` are skipped before the split."""
    return _evaluate(preds, score_fn, name, train_share)[1]


def _ranked(rows: list[tuple[float, Any, Evaluation]]) -> list[tuple[Any, Evaluation]]:
    """Best train rho first (NaN last), ties by weights; the evaluations are the test ones."""
    rows.sort(key=lambda row: (-row[0] if not math.isnan(row[0]) else math.inf, row[1]))
    return [(weights, ev) for _, weights, ev in rows]


def tune_title(preds: Sequence[Prediction]) -> list[tuple[float, Evaluation]]:
    """Title weights wG in 0.3..0.9 (wQ = 1 - wG), best on the train part first (03 section 7.3)."""
    rows = []
    for tenth in range(3, 10):
        wg, wq = tenth / 10, (10 - tenth) / 10
        train_rho, ev = _evaluate(
            preds, lambda p, wg=wg, wq=wq: title_score(p, wg, wq), f"title wG={wg:.1f}", 0.6
        )
        rows.append((train_rho, wg, ev))
    return _ranked(rows)


def tune_feed(preds: Sequence[Prediction]) -> list[tuple[tuple[float, float, float], Evaluation]]:
    """Feed weights (wG, wS, wQ) on the 0.1 simplex, best on the train part first."""
    rows = []
    for g in range(11):
        for s in range(11 - g):
            weights = (g / 10, s / 10, (10 - g - s) / 10)
            train_rho, ev = _evaluate(
                preds,
                lambda p, w=weights: feed_score(p, *w),
                f"feed wG={weights[0]:.1f} wS={weights[1]:.1f} wQ={weights[2]:.1f}",
                0.6,
            )
            rows.append((train_rho, weights, ev))
    return _ranked(rows)


# ===== Online: save rate by fit bucket (03 section 7.2) ===========================================

BUCKETS = ("0-40", "40-70", "70-100")
SURFACES = ("home", "discover")
_SAVE_SURFACE = {"post": "home", "discover": "discover"}


def _bucket(fit: float) -> str:
    if fit < 40:
        return BUCKETS[0]
    return BUCKETS[1] if fit < 70 else BUCKETS[2]


def save_rate_by_bucket(
    events: Sequence[FakeEvent] | Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, tuple[int, int]]]:
    """{surface: {bucket: (saves, views)}} from logged events. Home views are `post_viewed`,
    Discover views are each fit in a `discover_opened`; a save counts on the surface it came
    from (source `post` is Home) in the bucket of the fit it was saved with. Saves without a fit
    (the saver was locked) are left out."""
    saves = {s: dict.fromkeys(BUCKETS, 0) for s in SURFACES}
    views = {s: dict.fromkeys(BUCKETS, 0) for s in SURFACES}
    for event in events:
        kind, props = (
            (event.event_type, event.props)
            if isinstance(event, FakeEvent)
            else (event["event_type"], event["props"])
        )
        props = props or {}
        if kind == "post_viewed" and props.get("fit") is not None:
            views["home"][_bucket(props["fit"])] += 1
        elif kind == "discover_opened":
            for fit in props.get("fits") or ():
                views["discover"][_bucket(fit)] += 1
        elif kind == "saved" and props.get("fit") is not None:
            surface = _SAVE_SURFACE.get(props.get("source"))
            if surface is not None:
                saves[surface][_bucket(props["fit"])] += 1
    return {s: {b: (saves[s][b], views[s][b]) for b in BUCKETS} for s in SURFACES}
