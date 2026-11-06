"""Other people: search, profile cards and their posts (sign-in is enforced in main.py).

Every route also needs the caller to have a profile (409 profile_required). What the caller
may see of someone else is decided by Postgres RLS, not by this module.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import StringConstraints

from cinecircle_api.catalog.models import poster_url
from cinecircle_api.catalog.parse import Locale, pick_text
from cinecircle_api.db import UserDb
from cinecircle_api.people import repository
from cinecircle_api.people.deps import require_profile
from cinecircle_api.people.models import (
    PostItem,
    PostsResponse,
    PostTitle,
    SearchUsersResponse,
    UserCard,
    UserDetails,
    UserProfile,
)

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_profile)])

SearchQuery = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50), Query()
]
# A longer path segment cannot be a username; a failed path check answers 404.
Username = Annotated[str, Path(max_length=30)]
Lang = Annotated[Locale, Query()]


def _post_item(row: repository.PostRow, lang: Locale) -> PostItem:
    name, name_lang = pick_text(row.name_he, row.name_en, lang)
    return PostItem(
        id=row.id,
        title=PostTitle(
            id=row.title_id,
            media_type=row.media_type,
            name=name,
            name_lang=name_lang,
            poster_url=poster_url(row.poster_path),
        ),
        season_number=row.season_number,
        rating=float(row.rating),
        opinion=row.opinion,
        contains_spoilers=row.contains_spoilers,
        is_shared=row.is_shared,
        created_at=row.created_at,
    )


def _to_card(row: repository.CardRow) -> UserCard:
    return UserCard(
        username=row.username,
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        follow_state=row.follow_state,
    )


def _card_or_404(db: UserDb, username: str) -> repository.CardRow:
    card = repository.get_card(db, username.lower())
    if card is None:
        raise HTTPException(404, "not_found")
    return card


# Declared before /{username} so "search" is never read as a username.
@router.get("/search")
def search(db: UserDb, q: SearchQuery) -> SearchUsersResponse:
    return SearchUsersResponse(results=[_to_card(row) for row in repository.search_cards(db, q)])


@router.get("/{username}")
def get_user(db: UserDb, username: Username) -> UserProfile:
    card = _card_or_404(db, username)
    found = repository.get_details(db, card.id)  # None when RLS hides it from this viewer
    details = UserDetails(bio=found[0], post_count=found[1]) if found else None
    return UserProfile(**_to_card(card).model_dump(), details=details)


@router.get("/{username}/posts")
def get_user_posts(db: UserDb, username: Username, lang: Lang = "he") -> PostsResponse:
    card = _card_or_404(db, username)
    if not repository.can_see_content(db, card.id):
        raise HTTPException(404, "not_found")
    posts = repository.list_posts(db, card.id)
    return PostsResponse(posts=[_post_item(row, lang) for row in posts])
