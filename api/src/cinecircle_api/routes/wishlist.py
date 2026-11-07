"""The caller's private wishlist (sign-in is enforced in main.py). Every route needs a profile
(409 profile_required). Nobody else's list is reachable: RLS limits every row to its owner, so
an item that is missing and one that belongs to someone else answer 404 not_found alike.

Every item carries the owner's Taste Match with the title (the title formula, plan P3); saving
records the score the saver saw in `fit_at_save` (P10) and logs the owner-only events (P9)."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.db import UserDb
from cinecircle_api.events import repository as events
from cinecircle_api.pagination import BIGINT_MAX, PAGE_SIZE, Cursor, decode_cursor, page_of
from cinecircle_api.people.deps import require_profile
from cinecircle_api.posts import repository as posts_repository
from cinecircle_api.taste.cards import title_taste
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.taste.models import Taste
from cinecircle_api.wishlist import repository
from cinecircle_api.wishlist.models import (
    SaveTitle,
    UpdateWishlist,
    WishlistItem,
    WishlistPage,
    WishlistSort,
    WishlistStatus,
    wishlist_item,
)
from cinecircle_api.wishlist.repository import WishlistRow

router = APIRouter(prefix="/wishlist", tags=["wishlist"], dependencies=[Depends(require_profile)])

TitleId = Annotated[int, Path(ge=1, le=BIGINT_MAX)]  # a failed path check answers 404
Lang = Annotated[Locale, Query()]
_OFFSET = re.compile(r"[0-9]{1,9}")  # the cursor of the sort by Taste Match: how many items to skip

type Scored = tuple[WishlistRow, Taste | None]


def _taste(ctx: TasteContext, row: WishlistRow, lang: Locale) -> Taste | None:
    return ctx.for_title(row.genres, row.imdb_rating, row.tmdb_rating, lang)


def _item_or_404(db: UserDb, ctx: TasteContext, title_id: int, lang: Locale) -> WishlistItem:
    row = repository.get_item(db, title_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return wishlist_item(row, lang, _taste(ctx, row, lang))


def _recent_cursor(raw: str | None) -> Cursor | None:
    if raw is None:
        return None
    try:
        return decode_cursor(raw)
    except ValueError:
        raise HTTPException(422, "invalid_cursor") from None


def _offset(raw: str | None) -> int:
    if raw is None:
        return 0
    if not _OFFSET.fullmatch(raw):
        raise HTTPException(422, "invalid_cursor")
    return int(raw)


def _by_match(scored: list[Scored]) -> list[Scored]:
    """Best match first, items with no score last; then newest added, then highest title id.
    Two stable passes keep the time comparison exact."""
    scored = sorted(scored, key=lambda s: (s[0].added_at, s[0].title_id), reverse=True)
    return sorted(scored, key=lambda s: (s[1] is None, -(s[1].fit if s[1] else 0)))


@router.get("")
def list_items(
    db: UserDb,
    cursor: Annotated[str | None, Query()] = None,
    status: WishlistStatus = "want",
    sort: WishlistSort = "recent",
    lang: Lang = "he",
) -> WishlistPage:
    """Newest first with a keyset cursor, or (`sort=fit`) best Taste Match first with an offset
    cursor: every item is scored on read, so the order can use the score (plan P11)."""
    if sort == "recent":
        after = _recent_cursor(cursor)
        ctx = TasteContext.load(db)
        rows = repository.list_items(db, status, after, PAGE_SIZE + 1)
        page, next_cursor = page_of(rows, key=lambda row: row.cursor)
        items = [wishlist_item(row, lang, _taste(ctx, row, lang)) for row in page]
        return WishlistPage(items=items, next_cursor=next_cursor)
    offset = _offset(cursor)
    ctx = TasteContext.load(db)
    scored = _by_match([(row, _taste(ctx, row, lang)) for row in repository.list_all(db, status)])
    end = offset + PAGE_SIZE
    items = [wishlist_item(row, lang, taste) for row, taste in scored[offset:end]]
    return WishlistPage(items=items, next_cursor=str(end) if len(scored) > end else None)


def _fit_at_save(db: UserDb, ctx: TasteContext, body: SaveTitle, lang: Locale) -> int | None:
    """The score the saver saw (plan P10): the feed formula for a visible source post on this
    title, otherwise the title formula; None while locked. Computed before the insert: the
    column has no UPDATE grant."""
    if not ctx.unlocked:
        return None
    if body.source_post_id is not None:
        post = posts_repository.get_post(db, body.source_post_id)
        if post is not None and post.title_id == body.title_id:
            taste = ctx.for_post(post, lang)
            if taste is not None:
                return taste.fit
    taste = title_taste(db, ctx, body.title_id, lang)
    return taste.fit if taste is not None else None


@router.post(
    "",
    status_code=201,
    responses={200: {"model": WishlistItem, "description": "already on the list"}},
)
def save(db: UserDb, body: SaveTitle, response: Response, lang: Lang = "he") -> WishlistItem:
    """201 for a new item; 200 with the existing one when the title was already saved."""
    ctx = TasteContext.load(db)
    fit = _fit_at_save(db, ctx, body, lang)
    try:
        added = repository.save(db, body, fit)
    except (repository.TitleMissing, repository.SourceInvalid):
        # An unusable source post answers like a missing title: nothing says which it was.
        raise HTTPException(404, "not_found") from None
    if added:
        props = {"fit": fit, "source": body.source}
        events.log(db, events.Event("saved", body.title_id, body.source_post_id, props))
    else:
        response.status_code = 200
    return _item_or_404(db, ctx, body.title_id, lang)


@router.patch("/{title_id}")
def update(db: UserDb, title_id: TitleId, body: UpdateWishlist, lang: Lang = "he") -> WishlistItem:
    before = repository.status_of(db, title_id)
    if not repository.set_status(db, title_id, body.status):
        raise HTTPException(404, "not_found")
    if before == "want" and body.status == "watched":
        events.log(db, events.Event("watched", title_id, props={"via": "wishlist"}))
    return _item_or_404(db, TasteContext.load(db), title_id, lang)


@router.delete("/{title_id}", status_code=204)
def delete(db: UserDb, title_id: TitleId) -> Response:
    if not repository.remove(db, title_id):
        raise HTTPException(404, "not_found")
    return Response(status_code=204)
