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
def by_id(service: Service, title_id: Annotated[int, Path(ge=1)], lang: Lang = "he") -> TitleDetail:
    return _detail(lambda: service.get(title_id), lang)
