"""The taste quiz: genre picks and private ratings (plan P6-P9; sign-in is enforced in main.py).

Both routes need a profile (409 profile_required), declared per route so that the POST can first
make sure the genre rows exist, a catalogue write, before the request transaction opens.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from cinecircle_api.catalog.service import CatalogUnavailable, TitleService
from cinecircle_api.db import UserDb
from cinecircle_api.events import repository as events
from cinecircle_api.onboarding import repository
from cinecircle_api.onboarding.models import OnboardingAnswers, OnboardingState
from cinecircle_api.people.deps import Profile, require_profile
from cinecircle_api.posts.repository import TitleMissing
from cinecircle_api.wishlist import repository as wishlist_repository

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@dataclass(frozen=True)
class Answers:
    body: OnboardingAnswers
    genre_ids: set[int]  # the picked chips' ids that exist in app.genres


def _with_genres(request: Request, body: OnboardingAnswers) -> Answers:
    """The answers, once the picked genres exist in app.genres (user_genre_prefs has an FK to it).

    The first dependency of `submit`, so the TMDB call and the catalogue write run before
    `require_profile` opens the request's UserDb transaction. Ids TMDB does not list are dropped.
    """
    service: TitleService = request.app.state.title_service
    try:
        return Answers(body, service.ensure_genres(body.genre_ids))
    except CatalogUnavailable:
        raise HTTPException(503, "catalog_unavailable") from None


@router.get("", dependencies=[Depends(require_profile)])
def get_state(db: UserDb) -> OnboardingState:
    return repository.state(db)


@router.post("")
def submit(
    answers: Annotated[Answers, Depends(_with_genres)], _profile: Profile, db: UserDb
) -> OnboardingState:
    body = answers.body
    repository.replace_picks(db, answers.genre_ids)
    try:
        created = repository.add_private_ratings(db, body.ratings)
    except TitleMissing:
        raise HTTPException(404, "not_found") from None  # UserDb rolls the picks back too
    logged = []
    for title_id, post_id in created:
        props = {"shared": False, "surface": "onboarding"}
        logged.append(events.Event("post_created", title_id, post_id, props))
        if wishlist_repository.mark_watched_on_post(db, title_id):
            logged.append(events.Event("watched", title_id, props={"via": "post"}))
    done = {"genres": len(body.genres), "ratings": len(body.ratings)}
    logged.append(events.Event("onboarding_done", props=done))
    events.log(db, *logged)
    return repository.state(db)
