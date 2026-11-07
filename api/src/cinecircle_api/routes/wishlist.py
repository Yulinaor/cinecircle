"""The caller's private wishlist (sign-in is enforced in main.py). Every route needs a profile
(409 profile_required). Nobody else's list is reachable: RLS limits every row to its owner, so
an item that is missing and one that belongs to someone else answer 404 not_found alike."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.db import UserDb
from cinecircle_api.pagination import BIGINT_MAX, PAGE_SIZE, Cursor, cursor_param, page_of
from cinecircle_api.people.deps import require_profile
from cinecircle_api.wishlist import repository
from cinecircle_api.wishlist.models import (
    SaveTitle,
    UpdateWishlist,
    WishlistItem,
    WishlistPage,
    WishlistStatus,
    wishlist_item,
)

router = APIRouter(prefix="/wishlist", tags=["wishlist"], dependencies=[Depends(require_profile)])

TitleId = Annotated[int, Path(ge=1, le=BIGINT_MAX)]  # a failed path check answers 404
Lang = Annotated[Locale, Query()]


def _item_or_404(db: UserDb, title_id: int, lang: Locale) -> WishlistItem:
    row = repository.get_item(db, title_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return wishlist_item(row, lang)


@router.get("")
def list_items(
    db: UserDb,
    after: Annotated[Cursor | None, Depends(cursor_param)],
    status: WishlistStatus = "want",
    lang: Lang = "he",
) -> WishlistPage:
    rows = repository.list_items(db, status, after, PAGE_SIZE + 1)
    page, next_cursor = page_of(rows, key=lambda row: row.cursor)
    return WishlistPage(items=[wishlist_item(row, lang) for row in page], next_cursor=next_cursor)


@router.post("", status_code=201)
def save(db: UserDb, body: SaveTitle, response: Response, lang: Lang = "he") -> WishlistItem:
    """201 for a new item; 200 with the existing one when the title was already saved."""
    try:
        added = repository.save(db, body)
    except (repository.TitleMissing, repository.SourceInvalid):
        # An unusable source post answers like a missing title: nothing says which it was.
        raise HTTPException(404, "not_found") from None
    if not added:
        response.status_code = 200
    return _item_or_404(db, body.title_id, lang)


@router.patch("/{title_id}")
def update(db: UserDb, title_id: TitleId, body: UpdateWishlist, lang: Lang = "he") -> WishlistItem:
    if not repository.set_status(db, title_id, body.status):
        raise HTTPException(404, "not_found")
    return _item_or_404(db, title_id, lang)


@router.delete("/{title_id}", status_code=204)
def delete(db: UserDb, title_id: TitleId) -> Response:
    if not repository.remove(db, title_id):
        raise HTTPException(404, "not_found")
    return Response(status_code=204)
