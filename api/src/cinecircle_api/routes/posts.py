"""Posts: compose, read one, edit and delete (sign-in is enforced in main.py).

Every route needs the caller to have a profile (409 profile_required). Whether a post exists
for the caller, and whether they may change it, is decided by Postgres RLS: a post that is
hidden, missing or someone else's to edit answers 404 not_found alike.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.catalog.service import TitleService
from cinecircle_api.db import UserDb
from cinecircle_api.pagination import BIGINT_MAX
from cinecircle_api.people.deps import require_profile
from cinecircle_api.posts import repository
from cinecircle_api.posts.models import CreatePost, PostCard, UpdatePost, post_card

router = APIRouter(prefix="/posts", tags=["posts"], dependencies=[Depends(require_profile)])

PostId = Annotated[int, Path(ge=1, le=BIGINT_MAX)]  # a failed path check answers 404
Lang = Annotated[Locale, Query()]


def _card_or_404(db: UserDb, post_id: int, lang: Locale) -> PostCard:
    row = repository.get_post(db, post_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return post_card(row, lang)


@router.post("", status_code=201, response_model=PostCard)
def create(
    request: Request, db: UserDb, body: CreatePost, lang: Lang = "he"
) -> PostCard | JSONResponse:
    if body.season_number > 0:
        # Best effort, before the insert so the new card already carries the Hebrew text (P8).
        service: TitleService = request.app.state.title_service
        service.fill_season_text(body.title_id, body.season_number)
    try:
        post_id = repository.create_post(db, body)
    except repository.PostExists as exists:
        return JSONResponse({"detail": "post_exists", "post_id": exists.post_id}, status_code=409)
    except repository.TitleMissing:
        raise HTTPException(404, "not_found") from None
    except repository.SeasonInvalid:
        raise HTTPException(422, "season_invalid") from None
    return _card_or_404(db, post_id, lang)


@router.get("/{post_id}")
def get_one(db: UserDb, post_id: PostId, lang: Lang = "he") -> PostCard:
    return _card_or_404(db, post_id, lang)


@router.patch("/{post_id}")
def update(db: UserDb, post_id: PostId, body: UpdatePost, lang: Lang = "he") -> PostCard:
    if not repository.update_post(db, post_id, body.model_dump(exclude_unset=True)):
        raise HTTPException(404, "not_found")
    return _card_or_404(db, post_id, lang)


@router.delete("/{post_id}", status_code=204)
def delete(db: UserDb, post_id: PostId) -> Response:
    if not repository.delete_post(db, post_id):
        raise HTTPException(404, "not_found")
    return Response(status_code=204)
