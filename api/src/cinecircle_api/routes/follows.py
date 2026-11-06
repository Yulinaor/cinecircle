"""Following is one-way and needs approval: request, accept, decline, cancel, unfollow, remove.

Sign-in is enforced in main.py; every route also needs the caller to have a profile (409
profile_required). Postgres RLS, column grants and triggers enforce who may change what and write
the notifications; this module only exposes them.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from cinecircle_api.db import UserDb
from cinecircle_api.follows import repository
from cinecircle_api.people.deps import Username, card_or_404, require_profile
from cinecircle_api.people.models import UserCard

router = APIRouter(tags=["follows"], dependencies=[Depends(require_profile)])


class FollowResult(BaseModel):
    follow_state: Literal["requested", "following"]


class UsersResponse(BaseModel):
    users: list[UserCard]


def _no_content() -> Response:
    return Response(status_code=204)


@router.post("/follows/{username}")
def follow(db: UserDb, username: Username) -> FollowResult:
    target = card_or_404(db, username)
    if target.follow_state == "self":
        raise HTTPException(422, "cannot_follow_self")
    return FollowResult(follow_state=repository.request_follow(db, target.id))


@router.delete("/follows/{username}", status_code=204)
def unfollow(db: UserDb, username: Username) -> Response:
    """Cancel my request or stop following; 204 even when there was nothing to remove."""
    repository.delete_my_follow(db, card_or_404(db, username).id)
    return _no_content()


@router.post("/follow-requests/{username}/accept")
def accept(db: UserDb, username: Username) -> UserCard:
    follower = card_or_404(db, username)
    if not repository.accept_request(db, follower.id):
        raise HTTPException(404, "not_found")
    # The card's follow_state is my row towards them, which accepting does not change.
    return follower.card()


@router.delete("/follow-requests/{username}", status_code=204)
def decline(db: UserDb, username: Username) -> Response:
    if not repository.decline_request(db, card_or_404(db, username).id):
        raise HTTPException(404, "not_found")
    return _no_content()


@router.delete("/followers/{username}", status_code=204)
def remove_follower(db: UserDb, username: Username) -> Response:
    if not repository.remove_follower(db, card_or_404(db, username).id):
        raise HTTPException(404, "not_found")
    return _no_content()


@router.get("/me/followers")
def followers(db: UserDb) -> UsersResponse:
    return UsersResponse(users=[row.card() for row in repository.list_followers(db)])


@router.get("/me/following")
def following(db: UserDb) -> UsersResponse:
    return UsersResponse(users=[row.card() for row in repository.list_following(db)])


@router.get("/me/follow-requests")
def follow_requests(db: UserDb) -> UsersResponse:
    return UsersResponse(users=[row.card() for row in repository.list_requests(db)])
