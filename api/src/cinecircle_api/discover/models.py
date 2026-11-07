"""Discover's response pieces: the P4 name rule and the attributed external review."""

import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

from cinecircle_api.catalog.parse import ListItem, Locale

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
