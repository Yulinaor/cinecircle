"""Cache-first title service: serve app.titles rows, refresh them from TMDB/OMDb when stale,
and fall back to the cached row when TMDB is down."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from cinecircle_api.catalog import repository as repo
from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound
from cinecircle_api.catalog.omdb_client import OmdbClient
from cinecircle_api.catalog.parse import (
    GenreRow,
    Locale,
    MediaType,
    SearchResult,
    TypeFilter,
    merge_genre_lists,
    parse_omdb,
    parse_search,
    parse_title,
)
from cinecircle_api.catalog.tmdb_client import TmdbClient

REFRESH_AFTER = timedelta(days=30)
OMDB_RETRY_AFTER = timedelta(days=1)  # OMDb free tier: 1,000 calls/day
_LANGUAGE = {"he": "he-IL", "en": "en-US"}
# Stored as raw_omdb when OMDb has no record, so only real failures (NULL) are retried daily.
OMDB_UNKNOWN = {"Response": "False"}


class CatalogUnavailable(Exception):
    """TMDB is not configured or not reachable, and nothing usable is cached."""


class TitleNotFound(Exception):
    """No such title in the cache (by internal id) or on TMDB."""


@dataclass(frozen=True)
class CachedTitle:
    row: repo.TitleRow
    stale: bool  # True when a refresh was due but TMDB could not be reached


class TitleService:
    def __init__(
        self,
        engine: Engine,
        tmdb: TmdbClient | None,
        omdb: OmdbClient | None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._tmdb = tmdb
        self._omdb = omdb
        self._now = now

    def search(self, query: str, type_filter: TypeFilter, lang: Locale) -> list[SearchResult]:
        if self._tmdb is None:
            raise CatalogUnavailable
        try:
            raw = self._tmdb.search_multi(query, _LANGUAGE[lang])
        except ExternalApiError:
            raise CatalogUnavailable from None
        return parse_search(raw, type_filter)

    def get(self, title_id: int) -> CachedTitle:
        with self._engine.connect() as conn:
            row = repo.get_title(conn, title_id)
        if row is None:
            raise TitleNotFound
        if self._is_fresh(row):
            return CachedTitle(row, stale=False)
        return self._refresh(row.tmdb_id, row.media_type, row)

    def get_by_tmdb(self, tmdb_id: int, media_type: MediaType) -> CachedTitle:
        with self._engine.connect() as conn:
            row = repo.get_title_by_tmdb(conn, tmdb_id, media_type)
        if row is not None and self._is_fresh(row):
            return CachedTitle(row, stale=False)
        return self._refresh(tmdb_id, media_type, row)

    def _is_fresh(self, row: repo.TitleRow) -> bool:
        age = self._now() - row.fetched_at
        if age >= REFRESH_AFTER:
            return False
        omdb_failed = row.raw_omdb is None and row.imdb_id is not None
        return not (omdb_failed and age >= OMDB_RETRY_AFTER)

    def _unreachable(self, cached: repo.TitleRow | None) -> CachedTitle:
        if cached is None:
            raise CatalogUnavailable
        return CachedTitle(cached, stale=True)

    def _refresh(
        self, tmdb_id: int, media_type: MediaType, cached: repo.TitleRow | None
    ) -> CachedTitle:
        if self._tmdb is None:
            return self._unreachable(cached)
        try:
            record = parse_title(self._tmdb.title_details(tmdb_id, media_type), media_type)
        except ExternalNotFound:
            # TMDB deletes/merges entries; a title we already hold stays readable (stale).
            if cached is not None:
                return CachedTitle(cached, stale=True)
            raise TitleNotFound from None
        except ExternalApiError:
            return self._unreachable(cached)

        raw_omdb = None
        if record.imdb_id and self._omdb is not None:
            try:
                # None = OMDb answered "no such title": a real answer, kept for 30 days.
                raw_omdb = self._omdb.by_imdb_id(record.imdb_id) or OMDB_UNKNOWN
            except ExternalApiError:
                raw_omdb = None  # ratings stay empty; retried after OMDB_RETRY_AFTER

        with self._engine.connect() as conn:
            missing = repo.missing_genre_ids(conn, record.genre_ids)
        genres = []
        if missing:
            try:
                genres = self._genre_rows()
            except ExternalApiError:
                return self._unreachable(cached)

        with self._engine.begin() as conn:
            repo.upsert_genres(conn, genres)
            title_id = repo.upsert_title(conn, record, parse_omdb(raw_omdb), raw_omdb, self._now())
            row = repo.get_title(conn, title_id)
        assert row is not None
        return CachedTitle(row, stale=False)

    def _genre_rows(self) -> list[GenreRow]:
        assert self._tmdb is not None
        en, he = [], []
        for kind in ("movie", "tv"):
            en += self._tmdb.genre_list(kind, "en-US").get("genres") or []
            he += self._tmdb.genre_list(kind, "he-IL").get("genres") or []
        return merge_genre_lists(en, he)
