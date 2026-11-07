"""Cache-first Discover lists (6 h per key and locale) and TMDB reviews (7 days per title).

Everything runs on the service session: lists and reviews are TMDB data, never user content.
A TMDB failure serves what is cached; with nothing cached a list is left out and a title simply
has no reviews. No TMDB call is made while a database transaction is open."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from cinecircle_api.catalog._http import deadline
from cinecircle_api.catalog.errors import ExternalApiError
from cinecircle_api.catalog.parse import (
    ListItem,
    Locale,
    MediaType,
    parse_list,
    parse_reviews,
)
from cinecircle_api.catalog.service import CatalogUnavailable, TitleService
from cinecircle_api.catalog.tmdb_client import TmdbClient
from cinecircle_api.discover import repository as repo

logger = logging.getLogger(__name__)

LIST_REFRESH_AFTER = timedelta(hours=6)
REVIEWS_REFRESH_AFTER = timedelta(days=7)
MAX_REVIEWS = 5
_LANGUAGE = {"he": "he-IL", "en": "en-US"}

# ("trending", None), ("top_rated", None) or ("recs", <seed tmdb id>)
ListKey = tuple[str, int | None]


@dataclass(frozen=True)
class ServedList:
    key: ListKey
    items: list[ListItem]
    names_en: dict[int, str | None]  # English names, filled for lang "he" (plan P4)
    imdb: dict[int, float | None]  # only for items already cached in app.titles
    fetched_at: datetime  # when TMDB was last asked successfully for this list
    stale: bool  # a refresh was due but TMDB could not be reached


@dataclass(frozen=True)
class _Loaded:
    items: list[ListItem]
    fetched_at: datetime
    stale: bool


def _kind(media_type: MediaType) -> str:
    return "movie" if media_type == "movie" else "tv"


def _cache_key(media_type: MediaType, key: ListKey) -> str:
    kind, name = _kind(media_type), key[0]
    if name == "trending":
        return f"trending:{kind}:week"
    if name == "top_rated":
        return f"top_rated:{kind}"
    if name == "recs" and key[1] is not None:
        return f"recs:{kind}:{key[1]}"
    raise ValueError(f"unknown list key {key!r}")


def _to_payload(items: list[ListItem]) -> list[dict]:
    return [
        {
            "tmdb_id": i.tmdb_id,
            "media_type": i.media_type,
            "name": i.name,
            "poster_path": i.poster_path,
            "year": i.year,
            "genre_ids": list(i.genre_ids),
            "vote_average": None if i.vote_average is None else round(i.vote_average, 1),
        }
        for i in items
    ]


def _from_payload(payload: list[dict]) -> list[ListItem]:
    return [
        ListItem(
            tmdb_id=p["tmdb_id"],
            media_type=p["media_type"],
            name=p["name"],
            poster_path=p["poster_path"],
            year=p["year"],
            genre_ids=tuple(p["genre_ids"]),
            vote_average=p["vote_average"],
        )
        for p in payload
    ]


class DiscoverService:
    def __init__(
        self,
        engine: Engine,
        tmdb: TmdbClient | None,
        titles: TitleService,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._tmdb = tmdb
        self._titles = titles  # for ensure_genres
        self._now = now

    # ===== Lists =====

    def lists(
        self, media_type: MediaType, keys: Sequence[ListKey], lang: Locale
    ) -> list[ServedList]:
        """The requested lists in order; one TMDB cannot supply and nothing is cached for is
        left out. For `he` the English payload of each list is loaded too, for `names_en`."""
        loaded: list[tuple[ListKey, _Loaded, dict[int, str | None]]] = []
        with deadline():
            for key in keys:
                primary = self._load(media_type, key, lang)
                if primary is None:
                    continue
                names_en: dict[int, str | None] = {}
                if lang == "he":
                    english = self._load(media_type, key, "en")
                    if english is not None:
                        names_en = {i.tmdb_id: i.name for i in english.items}
                loaded.append((key, primary, names_en))
            self._ensure_genres(loaded)

        with self._engine.connect() as conn:
            imdb = repo.imdb_ratings(
                conn, media_type, (i.tmdb_id for _, p, _ in loaded for i in p.items)
            )
        return [
            ServedList(
                key=key,
                items=primary.items,
                names_en=names_en,
                imdb={i.tmdb_id: imdb[i.tmdb_id] for i in primary.items if i.tmdb_id in imdb},
                fetched_at=primary.fetched_at,
                stale=primary.stale,
            )
            for key, primary, names_en in loaded
        ]

    def _ensure_genres(self, loaded: list[tuple[ListKey, _Loaded, dict[int, str | None]]]) -> None:
        ids = {g for _, p, _ in loaded for i in p.items for g in i.genre_ids}
        if not ids:
            return
        try:
            self._titles.ensure_genres(ids)
        except CatalogUnavailable:
            # The lists are still good; chips and genre names simply lack the unknown genres.
            logger.warning("Genre names unavailable for Discover lists")

    def _load(self, media_type: MediaType, key: ListKey, locale: Locale) -> _Loaded | None:
        cache_key = _cache_key(media_type, key)
        with self._engine.connect() as conn:
            cached = repo.get_cached_list(conn, cache_key, locale)
        now = self._now()
        if cached is not None and now - cached.fetched_at < LIST_REFRESH_AFTER:
            return _Loaded(_from_payload(cached.payload), cached.fetched_at, stale=False)

        payload = self._fetch(media_type, key, locale)
        if payload is None:  # TMDB unreachable: the cached list, if any, is better than none
            if cached is None:
                return None
            return _Loaded(_from_payload(cached.payload), cached.fetched_at, stale=True)
        with self._engine.begin() as conn:
            repo.put_cached_list(conn, cache_key, locale, payload, now)
        return _Loaded(_from_payload(payload), now, stale=False)

    def _fetch(self, media_type: MediaType, key: ListKey, locale: Locale) -> list[dict] | None:
        if self._tmdb is None:
            return None
        kind, language = _kind(media_type), _LANGUAGE[locale]
        try:
            if key[0] == "trending":
                raw = self._tmdb.trending(kind, language)
            elif key[0] == "top_rated":
                raw = self._tmdb.top_rated(kind, language)
            else:
                assert key[1] is not None
                raw = self._tmdb.recommendations(kind, key[1], language)
        except ExternalApiError:  # includes ExternalNotFound and an exhausted deadline
            return None
        return _to_payload(parse_list(raw, media_type))

    # ===== Reviews =====

    def reviews(self, title_id: int) -> list[repo.ReviewRow] | None:
        """Up to five TMDB reviews of a cached title, newest first; None for an unknown title."""
        with self._engine.connect() as conn:
            state = repo.review_state(conn, title_id)
        if state is None:
            return None
        now = self._now()
        due = (
            state.reviews_fetched_at is None
            or now - state.reviews_fetched_at >= REVIEWS_REFRESH_AFTER
        )
        if due and self._tmdb is not None:
            try:
                with deadline():
                    raw = self._tmdb.reviews(_kind(state.media_type), state.tmdb_id)
            except ExternalApiError:
                raw = None  # keep the cached rows; try again on the next request
            if raw is not None:
                records = parse_reviews(raw)[:MAX_REVIEWS]
                with self._engine.begin() as conn:
                    repo.store_reviews(conn, state.id, records, now)
        with self._engine.connect() as conn:
            return repo.newest_reviews(conn, state.id, MAX_REVIEWS)
