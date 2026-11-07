"""Discover's response pieces: the P4 name rule, the Discover page and the attributed external
review. Nothing here has a field for another CineCircle user or their content (spec 00 R4.3): the
only personal parts of a page are each item's `taste` and the `seed` of a "because" section, both
computed from the viewer's own data."""

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from cinecircle_api.catalog.parse import ListItem, Locale, MediaType
from cinecircle_api.taste.models import Taste

_HEBREW_LETTER = re.compile("[֐-׿]")


def item_name(
    item: ListItem, names_en: Mapping[int, str | None], lang: Locale
) -> tuple[str | None, Locale | None]:
    """The name to show for a list item (plan P4) and the language it is in.

    `item` was fetched in `lang`. TMDB answers with the original title when it has no Hebrew
    translation, so for `he` a name without Hebrew letters is replaced by the English one
    (`names_en`, the same list fetched in English), labelled "en".
    """
    if lang == "he" and item.name and _HEBREW_LETTER.search(item.name):
        return item.name, "he"
    name = (names_en.get(item.tmdb_id) if lang == "he" else None) or item.name
    return (name, "en") if name else (None, None)


class ExternalReview(BaseModel):
    author_name: str
    excerpt: str  # plain text, at most 300 characters; the web renders it as text
    url: str
    author_rating: float | None
    source: Literal["tmdb"]


class ReviewsPage(BaseModel):
    reviews: list[ExternalReview]


class GenreChip(BaseModel):
    id: int
    name: str


class DiscoverItem(BaseModel):
    """An external title (a TMDB list item); the web labels each rating with its source."""

    tmdb_id: int
    media_type: MediaType
    name: str
    name_lang: Locale
    poster_url: str | None
    year: int | None
    genres: list[GenreChip]
    tmdb_rating: float | None
    imdb_rating: float | None  # only when the title is already cached in the catalogue
    taste: Taste | None  # the viewer's own Taste Match with this title; None while locked


class Seed(BaseModel):
    """The viewer's own rating that a "because" section is built on."""

    title_id: int
    name: str
    name_lang: Locale
    rating: float


class DiscoverSection(BaseModel):
    key: Literal["trending", "top_rated", "because"]
    seed: Seed | None  # only on "because"
    items: list[DiscoverItem]


class DiscoverPage(BaseModel):
    type: MediaType
    sections: list[DiscoverSection]
    genres: list[GenreChip]  # every genre of every item, before the `genre` filter
    stale: bool  # some list is older than its refresh time because TMDB could not be reached
    fetched_at: datetime | None  # the oldest list served; None when no list was needed
