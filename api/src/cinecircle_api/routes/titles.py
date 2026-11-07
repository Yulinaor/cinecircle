"""Catalogue endpoints (sign-in is enforced where main.py includes the router)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import StringConstraints

from cinecircle_api.catalog.models import (
    SearchResponse,
    TitleDetail,
    search_response,
    title_detail,
)
from cinecircle_api.catalog.parse import Locale, MediaType, TypeFilter
from cinecircle_api.catalog.service import (
    CachedTitle,
    CatalogUnavailable,
    TitleNotFound,
    TitleService,
)
from cinecircle_api.db import UserDb
from cinecircle_api.events import repository as events
from cinecircle_api.posts import repository as posts_repository
from cinecircle_api.posts.models import TitlePage
from cinecircle_api.taste.cards import post_cards, title_taste
from cinecircle_api.taste.context import TasteContext
from cinecircle_api.wishlist import repository as wishlist_repository

router = APIRouter(prefix="/titles", tags=["titles"])

SearchQuery = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), Query()
]
Lang = Annotated[Locale, Query()]


def get_title_service(request: Request) -> TitleService:
    return request.app.state.title_service


Service = Annotated[TitleService, Depends(get_title_service)]


def _detail(load, lang: Locale) -> TitleDetail:
    try:
        cached: CachedTitle = load()
    except TitleNotFound:
        raise HTTPException(404, "not_found") from None
    except CatalogUnavailable:
        raise HTTPException(503, "catalog_unavailable") from None
    return title_detail(cached, lang)


# Declared before /{title_id} so "search" is never read as an id.
@router.get("/search")
def search(
    service: Service,
    q: SearchQuery,
    type_filter: Annotated[TypeFilter, Query(alias="type")] = "all",
    lang: Lang = "he",
) -> SearchResponse:
    try:
        return search_response(service.search(q, type_filter, lang))
    except CatalogUnavailable:
        raise HTTPException(503, "catalog_unavailable") from None


@router.get("/tmdb/{media_type}/{tmdb_id}")
def by_tmdb(
    service: Service,
    media_type: MediaType,
    tmdb_id: Annotated[int, Path(ge=1)],
    lang: Lang = "he",
) -> TitleDetail:
    return _detail(lambda: service.get_by_tmdb(tmdb_id, media_type), lang)


@router.get("/{title_id}")
def by_id(
    service: Service, db: UserDb, title_id: Annotated[int, Path(ge=1)], lang: Lang = "he"
) -> TitlePage:
    """The catalogue entry plus the posts on it the viewer may see (plan P9) and the viewer's own
    `in_wishlist` flag, and the viewer's Taste Match with the title (plan P3; None while locked).
    The catalogue part needs no profile; a viewer without one has no posts to see, so RLS returns
    none, `in_wishlist` is False and `taste` is None."""
    detail = _detail(lambda: service.get(title_id), lang)
    rows = posts_repository.title_posts(db, detail.id)
    ctx = TasteContext.load(db)  # a viewer with nothing of their own is locked: no taste, no error
    taste = title_taste(db, ctx, detail.id, lang)
    if taste is not None:  # a score was shown (plan P9)
        props = {"fit": taste.fit, "surface": "title"}
        events.log(db, events.Event("title_viewed", detail.id, props=props))
    return TitlePage(
        **detail.model_dump(),
        posts=post_cards(db, rows, lang, ctx),
        in_wishlist=wishlist_repository.in_wishlist(db, detail.id),
        taste=taste,
    )
