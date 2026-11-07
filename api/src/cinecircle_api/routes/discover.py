"""GET /discover: external lists (trending, top rated, "because you rated X") scored with the
viewer's own Taste Match (plan P1-P5, P9, P10; spec 00 R4).

The request holds a database transaction only twice, briefly, as the signed-in user: first to read
the viewer's own taste profile, seeds and rated titles, last to log the `discover_opened` event.
The TMDB fetch in between runs with no transaction open. Sign-in is enforced in main.py.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from cinecircle_api.auth import CurrentUser
from cinecircle_api.catalog.models import poster_url
from cinecircle_api.catalog.parse import GenreRow, ListItem, Locale, MediaType, pick_text
from cinecircle_api.db import RequestScope, user_transaction
from cinecircle_api.discover import seeds as seeds_repository
from cinecircle_api.discover.models import (
    DiscoverItem,
    DiscoverPage,
    DiscoverSection,
    GenreChip,
    Seed,
    item_name,
)
from cinecircle_api.discover.service import DiscoverService, ListKey, ServedList
from cinecircle_api.events import repository as events
from cinecircle_api.people import repository as people
from cinecircle_api.taste.context import TasteContext

router = APIRouter(prefix="/discover", tags=["discover"])

SectionKey = Literal["trending", "top_rated", "because"]


def _chip(genre: GenreRow, lang: Locale) -> GenreChip:
    name, _ = pick_text(genre.name_he, genre.name_en, lang)
    return GenreChip(id=genre.id, name=name or genre.name_en)


def _item(
    served: ServedList,
    item: ListItem,
    genres: dict[int, GenreRow],
    ctx: TasteContext | None,
    lang: Locale,
) -> DiscoverItem | None:
    name, name_lang = item_name(item, served.names_en, lang)
    if name is None or name_lang is None:
        return None  # TMDB sent no name at all: nothing to show
    rows = [genres[g] for g in item.genre_ids if g in genres]  # ids app.genres lacks are skipped
    imdb = served.imdb.get(item.tmdb_id)
    return DiscoverItem(
        tmdb_id=item.tmdb_id,
        media_type=item.media_type,
        name=name,
        name_lang=name_lang,
        poster_url=poster_url(item.poster_path),
        year=item.year,
        genres=[_chip(g, lang) for g in rows],
        tmdb_rating=item.vote_average,
        imdb_rating=imdb,
        taste=ctx.for_title(rows, imdb, item.vote_average, lang) if ctx else None,
    )


def _seed(row: seeds_repository.SeedRow, lang: Locale) -> Seed:
    name, name_lang = pick_text(row.name_he, row.name_en, lang)
    return Seed(
        title_id=row.title_id,
        name=name or row.name_en,
        name_lang=name_lang or "en",
        rating=row.rating,
    )


@router.get("")
def discover(
    request: Request,
    claims: CurrentUser,
    _scope: RequestScope,
    media_type: Annotated[MediaType, Query(alias="type")] = "movie",
    genre: Annotated[int | None, Query(ge=1)] = None,
    section: Annotated[SectionKey | None, Query()] = None,
    lang: Annotated[Locale, Query()] = "he",
) -> DiscoverPage:
    """Sections of external titles for the viewer. Works without a profile (no seeds, no Taste,
    no event). `section` keeps one kind of section; `genre` keeps the items with that genre but
    leaves `genres` (the chips) as they are for the whole page."""
    service: DiscoverService = request.app.state.discover_service

    # 1. The viewer's own data, in one short transaction.
    ctx: TasteContext | None = None
    seeds: list[seeds_repository.SeedRow] = []
    rated: set[tuple[int, MediaType]] = set()
    with user_transaction(request, claims) as conn:
        has_profile = people.get_my_profile(conn) is not None
        if has_profile:
            ctx = TasteContext.load(conn)  # scoring a title needs no further queries
            if section in (None, "because"):
                seeds = seeds_repository.my_seeds(conn, media_type)
                rated = seeds_repository.my_rated(conn)

    # 2. TMDB, with no transaction open.
    keys: list[ListKey] = []
    if section in (None, "trending"):
        keys.append(("trending", None))
    if section in (None, "top_rated"):
        keys.append(("top_rated", None))
    keys += [("recs", seed.tmdb_id) for seed in seeds]
    served = service.lists(media_type, keys, lang) if keys else []
    if keys and not served:
        raise HTTPException(503, "discover_unavailable")
    genre_rows = service.genre_rows(g for s in served for i in s.items for g in i.genre_ids)

    # 3. The page.
    seed_by_tmdb_id = {seed.tmdb_id: seed for seed in seeds}
    sections: list[DiscoverSection] = []
    chips: dict[int, GenreChip] = {}
    for one in served:
        kind, seed_tmdb_id = one.key
        shown: list[DiscoverItem] = []
        for item in one.items:
            card = _item(one, item, genre_rows, ctx, lang)
            if card is None:
                continue
            chips.update({g.id: g for g in card.genres})
            if kind == "recs" and (item.tmdb_id, item.media_type) in rated:
                continue  # the viewer has rated it already
            if genre is None or genre in {g.id for g in card.genres}:
                shown.append(card)
        if not shown:
            continue
        if kind == "recs" and seed_tmdb_id is not None:
            sections.append(
                DiscoverSection(
                    key="because", seed=_seed(seed_by_tmdb_id[seed_tmdb_id], lang), items=shown
                )
            )
        elif kind == "trending" or kind == "top_rated":
            sections.append(DiscoverSection(key=kind, seed=None, items=shown))
    page = DiscoverPage(
        type=media_type,
        sections=sections,
        genres=sorted(chips.values(), key=lambda g: g.id),
        stale=any(s.stale for s in served),
        fetched_at=min((s.fetched_at for s in served), default=None),
    )

    # 4. The event, in a second short transaction (plan P10: the fits shown, nulls dropped).
    if has_profile:
        fits = [i.taste.fit for s in sections for i in s.items if i.taste]
        props = {"type": media_type, "genre": genre, "fits": fits}
        with user_transaction(request, claims) as conn:
            events.log(conn, events.Event("discover_opened", props=props))
    return page
