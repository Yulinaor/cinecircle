from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from cinecircle_api.catalog import _http
from cinecircle_api.catalog._http import get_json
from cinecircle_api.catalog.errors import ExternalNotFound
from cinecircle_api.catalog.service import (
    OMDB_UNKNOWN,
    CatalogUnavailable,
    TitleNotFound,
    TitleService,
)
from tests.fakes import NO_HEBREW_ID, ODYSSEY_ID, SEVERANCE_ID, FakeOmdb, FakeTmdb

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = T0 + timedelta(**kwargs)


@pytest.fixture
def world(engine):
    tmdb, omdb, clock = FakeTmdb(), FakeOmdb(), Clock()
    return TitleService(engine, tmdb, omdb, now=clock), tmdb, omdb, clock


def test_first_get_fetches_and_caches(world):
    service, tmdb, omdb, _ = world
    cached = service.get_by_tmdb(ODYSSEY_ID, "movie")
    assert tmdb.calls["title_details"] == 1 and omdb.calls == 1
    assert cached.stale is False
    assert cached.row.imdb_rating == Decimal("8.4")


def test_second_get_within_30_days_makes_no_calls(world):
    service, tmdb, omdb, clock = world
    first = service.get_by_tmdb(ODYSSEY_ID, "movie")
    before = (sum(tmdb.calls.values()), omdb.calls)
    clock.advance(days=29)
    again = service.get_by_tmdb(ODYSSEY_ID, "movie")
    by_id = service.get(first.row.id)
    assert (sum(tmdb.calls.values()), omdb.calls) == before
    assert again.stale is False and by_id.stale is False and by_id.row.id == first.row.id


def test_refresh_after_30_days(world):
    service, tmdb, _, clock = world
    first = service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(days=30)
    again = service.get(first.row.id)
    assert tmdb.calls["title_details"] == 2
    assert again.row.fetched_at == clock.now and again.stale is False


def test_genres_loaded_once(world):
    service, tmdb, _, _ = world
    service.get_by_tmdb(ODYSSEY_ID, "movie")
    service.get_by_tmdb(SEVERANCE_ID, "series")
    assert tmdb.calls["genre_list"] == 4
    assert service.get_by_tmdb(SEVERANCE_ID, "series").row.genres


def test_omdb_down_still_stores_title(world):
    service, _, omdb, _ = world
    omdb.fail = True
    cached = service.get_by_tmdb(ODYSSEY_ID, "movie")
    assert cached.row.imdb_rating is None and cached.row.raw_omdb is None
    assert cached.row.name_en


def test_omdb_retried_after_one_day(world):
    service, tmdb, omdb, clock = world
    omdb.fail = True
    service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(hours=23)
    assert service.get_by_tmdb(ODYSSEY_ID, "movie").row.imdb_rating is None
    assert tmdb.calls["title_details"] == 1
    omdb.fail = False
    clock.advance(days=1)
    assert service.get_by_tmdb(ODYSSEY_ID, "movie").row.imdb_rating == Decimal("8.4")


def test_tmdb_down_serves_stale_row(world):
    service, tmdb, _, clock = world
    first = service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(days=31)
    tmdb.fail = True
    cached = service.get_by_tmdb(ODYSSEY_ID, "movie")
    assert cached.stale is True
    assert cached.row.fetched_at == T0 and cached.row.id == first.row.id


def test_tmdb_down_uncached_raises(world):
    service, tmdb, _, _ = world
    tmdb.fail = True
    with pytest.raises(CatalogUnavailable):
        service.get_by_tmdb(ODYSSEY_ID, "movie")


def test_tmdb_404_raises_not_found(world):
    service, _, _, _ = world
    with pytest.raises(TitleNotFound):
        service.get_by_tmdb(1, "movie")


def test_get_unknown_id_raises_not_found(world):
    service, tmdb, omdb, _ = world
    with pytest.raises(TitleNotFound):
        service.get(987654)
    assert sum(tmdb.calls.values()) == 0 and omdb.calls == 0


def test_no_keys_search_unavailable(engine):
    with pytest.raises(CatalogUnavailable):
        TitleService(engine, None, None).search("x", "all", "he")


def test_tmdb_404_on_refresh_serves_cached_row(world):
    service, tmdb, _, clock = world
    first = service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(days=31)
    tmdb.gone.add(ODYSSEY_ID)
    cached = service.get(first.row.id)
    assert tmdb.calls["title_details"] == 2
    assert cached.stale is True and cached.row.id == first.row.id


def test_omdb_unknown_title_is_not_retried_daily(world):
    service, tmdb, omdb, clock = world
    first = service.get_by_tmdb(NO_HEBREW_ID, "movie")  # FakeOmdb has no record for it
    assert first.row.imdb_id is not None and first.row.imdb_rating is None
    clock.advance(days=2)
    again = service.get_by_tmdb(NO_HEBREW_ID, "movie")
    assert (tmdb.calls["title_details"], omdb.calls) == (1, 1)
    assert again.stale is False


def test_omdb_retry_does_not_call_tmdb(world):
    service, tmdb, omdb, clock = world
    omdb.fail = True
    service.get_by_tmdb(ODYSSEY_ID, "movie")
    omdb.fail = False
    clock.advance(hours=25)
    cached = service.get_by_tmdb(ODYSSEY_ID, "movie")
    assert cached.row.imdb_rating == Decimal("8.4") and cached.stale is False
    assert tmdb.calls["title_details"] == 1 and omdb.calls == 2
    assert cached.row.fetched_at == T0  # the 30-day TMDB clock is untouched
    # By internal id the same path applies, and the filled row is now simply fresh.
    assert service.get(cached.row.id).row.imdb_rating == Decimal("8.4")
    assert (tmdb.calls["title_details"], omdb.calls) == (1, 2)


def test_omdb_retry_failing_again_serves_row_and_waits_another_day(world):
    service, tmdb, omdb, clock = world
    omdb.fail = True
    first = service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(hours=25)
    again = service.get(first.row.id)  # retry fails
    assert again.stale is False and again.row.imdb_rating is None and omdb.calls == 2
    clock.advance(hours=30)  # less than a day after the failed retry
    service.get(first.row.id)
    assert omdb.calls == 2
    omdb.fail = False
    clock.advance(hours=50)  # a day after the failed retry
    assert service.get(first.row.id).row.imdb_rating == Decimal("8.4")
    assert (tmdb.calls["title_details"], omdb.calls) == (1, 3)


def test_omdb_retry_with_unknown_title_stores_marker(world):
    service, tmdb, omdb, clock = world
    omdb.fail = True
    first = service.get_by_tmdb(NO_HEBREW_ID, "movie")  # FakeOmdb has no record for it
    omdb.fail = False
    clock.advance(hours=25)
    retried = service.get(first.row.id)
    assert retried.row.raw_omdb == OMDB_UNKNOWN and retried.row.imdb_rating is None
    clock.advance(days=2)
    service.get(first.row.id)
    assert (tmdb.calls["title_details"], omdb.calls) == (1, 2)


def test_omdb_retry_without_omdb_client_makes_no_calls(engine):
    tmdb, clock = FakeTmdb(), Clock()
    service = TitleService(engine, tmdb, None, now=clock)
    service.get_by_tmdb(ODYSSEY_ID, "movie")
    clock.advance(days=3)
    assert service.get_by_tmdb(ODYSSEY_ID, "movie").stale is False
    assert tmdb.calls["title_details"] == 1


def _season_one(service, title_id):
    row = service.get(title_id).row
    return next(s for s in row.seasons if s.season_number == 1)


def test_fill_season_text_once(world):
    service, tmdb, _, _ = world
    title = service.get_by_tmdb(SEVERANCE_ID, "series").row
    assert _season_one(service, title.id).name_he is None
    service.fill_season_text(title.id, 1)
    assert tmdb.calls["season_details"] == 1
    assert _season_one(service, title.id).name_he
    service.fill_season_text(title.id, 1)
    assert tmdb.calls["season_details"] == 1


def test_fill_season_text_ignores_failures(world, caplog):
    service, tmdb, _, _ = world
    title = service.get_by_tmdb(SEVERANCE_ID, "series").row
    tmdb.fail = True
    with caplog.at_level("WARNING"):
        service.fill_season_text(title.id, 1)  # no exception
    assert tmdb.calls["season_details"] == 1
    assert _season_one(service, title.id).name_he is None
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_fill_season_text_ignores_not_found(world):
    service, tmdb, _, _ = world
    title = service.get_by_tmdb(SEVERANCE_ID, "series").row
    tmdb.season_details = lambda *a: (_ for _ in ()).throw(ExternalNotFound("tmdb", 404))
    service.fill_season_text(title.id, 1)
    assert _season_one(service, title.id).name_he is None


def test_fill_season_text_skips_movies_and_missing(world):
    service, tmdb, _, _ = world
    movie = service.get_by_tmdb(ODYSSEY_ID, "movie").row
    series = service.get_by_tmdb(SEVERANCE_ID, "series").row
    service.fill_season_text(movie.id, 1)
    service.fill_season_text(series.id, 99)
    service.fill_season_text(987654, 1)
    assert tmdb.calls["season_details"] == 0


def test_fill_season_text_without_tmdb_is_a_noop(engine):
    clock = Clock()
    cached = TitleService(engine, FakeTmdb(), None, now=clock)
    title = cached.get_by_tmdb(SEVERANCE_ID, "series").row
    TitleService(engine, None, None, now=clock).fill_season_text(title.id, 1)
    assert _season_one(cached, title.id).name_he is None


def test_refresh_keeps_season_hebrew(world):
    service, tmdb, _, clock = world
    title = service.get_by_tmdb(SEVERANCE_ID, "series").row
    service.fill_season_text(title.id, 1)
    filled = _season_one(service, title.id)
    clock.advance(days=30)
    service.get(title.id)
    assert tmdb.calls["title_details"] == 2
    after = _season_one(service, title.id)
    assert after.name_he == filled.name_he and after.overview_he == filled.overview_he


def test_ensure_genres_fetches_once(world):
    service, tmdb, _, _ = world
    assert service.ensure_genres([28, 10759, 18]) == {28, 10759, 18}
    assert tmdb.calls["genre_list"] == 4
    assert service.ensure_genres([28, 18]) == {28, 18}  # all present now
    assert tmdb.calls["genre_list"] == 4
    assert service.ensure_genres([]) == set()
    assert service.ensure_genres([28, 424242]) == {28}  # TMDB lists no 424242: dropped
    assert tmdb.calls["genre_list"] == 8


def test_ensure_genres_unavailable(world, engine):
    service, tmdb, _, _ = world
    tmdb.fail = True
    with pytest.raises(CatalogUnavailable):
        service.ensure_genres([28])
    assert service.ensure_genres([]) == set()  # nothing to look up, nothing to fail
    with pytest.raises(CatalogUnavailable):
        TitleService(engine, None, None).ensure_genres([28])


class _SlowHttp:
    """Every request takes `seconds` of the fake clock."""

    def __init__(self, tick: list[float], seconds: float) -> None:
        self._tick, self._seconds = tick, seconds

    def get(self, url, params=None, headers=None, timeout=None) -> httpx.Response:
        self._tick[0] += self._seconds
        return httpx.Response(200, json={})


class _SlowTmdb(FakeTmdb):
    """A FakeTmdb whose calls go through get_json, so the request deadline applies."""

    def __init__(self, http: _SlowHttp) -> None:
        super().__init__()
        self._http = http

    def _call(self, name: str) -> None:
        get_json(self._http, "tmdb", f"https://tmdb.test/{name}", {})
        super()._call(name)  # counted only when the deadline let the call through


def test_title_service_cold_fetch_respects_budget(engine, monkeypatch):
    tick = [1000.0]
    monkeypatch.setattr(_http, "time", SimpleNamespace(monotonic=lambda: tick[0]))
    tmdb = _SlowTmdb(_SlowHttp(tick, seconds=4.0))
    service = TitleService(engine, tmdb, FakeOmdb())

    with pytest.raises(CatalogUnavailable):
        service.get_by_tmdb(ODYSSEY_ID, "movie")

    # details (10 s left), genres en (6 s left), genres he (2 s left); then the budget is spent.
    assert sum(tmdb.calls.values()) == 3
    assert tick[0] == 1012.0
