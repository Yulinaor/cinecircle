"""Request and response bodies for posts, and the one card every post response uses (plan P6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, Strict, field_validator

from cinecircle_api.catalog.models import TitleDetail, poster_url
from cinecircle_api.catalog.parse import Locale, MediaType, pick_text
from cinecircle_api.pagination import BIGINT_MAX
from cinecircle_api.people.models import UserCard

if TYPE_CHECKING:
    from cinecircle_api.posts.repository import PostRow
    from cinecircle_api.wishlist.repository import WishlistRow

OPINION_MAX = 500  # code points, like Postgres char_length


def _half_step(value: float) -> float:
    # NaN fails both comparisons; infinities fail the range.
    if not (1 <= value <= 10 and (value * 2).is_integer()):
        raise ValueError("rating must be 1-10 in steps of 0.5")
    return value


# Strict: a number only. "9.5" and true are rejected rather than coerced.
Rating = Annotated[float, Strict(), AfterValidator(_half_step)]


def _clean_opinion(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > OPINION_MAX:  # len() counts code points: an emoji is never cut in half
        raise ValueError(f"opinion must be at most {OPINION_MAX} characters")
    return value or None


Opinion = Annotated[str | None, AfterValidator(_clean_opinion)]


class CardTitle(BaseModel):
    id: int
    media_type: MediaType
    name: str | None
    name_lang: Locale | None
    poster_url: str | None
    year_start: int | None
    runtime_min: int | None
    genres: list[str]
    overview: str | None
    overview_lang: Locale | None
    imdb_rating: float | None
    tmdb_rating: float | None


class CardSeason(BaseModel):
    number: int
    name: str | None
    name_lang: Locale | None
    overview: str | None
    overview_lang: Locale | None
    poster_url: str | None  # None when the season has no poster: the web uses the title's


class PostCard(BaseModel):
    id: int
    author: UserCard
    title: CardTitle
    season: CardSeason | None  # None for a post on the whole movie / series (season 0)
    rating: float
    opinion: str | None
    contains_spoilers: bool
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    edited: bool


class PostPage(BaseModel):
    posts: list[PostCard]
    next_cursor: str | None


class CreatePost(BaseModel):
    title_id: int = Field(ge=1, le=BIGINT_MAX)
    season_number: int = Field(0, ge=0, le=1000)
    rating: Rating
    opinion: Opinion = None
    contains_spoilers: bool = False
    is_shared: bool = True


class UpdatePost(BaseModel):
    """Only the fields sent change. Title and season are fixed once posted (plan P7)."""

    model_config = ConfigDict(extra="forbid")

    rating: Rating | None = None
    opinion: Opinion = None  # null or "" clears it
    contains_spoilers: bool | None = None
    is_shared: bool | None = None

    @field_validator("rating", "contains_spoilers", "is_shared", mode="before")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def card_title(row: PostRow | WishlistRow, lang: Locale) -> CardTitle:
    """The title half of a card: any row that carries the title columns and its genres."""
    name, name_lang = pick_text(row.name_he, row.name_en, lang)
    overview, overview_lang = pick_text(row.overview_he, row.overview_en, lang)
    return CardTitle(
        id=row.title_id,
        media_type=row.media_type,
        name=name,
        name_lang=name_lang,
        poster_url=poster_url(row.poster_path),
        year_start=row.year_start,
        runtime_min=row.runtime_min,
        genres=[g.name_he if lang == "he" and g.name_he else g.name_en for g in row.genres],
        overview=overview,
        overview_lang=overview_lang,
        imdb_rating=_float(row.imdb_rating),
        tmdb_rating=_float(row.tmdb_rating),
    )


def post_card(row: PostRow, lang: Locale) -> PostCard:
    season = None
    if row.season_number > 0:
        season_name, season_name_lang = pick_text(row.season_name_he, row.season_name_en, lang)
        season_overview, season_overview_lang = pick_text(
            row.season_overview_he, row.season_overview_en, lang
        )
        season = CardSeason(
            number=row.season_number,
            name=season_name,
            name_lang=season_name_lang,
            overview=season_overview,
            overview_lang=season_overview_lang,
            poster_url=poster_url(row.season_poster_path),
        )
    return PostCard(
        id=row.id,
        author=row.author.card(),
        title=card_title(row, lang),
        season=season,
        rating=float(row.rating),
        opinion=row.opinion,
        contains_spoilers=row.contains_spoilers,
        is_shared=row.is_shared,
        created_at=row.created_at,
        updated_at=row.updated_at,
        edited=row.updated_at > row.created_at,
    )


class TitlePage(TitleDetail):
    """A title with the posts the viewer may see on it (plan P9)."""

    posts: list[PostCard]
