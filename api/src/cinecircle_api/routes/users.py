"""Other people: search, profile cards and their posts (sign-in is enforced in main.py).

Every route also needs the caller to have a profile (409 profile_required). What the caller
may see of someone else is decided by Postgres RLS, not by this module.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import StringConstraints

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.db import UserDb
from cinecircle_api.pagination import PAGE_SIZE, Cursor, cursor_param, page_of
from cinecircle_api.people import repository
from cinecircle_api.people.deps import Username, card_or_404, require_profile
from cinecircle_api.people.models import SearchUsersResponse, UserDetails, UserProfile
from cinecircle_api.posts import repository as posts_repository
from cinecircle_api.posts.models import PostPage, post_card

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_profile)])

SearchQuery = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50), Query()
]
Lang = Annotated[Locale, Query()]


# Declared before /{username} so "search" is never read as a username.
@router.get("/search")
def search(db: UserDb, q: SearchQuery) -> SearchUsersResponse:
    return SearchUsersResponse(results=[row.card() for row in repository.search_cards(db, q)])


@router.get("/{username}")
def get_user(db: UserDb, username: Username) -> UserProfile:
    card = card_or_404(db, username)
    found = repository.get_details(db, card.id)  # None when RLS hides it from this viewer
    details = None
    if found:
        counts = repository.follow_counts(db) if card.follow_state == "self" else (None, None)
        details = UserDetails(
            bio=found[0], post_count=found[1], followers_count=counts[0], following_count=counts[1]
        )
    return UserProfile(**card.card().model_dump(), details=details)


@router.get("/{username}/posts")
def get_user_posts(
    db: UserDb,
    username: Username,
    after: Annotated[Cursor | None, Depends(cursor_param)],
    lang: Lang = "he",
) -> PostPage:
    card = card_or_404(db, username)
    if not repository.can_see_content(db, card.id):
        raise HTTPException(404, "not_found")
    rows = posts_repository.author_posts(db, card.id, after, PAGE_SIZE + 1)
    page, next_cursor = page_of(rows, key=lambda row: row.cursor)
    return PostPage(posts=[post_card(row, lang) for row in page], next_cursor=next_cursor)
