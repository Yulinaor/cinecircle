import dataclasses
from datetime import UTC, datetime

import psycopg.errors
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

from cinecircle_api.catalog import repository as repo
from cinecircle_api.catalog.parse import (
    GenreRow,
    merge_genre_lists,
    parse_omdb,
    parse_title,
)
from tests.fixtures import load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_catalog")]
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def all_genres() -> list[GenreRow]:
    en = load("tmdb/genre_movie_en")["genres"] + load("tmdb/genre_tv_en")["genres"]
    he = load("tmdb/genre_movie_he")["genres"] + load("tmdb/genre_tv_he")["genres"]
    return merge_genre_lists(en, he)


def odyssey():
    return parse_title(load("tmdb/movie_odyssey"), "movie"), load("omdb/odyssey")


def test_upsert_then_get_round_trip(engine):
    record, raw_omdb = odyssey()
    ratings = parse_omdb(raw_omdb)
    with engine.begin() as conn:
        repo.upsert_genres(conn, all_genres())
        title_id = repo.upsert_title(conn, record, ratings, raw_omdb, T0)
    with engine.connect() as conn:
        row = repo.get_title(conn, title_id)
        assert repo.get_title_by_tmdb(conn, record.tmdb_id, "movie") == row
    assert row.id == title_id
    assert (row.tmdb_id, row.media_type, row.imdb_id) == (
        record.tmdb_id,
        "movie",
        record.imdb_id,
    )
    assert (row.name_en, row.name_he, row.overview_en, row.overview_he) == (
        record.name_en,
        record.name_he,
        record.overview_en,
        record.overview_he,
    )
    assert (row.year_start, row.runtime_min, row.tmdb_rating) == (
        record.year_start,
        record.runtime_min,
        record.tmdb_rating,
    )
    assert (row.imdb_rating, row.imdb_votes, row.rt_score, row.metacritic) == (
        ratings.imdb_rating,
        ratings.imdb_votes,
        ratings.rt_score,
        ratings.metacritic,
    )
    assert row.raw_omdb == raw_omdb and row.raw_tmdb["id"] == record.tmdb_id
    assert row.fetched_at == T0
    assert {g.id for g in row.genres} == set(record.genre_ids)
    assert all(g.name_en for g in row.genres)
    assert row.seasons == ()


def test_upsert_same_title_twice_keeps_one_row(engine):
    record, raw_omdb = odyssey()
    ratings = parse_omdb(raw_omdb)
    with engine.begin() as conn:
        repo.upsert_genres(conn, all_genres())
        first = repo.upsert_title(conn, record, ratings, raw_omdb, T0)
        changed = dataclasses.replace(record, overview_en="New plot")
        second = repo.upsert_title(conn, changed, ratings, raw_omdb, T0)
    assert first == second
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM app.titles")) == 1
        assert repo.get_title(conn, first).overview_en == "New plot"


def test_series_seasons_replaced_on_refresh(engine):
    record = parse_title(load("tmdb/tv_severance"), "series")
    ratings = parse_omdb(None)
    with engine.begin() as conn:
        repo.upsert_genres(conn, all_genres())
        title_id = repo.upsert_title(conn, record, ratings, None, T0)
        assert [s.season_number for s in repo.get_title(conn, title_id).seasons] == [
            s.season_number for s in record.seasons
        ]
        shorter = dataclasses.replace(record, seasons=record.seasons[:-1])
        repo.upsert_title(conn, shorter, ratings, None, T0)
        numbers = [s.season_number for s in repo.get_title(conn, title_id).seasons]
    assert numbers == [s.season_number for s in record.seasons[:-1]]
    assert record.seasons[-1].season_number not in numbers


def test_duplicate_imdb_id_is_dropped_not_fatal(engine):
    record, raw_omdb = odyssey()
    ratings = parse_omdb(raw_omdb)
    twin = dataclasses.replace(record, tmdb_id=record.tmdb_id + 1_000_000)
    with engine.begin() as conn:
        repo.upsert_genres(conn, all_genres())
        repo.upsert_title(conn, record, ratings, raw_omdb, T0)
        twin_id = repo.upsert_title(conn, twin, ratings, raw_omdb, T0)
        assert repo.get_title(conn, twin_id).imdb_id is None


def test_missing_genre_ids(engine):
    with engine.begin() as conn:
        repo.upsert_genres(conn, [GenreRow(18, "Drama", "דרמה")])
        assert repo.missing_genre_ids(conn, {18, 99999}) == {99999}


def test_rls_anon_cannot_read_catalog(engine):
    with engine.begin() as conn:
        conn.execute(sa.text("SET LOCAL ROLE anon"))
        with pytest.raises(ProgrammingError) as info:
            conn.execute(sa.text("SELECT * FROM app.titles"))
    assert isinstance(info.value.orig, psycopg.errors.InsufficientPrivilege)


def test_rls_authenticated_reads_but_cannot_write(engine):
    with engine.begin() as conn:
        conn.execute(sa.text("SET LOCAL ROLE authenticated"))
        conn.execute(sa.text("SELECT * FROM app.titles")).all()
        with pytest.raises(ProgrammingError) as info:
            conn.execute(sa.text("INSERT INTO app.genres (id, name_en) VALUES (1, 'x')"))
    assert isinstance(info.value.orig, psycopg.errors.InsufficientPrivilege)
