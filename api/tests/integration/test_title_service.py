from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cinecircle_api.catalog.service import CatalogUnavailable, TitleNotFound, TitleService
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
