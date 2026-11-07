"""The My Stats response (plan P1-P3) and the two bucket rules behind its charts."""

import math
from typing import Literal

from pydantic import BaseModel

ImdbBucketKey = Literal["much_lower", "lower", "same", "higher", "much_higher"]
# The five "you vs IMDb" buckets, lowest gap first: the order the response always lists them in.
IMDB_BUCKET_KEYS: tuple[ImdbBucketKey, ...] = (
    "much_lower",
    "lower",
    "same",
    "higher",
    "much_higher",
)


class RatingBucket(BaseModel):
    rating: int  # 1-10
    count: int


class GenreStat(BaseModel):
    id: int
    name: str  # localised
    count: int  # rated titles in the genre
    mean: float  # 1-10 scale, one decimal


class ImdbBucket(BaseModel):
    key: ImdbBucketKey
    count: int


class ImdbStats(BaseModel):
    compared: int  # rated titles that have an IMDb rating
    mean_gap: float | None  # mean of (my rating - IMDb), one decimal; None when compared == 0
    buckets: list[ImdbBucket]  # always five, in IMDB_BUCKET_KEYS order


class AgreementRow(BaseModel):
    username: str
    display_name: str
    avatar_url: str | None
    agreement: int  # 0-100
    common: int  # titles both rated, at least 3


class MyStats(BaseModel):
    rated: int  # distinct titles rated (one rating per title)
    distribution: list[RatingBucket]  # always ten, ratings 1..10
    genres: list[GenreStat]  # up to five
    imdb: ImdbStats
    agreement: list[AgreementRow]  # up to five


def bucket_of(rating: float) -> int:
    """The distribution bucket of a rating: floor(r), so 10 holds only 10.0."""
    return max(1, min(10, math.floor(rating)))


def imdb_bucket(gap: float) -> ImdbBucketKey:
    """Where `my rating - IMDb rating` falls: -2 and -0.5 are the lower buckets' upper edges,
    0.5 and 2 the higher buckets' lower edges."""
    if gap <= -2:
        return "much_lower"
    if gap <= -0.5:
        return "lower"
    if gap < 0.5:
        return "same"
    if gap < 2:
        return "higher"
    return "much_higher"
