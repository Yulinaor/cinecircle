"""Home feed: shared posts by the caller and the people they follow (sign-in is enforced in
main.py). Needs a profile (409 profile_required); which posts exist for the caller is decided
by Postgres RLS."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from cinecircle_api.catalog.parse import Locale, TypeFilter
from cinecircle_api.db import UserDb
from cinecircle_api.events import repository as events
from cinecircle_api.pagination import PAGE_SIZE, Cursor, cursor_param, page_of
from cinecircle_api.people.deps import require_profile
from cinecircle_api.posts import repository
from cinecircle_api.posts.models import PostPage
from cinecircle_api.taste.cards import post_cards

router = APIRouter(prefix="/feed", tags=["feed"], dependencies=[Depends(require_profile)])


@router.get("")
def home(
    db: UserDb,
    after: Annotated[Cursor | None, Depends(cursor_param)],
    type_filter: Annotated[TypeFilter, Query(alias="type")] = "all",
    lang: Annotated[Locale, Query()] = "he",
) -> PostPage:
    rows = repository.feed(db, type_filter, after, PAGE_SIZE + 1)
    page, next_cursor = page_of(rows, key=lambda row: row.cursor)
    cards = post_cards(db, page, lang)
    # A card that showed a score was viewed with that fit (plan P9); unscored ones log nothing.
    events.log(
        db,
        *(
            events.Event(
                "post_viewed", card.title.id, card.id, {"fit": card.taste.fit, "surface": "home"}
            )
            for card in cards
            if card.taste is not None
        ),
    )
    return PostPage(posts=cards, next_cursor=next_cursor)
