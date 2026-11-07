"""Request and response bodies for the private wishlist (plan P3-P4, P6, P9)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.pagination import BIGINT_MAX
from cinecircle_api.people.models import UserCard
from cinecircle_api.posts.models import CardTitle, card_title

if TYPE_CHECKING:
    from cinecircle_api.wishlist.repository import WishlistRow

# The schema also allows 'dropped'; the API never uses it (plan P3).
WishlistStatus = Literal["want", "watched"]
WishlistSource = Literal["post", "discover", "search"]


class WishlistVia(BaseModel):
    """The post an item was saved from, while the owner can still see it (plan P6)."""

    post_id: int
    author: UserCard


class MyPost(BaseModel):
    """The owner's newest post on the title, any season: what the Rate it now link needs."""

    id: int
    rating: float


class WishlistItem(BaseModel):
    title: CardTitle
    status: WishlistStatus
    source: WishlistSource
    via: WishlistVia | None
    added_at: datetime
    watched_at: datetime | None
    my_post: MyPost | None


class WishlistPage(BaseModel):
    items: list[WishlistItem]
    next_cursor: str | None


class SaveTitle(BaseModel):
    """`fit_at_save` is not accepted: the server fills it (plan P4)."""

    model_config = ConfigDict(extra="forbid")

    title_id: int = Field(ge=1, le=BIGINT_MAX)
    source: WishlistSource
    source_post_id: int | None = Field(None, ge=1, le=BIGINT_MAX)

    @model_validator(mode="after")
    def _post_source_has_a_post(self) -> Self:
        if (self.source == "post") != (self.source_post_id is not None):
            raise ValueError("source_post_id goes with source 'post' and with nothing else")
        return self


class UpdateWishlist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: WishlistStatus


def wishlist_item(row: WishlistRow, lang: Locale) -> WishlistItem:
    via = None
    if row.via_post_id is not None and row.via_author is not None:
        via = WishlistVia(post_id=row.via_post_id, author=row.via_author.card())
    my_post = None
    if row.my_post_id is not None and row.my_rating is not None:
        my_post = MyPost(id=row.my_post_id, rating=float(row.my_rating))
    return WishlistItem(
        title=card_title(row, lang),
        status=row.status,
        source=row.source,
        via=via,
        added_at=row.added_at,
        watched_at=row.watched_at,
        my_post=my_post,
    )
