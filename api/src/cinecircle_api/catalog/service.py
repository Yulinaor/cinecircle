"""Cache-first title service: serve app.titles rows, refresh them from TMDB/OMDb when stale,
and fall back to the cached row when TMDB is down."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from cinecircle_api.catalog import repository as repo
from cinecircle_api.catalog._http import deadline
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
    parse_season_text,
    parse_title,
)
from cinecircle_api.catalog.tmdb_client import TmdbClient

logger = logging.getLogger(__name__)

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
        # When OMDb was last asked about a title whose ratings are still missing. There is no
        # column for it (fetched_at is the TMDB data's age), so this lives in memory: it caps
        # retries at one a day per process and is simply forgotten on restart.
        self._omdb_tried: dict[int, datetime] = {}

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
        with deadline():  # a refresh is up to six sequential calls (plan P8)
            return self._serve(row)

    def get_by_tmdb(self, tmdb_id: int, media_type: MediaType) -> CachedTitle:
        with self._engine.connect() as conn:
            row = repo.get_title_by_tmdb(conn, tmdb_id, media_type)
        with deadline():
            if row is None:
                return self._refresh(tmdb_id, media_type, None)
            return self._serve(row)

    def fill_season_text(self, title_id: int, season_number: int) -> None:
        """Fetch a season's Hebrew name and overview from TMDB once, while both are unset.

        Best effort (P8): a missing series/season, a season already filled, no TMDB client or a
        TMDB failure all leave the row as it is; the UI falls back to English.
        """
        if self._tmdb is None:
            return
        with self._engine.connect() as conn:
            row = repo.get_title(conn, title_id)
        if row is None or row.media_type != "series":
            return
        season = next((s for s in row.seasons if s.season_number == season_number), None)
        if season is None or season.name_he is not None or season.overview_he is not None:
            return
        try:
            with deadline():
                raw = self._tmdb.season_details(row.tmdb_id, season_number, "he-IL")
        except (ExternalApiError, ExternalNotFound) as err:
            logger.warning(
                "Hebrew season text unavailable for title %s season %s: %s",
                title_id,
                season_number,
                type(err).__name__,
            )
            return
        name_he, overview_he = parse_season_text(raw)
        with self._engine.begin() as conn:
            repo.update_season_text(conn, title_id, season_number, name_he, overview_he)

    def ensure_genres(self, ids: Iterable[int]) -> set[int]:
        """Make sure the genre rows for `ids` exist, fetching TMDB's lists once when any are
        missing. Returns the ids present afterwards: ones TMDB does not list are dropped.

        Raises CatalogUnavailable when genres are missing and TMDB is absent or failing.
        """
        wanted = set(ids)
        with self._engine.connect() as conn:
            missing = repo.missing_genre_ids(conn, wanted)
        if not missing:
            return wanted
        if self._tmdb is None:
            raise CatalogUnavailable
        try:
            with deadline():
                rows = self._genre_rows()
        except ExternalApiError:
            raise CatalogUnavailable from None
        with self._engine.begin() as conn:
            repo.upsert_genres(conn, rows)
        return wanted - (missing - {row.id for row in rows})

    def _serve(self, row: repo.TitleRow) -> CachedTitle:
        now = self._now()
        if now - row.fetched_at >= REFRESH_AFTER:
            return self._refresh(row.tmdb_id, row.media_type, row)
        if self._omdb_retry_due(row, now):
            return self._retry_omdb(row)
        return CachedTitle(row, stale=False)

    def _omdb_retry_due(self, row: repo.TitleRow, now: datetime) -> bool:
        """OMDb failed when the row was cached (raw_omdb NULL) and a day has passed since."""
        if self._omdb is None or row.raw_omdb is not None or row.imdb_id is None:
            return False
        last_try = self._omdb_tried.get(row.id, row.fetched_at)
        return now - last_try >= OMDB_RETRY_AFTER

    def _retry_omdb(self, row: repo.TitleRow) -> CachedTitle:
        """Fill in the ratings only: the TMDB part of the row is still fresh, so TMDB is not
        called and fetched_at (the 30-day TMDB clock) is left alone."""
        assert self._omdb is not None and row.imdb_id is not None
        raw_omdb = self._ask_omdb(row.imdb_id)
        if raw_omdb is None:
            self._omdb_tried[row.id] = self._now()
            return CachedTitle(row, stale=False)  # still unrated; asked again in a day
        self._omdb_tried.pop(row.id, None)
        with self._engine.begin() as conn:
            repo.update_omdb(conn, row.id, row.imdb_id, parse_omdb(raw_omdb), raw_omdb)
            updated = repo.get_title(conn, row.id)
        assert updated is not None
        return CachedTitle(updated, stale=False)

    def _ask_omdb(self, imdb_id: str) -> dict | None:
        """OMDb's record, OMDB_UNKNOWN when it has none, None when the call failed."""
        assert self._omdb is not None
        try:
            # No such title is a real answer, kept for 30 days.
            return self._omdb.by_imdb_id(imdb_id) or OMDB_UNKNOWN
        except ExternalApiError:
            return None  # ratings stay empty; retried after OMDB_RETRY_AFTER

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
            raw_omdb = self._ask_omdb(record.imdb_id)

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
        self._omdb_tried.pop(row.id, None)  # fetched_at is the newest attempt now
        return CachedTitle(row, stale=False)

    def _genre_rows(self) -> list[GenreRow]:
        assert self._tmdb is not None
        en, he = [], []
        for kind in ("movie", "tv"):
            en += self._tmdb.genre_list(kind, "en-US").get("genres") or []
            he += self._tmdb.genre_list(kind, "he-IL").get("genres") or []
        return merge_genre_lists(en, he)
