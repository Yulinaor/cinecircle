"""A deterministic fake CineCircle: users, follows, titles, ratings, wishlists and events.

Pure and seeded (plan P7, P10, P11): no database, no clock, no network. The same seed gives the
same `Dataset`; `load.py` writes it to the local database and the notebooks read it back.

The model, in one paragraph. Four taste clusters each like a handful of genres; a user's genre
preferences are their cluster's plus personal noise, and they have a harshness bias. A title has a
latent quality `q` that drives its IMDb and TMDB ratings. A user's latent opinion of a title is
`L = q + 1.5 * mean(pref of its genres) + bias`; the rating they post is `L + N(0, 1)` rounded to a
half step. People pick what to watch with probability rising with `L`, so ratings are biased
upwards (selection) while still carrying real signal. Users sign up over the first 13 weeks and
their activity then decays with a personal half-life (retention). Followers view shared ratings a
few hours to three days later, with the fit the app would have shown from the history they had at
that moment (`cinecircle_api.taste.score`); they save with a probability driven by `L`, not by the
fit, and a saved title that is rated later becomes "watched".

Indices: a user is `n`, numbered from 1 (`users[n - 1]`, `fake01`); a title is `i`, numbered from
0 (`titles[i]`). Posts are keyed by `(author n, title i)` (one per pair, season 0 only).
"""

import heapq
import math
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid5

from cinecircle_api.catalog.parse import MediaType
from cinecircle_api.events.repository import EventType
from cinecircle_api.taste import score
from cinecircle_api.taste.score import GenreStat, TasteProfile

FAKE_DOMAIN = "fake.cinecircle.local"
FAKE_TMDB_BASE = 2_000_000_000  # real TMDB ids stay under ~1.5 million
FAKE_NAMESPACE = UUID("5e0f2a6c-3b1d-4c8e-9f47-0c1ec1c1e000")
START = datetime(2026, 5, 4, tzinfo=UTC)  # a Monday; the timeline is fixed, there is no clock
WEEKS = 26

# The 19 TMDB movie genres: id, English name, TMDB's he-IL name.
GENRES: tuple[tuple[int, str, str], ...] = (
    (28, "Action", "אקשן"),
    (12, "Adventure", "הרפתקאות"),
    (16, "Animation", "אנימציה"),
    (35, "Comedy", "קומדיה"),
    (80, "Crime", "פשע"),
    (99, "Documentary", "דוקומנטרי"),
    (18, "Drama", "דרמה"),
    (10751, "Family", "משפחה"),
    (14, "Fantasy", "פנטזיה"),
    (36, "History", "היסטוריה"),
    (27, "Horror", "אימה"),
    (10402, "Music", "מוזיקה"),
    (9648, "Mystery", "מסתורין"),
    (10749, "Romance", "רומנטיקה"),
    (878, "Science Fiction", "מדע בדיוני"),
    (10770, "TV Movie", "סרט טלוויזיה"),
    (53, "Thriller", "מותחן"),
    (10752, "War", "מלחמה"),
    (37, "Western", "מערבון"),
)
_GENRE_IDS = tuple(g[0] for g in GENRES)

# ===== The model's parameters (plan P10, P11) ====================================================

_CLUSTER_LIKES: tuple[tuple[int, ...], ...] = (
    (28, 12, 878, 14, 53),  # action and adventure
    (18, 10749, 36, 10752, 10402),  # drama and romance
    (35, 10751, 16, 12, 10402),  # comedy and family
    (27, 53, 80, 9648, 99),  # dark: horror, thriller, crime, mystery, documentary
)
_LIKED, _DISLIKED, _PREF_NOISE = 0.8, -0.35, 0.3
_GENRE_WEIGHT = 1.5  # L = q + 1.5 * mean pref + bias
_BIAS_SD, _RATING_SD = 0.6, 1.0
_SELECTION = 0.8  # P(pick title) ~ exp(0.8 * (L - 6))
_WISH_BOOST = 6.0  # a saved title is much likelier to be watched (rated) next
_SIGNUP_WEEKS = 13
_ONBOARDED = 0.7
_PRIVATE = 0.16  # of the non-onboarding ratings; onboarding ratings are all private
_VIEW_P = 0.6
_DISCOVER_P = 1 / 3  # of the weeks a user rated something
_DISCOVER_SHOWN = 10
_SAVE_DELAY = (5.0, 300.0)  # seconds from seeing a title to saving it
_ACCEPTED = 0.9
_MAX_RATED_SHARE = 0.8  # nobody rates more than this share of the catalogue
_SIGNUP_MARGIN = timedelta(hours=1)  # ratings come at least this long after sign-up

_WEEK = timedelta(weeks=1)
_END = START + WEEKS * _WEEK

# ===== Names =====================================================================================

_FIRST_NAMES = (
    ("Noa", "נועה"),
    ("Gal", "גל"),
    ("Dana", "דנה"),
    ("Ron", "רון"),
    ("Maya", "מאיה"),
    ("Eitan", "איתן"),
    ("Tamar", "תמר"),
    ("Yoav", "יואב"),
    ("Shira", "שירה"),
    ("Omer", "עומר"),
    ("Lior", "ליאור"),
    ("Nitzan", "ניצן"),
    ("Amit", "עמית"),
    ("Roni", "רוני"),
    ("Yael", "יעל"),
    ("Daniel", "דניאל"),
    ("Tal", "טל"),
    ("Hila", "הילה"),
    ("Itay", "איתי"),
    ("Michal", "מיכל"),
    ("Oren", "אורן"),
    ("Noam", "נועם"),
    ("Adi", "עדי"),
    ("Guy", "גיא"),
    ("Keren", "קרן"),
    ("Alon", "אלון"),
    ("Maor", "מאור"),
    ("Sharon", "שרון"),
    ("Uri", "אורי"),
    ("Liat", "ליאת"),
)

# English adjective, Hebrew masculine, Hebrew feminine.
_ADJECTIVES = (
    ("Silent", "שקט", "שקטה"),
    ("Golden", "זהוב", "זהובה"),
    ("Hidden", "נסתר", "נסתרת"),
    ("Crimson", "ארגמני", "ארגמנית"),
    ("Last", "אחרון", "אחרונה"),
    ("Distant", "רחוק", "רחוקה"),
    ("Broken", "שבור", "שבורה"),
    ("Electric", "חשמלי", "חשמלית"),
    ("Frozen", "קפוא", "קפואה"),
    ("Burning", "בוער", "בוערת"),
    ("Lonely", "בודד", "בודדת"),
    ("Wild", "פראי", "פראית"),
    ("Secret", "סודי", "סודית"),
    ("Endless", "אינסופי", "אינסופית"),
    ("Hollow", "חלול", "חלולה"),
    ("Bright", "בהיר", "בהירה"),
    ("Forgotten", "נשכח", "נשכחת"),
    ("Velvet", "קטיפתי", "קטיפתית"),
    ("Paper", "נייר", "נייר"),
    ("Midnight", "חצות", "חצות"),
)
# English noun, Hebrew noun, grammatical gender.
_NOUNS = (
    ("Harbor", "נמל", "m"),
    ("Garden", "גן", "m"),
    ("Orchard", "פרדס", "m"),
    ("Lantern", "פנס", "m"),
    ("Tower", "מגדל", "m"),
    ("River", "נהר", "m"),
    ("Bridge", "גשר", "m"),
    ("Mirror", "מראה", "f"),
    ("Island", "אי", "m"),
    ("Station", "תחנה", "f"),
    ("Letter", "מכתב", "m"),
    ("Window", "חלון", "m"),
    ("Compass", "מצפן", "m"),
    ("Desert", "מדבר", "m"),
    ("Carnival", "קרנבל", "m"),
    ("Lighthouse", "מגדלור", "m"),
    ("Orchestra", "תזמורת", "f"),
    ("Voyage", "מסע", "m"),
    ("Kingdom", "ממלכה", "f"),
    ("Season", "עונה", "f"),
)

# ===== The dataset ===============================================================================


@dataclass(frozen=True)
class FakeUser:
    n: int  # 1-based
    id: UUID
    email: str
    username: str
    display_name: str
    cluster: int  # 0-3
    signed_up: datetime
    picks: tuple[int, ...]  # genre ids from onboarding; empty when the user skipped it


@dataclass(frozen=True)
class FakeTitle:
    i: int  # 0-based, the index into `Dataset.titles`
    tmdb_id: int
    media_type: MediaType
    name_en: str
    name_he: str
    year: int
    genre_ids: tuple[int, ...]
    imdb_rating: float
    tmdb_rating: float


@dataclass(frozen=True)
class FakeFollow:
    follower: int
    followee: int
    status: Literal["pending", "accepted"]
    created_at: datetime
    responded_at: datetime | None


@dataclass(frozen=True)
class FakePost:
    author: int
    title: int
    rating: float
    is_shared: bool
    created_at: datetime


@dataclass(frozen=True)
class FakeWish:
    owner: int
    title: int
    source: Literal["post", "discover"]
    source_post: tuple[int, int] | None  # (author, title) of the post it was saved from
    status: Literal["want", "watched"]
    fit_at_save: int | None  # None when the saver was locked and saw no score
    added_at: datetime
    watched_at: datetime | None


@dataclass(frozen=True)
class FakeEvent:
    user: int
    event_type: EventType
    title: int | None
    post: tuple[int, int] | None  # (author, title)
    props: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class Dataset:
    users: tuple[FakeUser, ...]
    titles: tuple[FakeTitle, ...]
    follows: tuple[FakeFollow, ...]
    posts: tuple[FakePost, ...]
    wishes: tuple[FakeWish, ...]
    events: tuple[FakeEvent, ...]


# ===== Simulation state ==========================================================================


@dataclass
class _Wish:
    owner: int
    title: int
    source: Literal["post", "discover"]
    source_post: tuple[int, int] | None
    fit_at_save: int | None
    added_at: datetime
    status: Literal["want", "watched"] = "want"
    watched_at: datetime | None = None


@dataclass
class _Person:
    """What a user has done so far: the history their fits are computed from."""

    user: FakeUser
    bias: float
    prefs: dict[int, float]
    activity: float
    half_life: float
    onboarding_ratings: int = 0
    rated: dict[int, float] = field(default_factory=dict)  # title -> rating (1-10)
    shared: dict[int, float] = field(default_factory=dict)  # title -> rating, shared ones only
    genre_sum: dict[int, float] = field(default_factory=dict)  # genre -> sum of rating / 10
    genre_n: dict[int, int] = field(default_factory=dict)
    wishes: dict[int, _Wish] = field(default_factory=dict)

    def profile(self) -> TasteProfile:
        n = len(self.rated)
        total = sum(self.rated.values()) / 10
        return TasteProfile(
            rated=n,
            mean_all=total / n if n else None,
            genres={g: GenreStat(c, self.genre_sum[g] / c) for g, c in self.genre_n.items()},
            picked=frozenset(self.user.picks),
        )

    def rate(self, title: FakeTitle, rating: float, is_shared: bool) -> None:
        self.rated[title.i] = rating
        if is_shared:
            self.shared[title.i] = rating
        for genre in title.genre_ids:
            self.genre_sum[genre] = self.genre_sum.get(genre, 0.0) + rating / 10
            self.genre_n[genre] = self.genre_n.get(genre, 0) + 1


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def _seconds(rng: random.Random, low: float, high: float) -> timedelta:
    return timedelta(seconds=rng.uniform(low, high))


# ===== Generation ================================================================================


def _make_titles(rng: random.Random, count: int) -> tuple[list[FakeTitle], list[float]]:
    combos = [(a, n) for a in range(len(_ADJECTIVES)) for n in range(len(_NOUNS))]
    rng.shuffle(combos)
    titles: list[FakeTitle] = []
    quality: list[float] = []
    for i in range(count):
        adj, noun = combos[i % len(combos)]
        suffix = "" if i < len(combos) else f" {i // len(combos) + 1}"
        adj_en, adj_m, adj_f = _ADJECTIVES[adj]
        noun_en, noun_he, gender = _NOUNS[noun]
        q = _clamp(rng.gauss(6.5, 1.1), 3.5, 9.0)
        genre_ids = tuple(sorted(rng.sample(_GENRE_IDS, rng.choice((1, 2, 2, 3)))))
        titles.append(
            FakeTitle(
                i=i,
                tmdb_id=FAKE_TMDB_BASE + i,
                media_type="series" if rng.random() < 0.25 else "movie",
                name_en=f"The {adj_en} {noun_en}{suffix}",
                name_he=f"ה{noun_he} ה{adj_m if gender == 'm' else adj_f}{suffix}",
                year=rng.randint(1985, 2026),
                genre_ids=genre_ids,
                imdb_rating=round(_clamp(q + rng.gauss(0, 0.35), 3.0, 9.3), 1),
                tmdb_rating=round(_clamp(q + rng.gauss(0, 0.5), 2.5, 9.5), 1),
            )
        )
        quality.append(q)
    return titles, quality


def _make_people(rng: random.Random, count: int) -> list[_Person]:
    weeks = list(range(_SIGNUP_WEEKS)) + [
        min(int(rng.expovariate(0.25)), _SIGNUP_WEEKS - 1) for _ in range(max(0, count - 13))
    ]
    weeks = weeks[:count]
    rng.shuffle(weeks)
    clusters = [n % 4 for n in range(count)]
    rng.shuffle(clusters)
    people = []
    for index in range(count):
        n = index + 1
        first_en, first_he = _FIRST_NAMES[index % len(_FIRST_NAMES)]
        cluster = clusters[index]
        likes = _CLUSTER_LIKES[cluster]
        prefs = {
            g: (_LIKED if g in likes else _DISLIKED) + rng.gauss(0, _PREF_NOISE) for g in _GENRE_IDS
        }
        picks = tuple(sorted(rng.sample(likes, 3))) if rng.random() < _ONBOARDED else ()
        signed_up = START + weeks[index] * _WEEK + _seconds(rng, 0, _WEEK.total_seconds() - 7200)
        user = FakeUser(
            n=n,
            id=uuid5(FAKE_NAMESPACE, f"fake-user-{n:02d}"),
            email=f"fake{n:02d}@{FAKE_DOMAIN}",
            username=f"fake_{first_en.lower()}_{n:02d}",
            display_name=first_he if n % 2 else first_en,
            cluster=cluster,
            signed_up=signed_up,
            picks=picks,
        )
        people.append(
            _Person(
                user=user,
                bias=rng.gauss(0, _BIAS_SD),
                prefs=prefs,
                activity=rng.lognormvariate(0, 0.5),
                half_life=_clamp(rng.lognormvariate(math.log(5), 0.8), 1.0, 40.0),
                onboarding_ratings=rng.randint(3, 6) if picks else 0,
            )
        )
    return people


def _make_follows(
    rng: random.Random, people: list[_Person]
) -> tuple[list[FakeFollow], dict[int, list[tuple[int, datetime]]]]:
    """Homophilous follows: 3-15 per user, same cluster three times as likely. Returns the
    follows and, per followee, their approved followers with the time they were approved."""
    popularity = {p.user.n: rng.lognormvariate(0, 0.5) for p in people}
    follows: list[FakeFollow] = []
    followers: dict[int, list[tuple[int, datetime]]] = {p.user.n: [] for p in people}
    for me in people:
        wanted = min(len(people) - 1, int(_clamp(round(rng.gauss(8, 3)), 3, 15)))
        keyed = []
        for other in people:
            if other is me:
                continue
            weight = 3.0 if other.user.cluster == me.user.cluster else 1.0
            weight *= popularity[other.user.n]
            keyed.append((rng.random() ** (1 / weight), other))
        keyed.sort(key=lambda pair: (-pair[0], pair[1].user.n))
        for _, other in keyed[:wanted]:
            created = max(me.user.signed_up, other.user.signed_up) + _seconds(rng, 3600, 14 * 86400)
            if rng.random() < _ACCEPTED:
                responded = created + _seconds(rng, 1800, 3 * 86400)
                follows.append(FakeFollow(me.user.n, other.user.n, "accepted", created, responded))
                followers[other.user.n].append((me.user.n, responded))
            else:
                follows.append(FakeFollow(me.user.n, other.user.n, "pending", created, None))
    follows.sort(key=lambda f: (f.created_at, f.follower, f.followee))
    return follows, followers


def _cells(people: list[_Person]) -> tuple[list[tuple[int, int]], list[float]]:
    """(person index, week) cells with their activity weight: decays after sign-up."""
    cells, weights = [], []
    for index, person in enumerate(people):
        first = int((person.user.signed_up - START) / _WEEK)
        for week in range(first, WEEKS):
            cells.append((index, week))
            weights.append(person.activity * 0.5 ** ((week - first) / person.half_life))
    return cells, weights


def _window(person: _Person, week: int) -> tuple[datetime, datetime]:
    start = max(START + week * _WEEK, person.user.signed_up + _SIGNUP_MARGIN)
    return start, START + (week + 1) * _WEEK


def generate(seed: int = 7, users: int = 50, titles: int = 300, ratings: int = 3000) -> Dataset:
    rng = random.Random(seed)
    title_list, quality = _make_titles(rng, titles)
    people = _make_people(rng, users)
    follows, followers = _make_follows(rng, people)

    # Latent opinion L(u, t) and the base chance of picking each title.
    latent = [
        [
            quality[t.i]
            + _GENRE_WEIGHT * sum(p.prefs[g] for g in t.genre_ids) / len(t.genre_ids)
            + p.bias
            for t in title_list
        ]
        for p in people
    ]
    pick_weight = [[math.exp(_SELECTION * (value - 6.0)) for value in row] for row in latent]
    by_type = {
        kind: [t.i for t in title_list if t.media_type == kind] for kind in ("movie", "series")
    }

    # Onboarding ratings come first; the rest of the budget is spread over (user, week) cells.
    budget = ratings
    for p in people:
        p.onboarding_ratings = min(p.onboarding_ratings, budget)
        budget -= p.onboarding_ratings
    cap = int(_MAX_RATED_SHARE * titles)
    if budget > sum(cap - p.onboarding_ratings for p in people):
        raise ValueError(f"{ratings} ratings do not fit {users} users and {titles} titles")
    cells, weights = _cells(people)
    used = [p.onboarding_ratings for p in people]
    slots: list[int] = []
    while len(slots) < budget:
        for cell in rng.choices(range(len(cells)), weights=weights, k=budget - len(slots)):
            if used[cells[cell][0]] < cap:
                used[cells[cell][0]] += 1
                slots.append(cell)

    # The timeline: a heap of (time, tie-break, kind, user index, extra).
    heap: list[tuple[datetime, int, str, int, Any]] = []
    counter = 0

    def push(when: datetime, kind: str, index: int, extra: Any = None) -> None:
        nonlocal counter
        counter += 1
        heapq.heappush(heap, (when, counter, kind, index, extra))

    for index, p in enumerate(people):
        if p.onboarding_ratings:
            push(p.user.signed_up + _seconds(rng, 60, 600), "onboard", index)
    active_weeks: dict[tuple[int, int], int] = {}
    for cell in sorted(slots):
        index, week = cells[cell]
        low, high = _window(people[index], week)
        push(low + _seconds(rng, 0, (high - low).total_seconds()), "post", index)
        active_weeks[cells[cell]] = active_weeks.get(cells[cell], 0) + 1
    for index, week in sorted(active_weeks):
        if rng.random() < _DISCOVER_P:
            low, high = _window(people[index], week)
            push(low + _seconds(rng, 0, (high - low).total_seconds()), "open", index)

    posts: list[FakePost] = []
    events: list[FakeEvent] = []
    by_n = {p.user.n: index for index, p in enumerate(people)}

    def log(
        user: int,
        kind: EventType,
        title: int | None,
        post: tuple[int, int] | None,
        props: dict,
        when: datetime,
    ) -> None:
        events.append(FakeEvent(user, kind, title, post, props, when))

    def choose_title(index: int) -> int:
        """An unrated title, likelier the more the user expects to like it (and a saved one)."""
        person = people[index]
        weights = list(pick_weight[index])
        for t in person.rated:
            weights[t] = 0.0
        for t, wish in person.wishes.items():
            if wish.status == "want":
                weights[t] *= _WISH_BOOST
        return rng.choices(range(titles), weights=weights)[0]

    def rate(index: int, when: datetime, shared: bool, surface: str) -> FakePost:
        person = people[index]
        title = title_list[choose_title(index)]
        value = latent[index][title.i] + rng.gauss(0, _RATING_SD)
        rating = _clamp(round(value * 2) / 2, 1.0, 10.0)
        post = FakePost(person.user.n, title.i, rating, shared, when)
        posts.append(post)
        person.rate(title, rating, shared)
        log(
            person.user.n,
            "post_created",
            title.i,
            (post.author, title.i),
            {"shared": shared, "surface": surface},
            when,
        )
        wish = person.wishes.get(title.i)
        if wish is not None and wish.status == "want":
            wish.status, wish.watched_at = "watched", when
            log(
                person.user.n,
                "watched",
                title.i,
                None,
                {"via": "post"},  # as routes/posts.py logs a post on a wished title
                when + timedelta(seconds=1),
            )
        return post

    def feed_fit(viewer: _Person, author: _Person, title: FakeTitle, rating: float) -> int | None:
        profile = viewer.profile()
        if profile.state == "locked":
            return None
        g = score.genre_fit(profile, title.genre_ids)
        q = score.quality(title.imdb_rating, title.tmdb_rating)
        agree = 0.5
        if profile.state == "full":
            gaps = [abs(viewer.rated[t] - r) for t, r in author.shared.items() if t in viewer.rated]
            agree = score.agreement(len(gaps), sum(gaps) / len(gaps) if gaps else None)
        return score.feed_fit(g, score.signal(agree, rating), q)

    def maybe_save(
        index: int,
        title: int,
        fit: int | None,
        when: datetime,
        source: Literal["post", "discover"],
        source_post: tuple[int, int] | None,
    ) -> None:
        """Decide now whether to save; the save itself lands a few seconds to minutes later (the
        fit is the one shown at `when`, from the history before it)."""
        person = people[index]
        if title in person.rated or title in person.wishes:
            return
        if rng.random() >= _sigmoid(1.2 * (latent[index][title] - 7) - 1.0):
            return
        saved_at = when + _seconds(rng, *_SAVE_DELAY)
        push(saved_at, "save", index, (title, fit, source, source_post))

    while heap:
        when, _, kind, index, extra = heapq.heappop(heap)
        person = people[index]
        if kind == "onboard":
            clock = when
            for _ in range(person.onboarding_ratings):
                clock += _seconds(rng, 20, 90)
                rate(index, clock, False, "onboarding")
            log(
                person.user.n,
                "onboarding_done",
                None,
                None,
                {"genres": len(person.user.picks), "ratings": person.onboarding_ratings},
                clock + timedelta(seconds=5),
            )
        elif kind == "post":
            post = rate(index, when, rng.random() >= _PRIVATE, "compose")
            if post.is_shared:
                for follower, responded in followers[person.user.n]:
                    if responded < when and rng.random() < _VIEW_P:
                        seen = when + _seconds(rng, 2 * 3600, 72 * 3600)
                        if seen < _END:
                            push(seen, "view", by_n[follower], (person.user.n, post.title))
        elif kind == "view":
            author_n, title_i = extra
            title = title_list[title_i]
            author = people[by_n[author_n]]
            fit = feed_fit(person, author, title, author.shared[title_i])
            key = (author_n, title_i)
            if fit is not None:  # the app logs a view only when a score was shown
                log(
                    person.user.n,
                    "post_viewed",
                    title_i,
                    key,
                    {"fit": fit, "surface": "home"},
                    when,
                )
            maybe_save(index, title_i, fit, when, "post", key)
        elif kind == "save":
            title_i, fit, source, source_post = extra
            if title_i in person.rated or title_i in person.wishes:
                continue  # rated (or saved from elsewhere) in the meantime
            person.wishes[title_i] = _Wish(person.user.n, title_i, source, source_post, fit, when)
            log(
                person.user.n,
                "saved",
                title_i,
                source_post,
                {"fit": fit, "source": source},
                when,
            )
        else:  # open: the Discover page
            media = "movie" if rng.random() < 0.7 else "series"
            pool = [t for t in by_type[media] if t not in person.rated]
            shown = rng.sample(pool, min(_DISCOVER_SHOWN, len(pool)))
            profile = person.profile()
            fits: list[int | None] = [None] * len(shown)
            if profile.state != "locked":
                fits = [
                    score.title_fit(
                        score.genre_fit(profile, title_list[t].genre_ids),
                        score.quality(title_list[t].imdb_rating, title_list[t].tmdb_rating),
                    )
                    for t in shown
                ]
            log(
                person.user.n,
                "discover_opened",
                None,
                None,
                {"type": media, "genre": None, "fits": [f for f in fits if f is not None]},
                when,
            )
            for t, fit in zip(shown, fits, strict=True):
                maybe_save(index, t, fit, when, "discover", None)

    wishes = sorted(
        (
            FakeWish(
                w.owner,
                w.title,
                w.source,
                w.source_post,
                w.status,
                w.fit_at_save,
                w.added_at,
                w.watched_at,
            )
            for p in people
            for w in p.wishes.values()
        ),
        key=lambda w: (w.added_at, w.owner, w.title),
    )
    return Dataset(
        users=tuple(p.user for p in people),
        titles=tuple(title_list),
        follows=tuple(follows),
        posts=tuple(sorted(posts, key=lambda p: (p.created_at, p.author))),
        wishes=tuple(wishes),
        events=tuple(sorted(events, key=lambda e: e.created_at)),
    )
