"""The signed-in user's own statistics (sign-in is enforced in main.py)."""

from typing import Annotated

from fastapi import APIRouter, Query

from cinecircle_api.catalog.parse import Locale
from cinecircle_api.db import UserDb
from cinecircle_api.people.deps import Profile
from cinecircle_api.stats import repository
from cinecircle_api.stats.models import MyStats

router = APIRouter(prefix="/me", tags=["stats"])


@router.get("/stats")
def my_stats(db: UserDb, _: Profile, lang: Annotated[Locale, Query()] = "he") -> MyStats:
    """Ratings distribution, top genres, you vs IMDb and agreement with followed accounts: only
    the caller's own ratings (shared and private) and what RLS shows of other people's."""
    return repository.my_stats(db, lang)
