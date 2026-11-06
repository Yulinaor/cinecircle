"""The signed-in user's own profile and settings (sign-in is enforced in main.py)."""

from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException

from cinecircle_api.auth import Claims, CurrentUser
from cinecircle_api.db import UserDb
from cinecircle_api.people import repository
from cinecircle_api.people.deps import Profile
from cinecircle_api.people.models import CreateProfile, MeResponse, UpdateProfile
from cinecircle_api.people.usernames import normalize_username

router = APIRouter(prefix="/me", tags=["me"])


def _me(db: UserDb, claims: Claims) -> MeResponse:
    return MeResponse(id=claims.user_id, email=claims.email, profile=repository.get_my_profile(db))


_AVATAR_MAX_LENGTH = 512
_AVATAR_HOST_SUFFIX = ".googleusercontent.com"


def safe_avatar_url(value: object) -> str | None:
    """The avatar URL if it points at Google's user-content hosts, else None.

    user_metadata is user-writable and the URL is rendered as <img src> for every viewer, so
    anything else would let a user make other people's browsers contact a host of their choice.
    """
    if not isinstance(value, str) or len(value) > _AVATAR_MAX_LENGTH:
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username is not None or not host:
        return None
    if host == "googleusercontent.com" or host.endswith(_AVATAR_HOST_SUFFIX):
        return value
    return None


def _google_avatar(claims: Claims) -> str | None:
    metadata: Any = claims.raw.get("user_metadata")
    return safe_avatar_url(metadata.get("avatar_url") if isinstance(metadata, dict) else None)


@router.get("")
def get_me(db: UserDb, claims: CurrentUser) -> MeResponse:
    return _me(db, claims)


@router.post("", status_code=201)
def create_me(body: CreateProfile, db: UserDb, claims: CurrentUser) -> MeResponse:
    try:
        username = normalize_username(body.username)
    except ValueError as exc:
        raise HTTPException(422, f"username_{exc}") from None
    if repository.get_my_profile(db) is not None:
        raise HTTPException(409, "profile_exists")
    try:
        repository.create_profile(
            db, username, body.display_name, _google_avatar(claims), body.locale
        )
    except repository.ProfileExists:  # lost a race with another request of the same user
        raise HTTPException(409, "profile_exists") from None
    except repository.UsernameTaken:
        raise HTTPException(409, "username_taken") from None
    return _me(db, claims)


@router.patch("")
def update_me(body: UpdateProfile, db: UserDb, claims: CurrentUser, _: Profile) -> MeResponse:
    changes: dict[str, Any] = {}
    if body.display_name is not None:
        changes["display_name"] = body.display_name
    if "bio" in body.model_fields_set:
        changes["bio"] = body.bio or None  # "" and null both clear the bio
    if body.locale is not None:
        changes["locale"] = body.locale
    repository.update_my_profile(db, **changes)
    return _me(db, claims)
