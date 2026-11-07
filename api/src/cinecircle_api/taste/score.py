"""The Taste Match formulas of spec 03 section 3, pure: no I/O, no clock (plan P1, P2, P4).

Ratings are on the r/10 scale (0.1-1.0) unless a name ends in `_rating`. A viewer's profile is
loaded elsewhere; here it is just numbers. Fits are ints 0-100, rounded half up.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

K = 3  # shrinkage strength
PICK_BONUS = 0.10  # added to a genre picked in onboarding (full state)
STRONG_GENRE = 0.70  # affinity at which a genre is named in the reason
AGREE_MIN_COMMON = 3  # common titles before the agreement % is shown
FULL_AFTER = 5  # rated titles before the full formula applies
COLD_PICKED = 0.8  # cold start: shrinkage target for a picked genre
COLD_OTHER = 0.5  # cold start: shrinkage target for any other genre
Q_DEFAULT = 0.6  # quality when the catalogue has no rating

_MAX_REASON_GENRES = 2

State = Literal["locked", "cold", "full"]


@dataclass(frozen=True)
class GenreStat:
    """One genre over the viewer's rated titles."""

    n: int
    mean: float  # avg(r/10)


@dataclass(frozen=True)
class TasteProfile:
    rated: int  # distinct titles rated (one rating per title)
    mean_all: float | None  # avg(r/10) over them; None when rated == 0
    genres: Mapping[int, GenreStat]  # genre id -> stat (rated genres only)
    picked: frozenset[int]  # genre ids from onboarding

    @property
    def state(self) -> State:
        if self.rated == 0 and not self.picked:
            return "locked"
        return "full" if self.rated >= FULL_AFTER else "cold"


def affinity(profile: TasteProfile, genre_id: int) -> float:
    """How well a genre fits the viewer, 0-1 (spec 03 G).

    Locked viewers get the cold value: callers never score for them.
    """
    stat = profile.genres.get(genre_id)
    n, mean = (stat.n, stat.mean) if stat else (0, 0.0)
    picked = genre_id in profile.picked
    if profile.state == "full":
        # A full profile has rated titles; the fallback only guards a bad profile.
        prior = profile.mean_all if profile.mean_all is not None else COLD_OTHER
        value = (n * mean + K * prior) / (n + K)
        return min(1.0, value + PICK_BONUS) if picked else value
    target = COLD_PICKED if picked else COLD_OTHER
    return (n * mean + K * target) / (n + K)


def mean_of(values: Sequence[float]) -> float:
    """G from the given genre affinities; an empty list is the caller's mistake."""
    if not values:
        raise ValueError("mean_of needs at least one value")
    return sum(values) / len(values)


def genre_fit(profile: TasteProfile, genre_ids: Sequence[int]) -> float:
    """G for a title; one with no genres gets the prior of an unpicked, unrated genre."""
    if not genre_ids:
        return affinity(profile, -1)  # no real genre has id -1: the prior
    return mean_of([affinity(profile, g) for g in genre_ids])


def quality(imdb_rating: float | None, tmdb_rating: float | None) -> float:
    """Q: IMDb/10, else TMDB/10, else the default."""
    if imdb_rating is not None:
        return imdb_rating / 10
    if tmdb_rating is not None:
        return tmdb_rating / 10
    return Q_DEFAULT


def agreement(common: int, mean_gap: float | None) -> float:
    """How often the viewer and an author agree; few common titles pull towards 0.5.

    `mean_gap` is the mean absolute rating gap on the 1-10 scale over `common` titles.
    """
    if common <= 0 or mean_gap is None:
        return 0.5
    raw = 1 - mean_gap / 9
    return (common * raw + 3 * 0.5) / (common + 3)


def signal(agreement: float, author_rating: float) -> float:
    """S: the author's rating, trusted as far as the viewer usually agrees with them."""
    liked = author_rating / 10
    return agreement * liked + (1 - agreement) * (1 - liked)


def round_half_up(x: float) -> int:
    """floor(x + 0.5) clamped to 0-100; float noise (78.49999999999) rounds as 78.5."""
    return max(0, min(100, math.floor(round(x, 9) + 0.5)))


def feed_fit(g: float, s: float, q: float) -> int:
    return round_half_up(100 * (0.5 * g + 0.3 * s + 0.2 * q))


def title_fit(g: float, q: float) -> int:
    return round_half_up(100 * (0.7 * g + 0.3 * q))


def strong_genres(profile: TasteProfile, genre_ids: Sequence[int]) -> list[int]:
    """Up to two genres that fit the viewer: affinity >= 0.70, best first, ties by genre id."""
    scored = [(affinity(profile, g), g) for g in genre_ids]
    strong = sorted(
        ((a, g) for a, g in scored if a >= STRONG_GENRE), key=lambda ag: (-ag[0], ag[1])
    )
    return [g for _, g in strong[:_MAX_REASON_GENRES]]
