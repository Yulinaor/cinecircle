"""`require_profile`: the guard for every route that needs the caller to have a profile."""

from typing import Annotated

from fastapi import Depends, HTTPException

from cinecircle_api.db import UserDb
from cinecircle_api.people import repository
from cinecircle_api.people.models import MyProfile


def require_profile(db: UserDb) -> MyProfile:
    """The caller's profile, or 409 profile_required (signed in, but onboarding is not done)."""
    profile = repository.get_my_profile(db)
    if profile is None:
        raise HTTPException(409, "profile_required")
    return profile


Profile = Annotated[MyProfile, Depends(require_profile)]
