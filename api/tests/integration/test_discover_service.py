from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from cinecircle_api.catalog.errors import ExternalApiError
from cinecircle_api.catalog.service import TitleService
from cinecircle_api.discover.models import item_name
from cinecircle_api.discover.service import DiscoverService
from tests.fakes import MATRIX_ID, ODYSSEY_ID, FakeOmdb, FakeTmdb

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]
T0 = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
TRENDING = ("trending", None)
TOP_RATED = ("top_rated", None)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = T0 + timedelta(**kwargs)


@pytest.fixture
def world(engine):
    tmdb, clock = FakeTmdb(), Clock()
    titles = TitleService(engine, tmdb, FakeOmdb(), now=clock)
    return DiscoverService(engine, tmdb, titles, now=clock), tmdb, clock, titles


def test_lists_are_cached_for_six_hours(world):
    service, tmdb, clock, _ = world
    first = service.lists("movie", [TRENDING], "en")
    assert tmdb.calls["trending"] == 1
    assert first[0].stale is False and first[0].fetched_at == T0 and len(first[0].items) == 6

    clock.advance(hours=5, minutes=59)
    again = service.lists("movie", [TRENDING], "en")
    assert tmdb.calls["trending"] == 1
    assert again[0].items == first[0].items and again[0].fetched_at == T0

    clock.advance(hours=6)
    refreshed = service.lists("movie", [TRENDING], "en")
    assert tmdb.calls["trending"] == 2
    assert refreshed[0].fetched_at == clock.now and refreshed[0].stale is False


def test_each_list_is_cached_under_its_own_key(world, engine):
    service, tmdb, _, _ = world
    served = service.lists("movie", [TRENDING, TOP_RATED, ("recs", MATRIX_ID)], "en")
    assert [s.key for s in served] == [TRENDING, TOP_RATED, ("recs", MATRIX_ID)]
    with engine.connect() as conn:
        keys = conn.scalars(sa.text("SELECT list_key FROM app.discover_cache ORDER BY 1")).all()
    assert keys == [f"recs:movie:{MATRIX_ID}", "top_rated:movie", "trending:movie:week"]
    service.lists("movie", [TRENDING, TOP_RATED, ("recs", MATRIX_ID)], "en")
    assert tmdb.calls["trending"] == tmdb.calls["top_rated"] == tmdb.calls["recommendations"] == 1


def test_series_use_tmdb_tv(world, engine):
    service, tmdb, _, _ = world
    served = service.lists("series", [TRENDING], "en")
    assert served[0].items and all(i.media_type == "series" for i in served[0].items)
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT list_key FROM app.discover_cache")) == "trending:tv:week"


def test_stale_lists_are_served(world):
    service, tmdb, clock, _ = world
    fresh = service.lists("movie", [TRENDING], "he")
    clock.advance(hours=7)
    tmdb.fail = True
    stale = service.lists("movie", [TRENDING], "he")
    assert stale[0].items == fresh[0].items
    assert stale[0].names_en == fresh[0].names_en
    assert stale[0].stale is True and stale[0].fetched_at == T0
    tmdb.fail = False
    assert service.lists("movie", [TRENDING], "he")[0].stale is False


def test_stale_list_is_not_rewritten_on_failure(world, engine):
    service, tmdb, clock, _ = world
    service.lists("movie", [TRENDING], "en")
    clock.advance(hours=7)
    tmdb.fail = True
    service.lists("movie", [TRENDING], "en")
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT fetched_at FROM app.discover_cache")) == T0


def test_nothing_cached_is_omitted(world):
    service, tmdb, _, _ = world
    tmdb.fail = True
    assert service.lists("movie", [TRENDING, TOP_RATED], "he") == []


def test_one_missing_list_does_not_hide_the_others(world):
    service, tmdb, _, _ = world
    service.lists("movie", [TRENDING], "en")
    tmdb.fail = True
    served = service.lists("movie", [TRENDING, TOP_RATED], "en")
    assert [s.key for s in served] == [TRENDING]


def test_no_tmdb_client_serves_the_cache_only(engine):
    clock = Clock()
    tmdb = FakeTmdb()
    titles = TitleService(engine, tmdb, None, now=clock)
    DiscoverService(engine, tmdb, titles, now=clock).lists("movie", [TRENDING], "en")
    clock.advance(hours=9)
    offline = DiscoverService(engine, None, titles, now=clock)
    served = offline.lists("movie", [TRENDING, TOP_RATED], "en")
    assert [s.key for s in served] == [TRENDING] and served[0].stale is True


def test_cache_is_per_locale(world, engine):
    service, tmdb, _, _ = world
    he = service.lists("movie", [TRENDING], "he")[0]
    assert tmdb.calls["trending"] == 2  # the Hebrew list and the English one for names_en
    with engine.connect() as conn:
        locales = conn.scalars(sa.text("SELECT locale FROM app.discover_cache ORDER BY 1")).all()
    assert locales == ["en", "he"]

    en = service.lists("movie", [TRENDING], "en")[0]
    assert tmdb.calls["trending"] == 2
    assert en.names_en == {}
    odyssey_he = next(i for i in he.items if i.tmdb_id == ODYSSEY_ID)
    odyssey_en = next(i for i in en.items if i.tmdb_id == ODYSSEY_ID)
    assert item_name(odyssey_he, he.names_en, "he") == ("האודיסאה", "he")
    assert item_name(odyssey_en, en.names_en, "en") == ("The Odyssey", "en")
    assert he.names_en[ODYSSEY_ID] == "The Odyssey"


def test_hebrew_names_fall_back_to_english(world):
    service, _, _, _ = world
    served = service.lists("movie", [TRENDING], "he")[0]
    # TMDB sent the original title for this one: no Hebrew letters in the he answer.
    model_citizen = next(i for i in served.items if i.tmdb_id == 1792170)
    assert model_citizen.name == "Model Citizen"
    assert item_name(model_citizen, served.names_en, "he") == ("Model Citizen", "en")
    odyssey = next(i for i in served.items if i.tmdb_id == ODYSSEY_ID)
    assert item_name(odyssey, served.names_en, "he")[1] == "he"


def test_hebrew_list_survives_the_english_one_failing(world, engine):
    service, tmdb, _, _ = world
    fail_en = tmdb.trending

    def trending(kind, language):
        if language == "en-US":
            tmdb.fail = True
        try:
            return fail_en(kind, language)
        finally:
            tmdb.fail = False

    tmdb.trending = trending  # the English call fails, the Hebrew one succeeds
    served = service.lists("movie", [TRENDING], "he")
    assert len(served) == 1 and served[0].names_en == {} and served[0].stale is False


def test_list_genres_exist_after_load(world, engine):
    service, _, _, _ = world
    checked = 0
    for media_type in ("movie", "series"):
        served = service.lists(media_type, [TRENDING, TOP_RATED], "he")
        assert len(served) == 2 and all(s.items for s in served)
        for one in served:
            wanted = {g for item in one.items for g in item.genre_ids}
            assert wanted
            with engine.connect() as conn:
                found = set(conn.scalars(sa.text("SELECT id FROM app.genres")).all())
            assert wanted <= found
            checked += len(wanted)
    assert checked > 0


def test_lists_are_served_when_genres_cannot_be_loaded(world, engine):
    service, tmdb, _, _ = world

    def no_genres(kind, language):
        raise ExternalApiError("tmdb", 503)

    tmdb.genre_list = no_genres
    served = service.lists("movie", [TRENDING], "en")
    assert len(served) == 1 and served[0].items
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM app.genres")) == 0


def test_imdb_ratings_for_cached_titles_only(world):
    service, _, _, titles = world
    titles.get_by_tmdb(ODYSSEY_ID, "movie")  # cached with its OMDb rating
    served = service.lists("movie", [TRENDING], "en")[0]
    assert served.imdb == {ODYSSEY_ID: 8.4}
    assert service.lists("series", [TRENDING], "en")[0].imdb == {}


def test_imdb_lookup_is_per_media_type(world, engine):
    # TMDB numbers movies and series separately, so one id can be both.
    service, _, _, _ = world
    movie_id = service.lists("movie", [TRENDING], "en")[0].items[0].tmdb_id
    series_id = service.lists("series", [TRENDING], "en")[0].items[0].tmdb_id
    insert = sa.text(
        "INSERT INTO app.titles (tmdb_id, media_type, name_en, imdb_rating, raw_tmdb)"
        " VALUES (:id, :mt, 'T', :rating, '{}')"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"id": movie_id, "mt": "movie", "rating": 7.1})
        conn.execute(insert, {"id": movie_id, "mt": "series", "rating": 3.2})
        conn.execute(insert, {"id": series_id, "mt": "series", "rating": 9.4})
        conn.execute(insert, {"id": series_id, "mt": "movie", "rating": 2.3})
    movies = service.lists("movie", [TRENDING], "en")[0]
    series = service.lists("series", [TRENDING], "en")[0]
    assert movies.imdb[movie_id] == 7.1 and series.imdb[series_id] == 9.4
    assert all(r in (7.1, 2.3) for r in movies.imdb.values())
    assert all(r in (3.2, 9.4) for r in series.imdb.values())


def test_imdb_rating_none_when_title_has_no_rating(world, engine):
    service, _, _, _ = world
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO app.titles (tmdb_id, media_type, name_en, raw_tmdb)"
                " VALUES (1423191, 'movie', 'Resident Evil', '{}')"
            )
        )
    served = service.lists("movie", [TRENDING], "en")[0]
    assert served.imdb == {1423191: None}


def test_payload_has_only_catalogue_fields(world, engine):
    service, _, _, _ = world
    service.lists("movie", [TRENDING], "en")
    with engine.connect() as conn:
        payload = conn.scalar(sa.text("SELECT payload FROM app.discover_cache"))
    assert set(payload[0]) == {
        "tmdb_id",
        "media_type",
        "name",
        "poster_path",
        "year",
        "genre_ids",
        "vote_average",
    }
    assert all(
        p["vote_average"] is None or p["vote_average"] == round(p["vote_average"], 1)
        for p in payload
    )


def _write_bad_row(engine, payload: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO app.discover_cache (list_key, locale, payload, fetched_at)"
                " VALUES ('trending:movie:week', 'en', CAST(:payload AS jsonb), :at)"
                " ON CONFLICT (list_key, locale) DO UPDATE SET"
                " payload = EXCLUDED.payload, fetched_at = EXCLUDED.fetched_at"
            ),
            {"payload": payload, "at": T0},
        )


@pytest.mark.parametrize(
    "bad",
    ['[{"tmdb_id": 1}]', '[{"tmdb_id": "x"}, 5]', '{"not": "a list"}', "null"],
    ids=["missing-keys", "wrong-shapes", "not-a-list", "null"],
)
def test_an_undecodable_cached_row_is_a_cache_miss(world, engine, bad):
    service, tmdb, clock, _ = world
    _write_bad_row(engine, bad)  # fresh by the clock: would be served for six hours
    served = service.lists("movie", [TRENDING], "en")
    assert tmdb.calls["trending"] == 1 and len(served[0].items) == 6  # refetched
    assert served[0].stale is False and served[0].fetched_at == clock.now
    again = service.lists("movie", [TRENDING], "en")  # the rewritten row decodes
    assert tmdb.calls["trending"] == 1 and again[0].items == served[0].items


def test_an_undecodable_cached_row_with_tmdb_down_omits_the_list(world, engine):
    service, tmdb, clock, _ = world
    _write_bad_row(engine, '[{"tmdb_id": 1}]')
    tmdb.fail = True
    assert service.lists("movie", [TRENDING], "en") == []
    clock.advance(hours=9)  # stale and undecodable
    assert service.lists("movie", [TRENDING], "en") == []
