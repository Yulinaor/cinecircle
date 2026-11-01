"""Hand-written SQL for the catalogue tables. Every function takes an open Connection;
the caller owns the transaction."""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.catalog.parse import GenreRow, MediaType, OmdbRatings, TitleRecord

log = logging.getLogger(__name__)

_TITLE_COLUMNS = (
    "id, tmdb_id, media_type, imdb_id, name_en, name_he, overview_en, overview_he, "
    "year_start, year_end, runtime_min, season_count, poster_path, imdb_rating, imdb_votes, "
    "rt_score, metacritic, tmdb_rating, raw_tmdb, raw_omdb, fetched_at"
)


@dataclass(frozen=True)
class SeasonRow:
    season_number: int
    name_en: str | None
    name_he: str | None
    overview_en: str | None
    overview_he: str | None
    poster_path: str | None
    air_date: date | None
    episode_count: int | None


@dataclass(frozen=True)
class TitleRow:
    id: int
    tmdb_id: int
    media_type: MediaType
    imdb_id: str | None
    name_en: str
    name_he: str | None
    overview_en: str | None
    overview_he: str | None
    year_start: int | None
    year_end: int | None
    runtime_min: int | None
    season_count: int | None
    poster_path: str | None
    imdb_rating: Decimal | None
    imdb_votes: int | None
    rt_score: int | None
    metacritic: int | None
    tmdb_rating: Decimal | None
    raw_tmdb: dict
    raw_omdb: dict | None
    fetched_at: datetime
    genres: tuple[GenreRow, ...]
    seasons: tuple[SeasonRow, ...]


def _load(conn: Connection, where: str, params: dict) -> TitleRow | None:
    row = conn.execute(
        sa.text(f"SELECT {_TITLE_COLUMNS} FROM app.titles WHERE {where}"), params
    ).first()
    if row is None:
        return None
    genres = conn.execute(
        sa.text(
            "SELECT g.id, g.name_en, g.name_he FROM app.title_genres tg "
            "JOIN app.genres g ON g.id = tg.genre_id WHERE tg.title_id = :id ORDER BY g.id"
        ),
        {"id": row.id},
    ).all()
    seasons = conn.execute(
        sa.text(
            "SELECT season_number, name_en, name_he, overview_en, overview_he, poster_path, "
            "air_date, episode_count FROM app.title_seasons WHERE title_id = :id "
            "ORDER BY season_number"
        ),
        {"id": row.id},
    ).all()
    return TitleRow(
        **row._asdict(),
        genres=tuple(GenreRow(*g) for g in genres),
        seasons=tuple(SeasonRow(*s) for s in seasons),
    )


def get_title(conn: Connection, title_id: int) -> TitleRow | None:
    return _load(conn, "id = :id", {"id": title_id})


def get_title_by_tmdb(conn: Connection, tmdb_id: int, media_type: MediaType) -> TitleRow | None:
    return _load(
        conn, "tmdb_id = :tmdb_id AND media_type = :mt", {"tmdb_id": tmdb_id, "mt": media_type}
    )


def _free_imdb_id(conn: Connection, record: TitleRecord) -> str | None:
    """The record's imdb_id, or None when another title already holds it (imdb_id is UNIQUE)."""
    if record.imdb_id is None:
        return None
    holder = conn.execute(
        sa.text(
            "SELECT tmdb_id, media_type FROM app.titles WHERE imdb_id = :imdb "
            "AND NOT (tmdb_id = :tmdb_id AND media_type = :mt)"
        ),
        {"imdb": record.imdb_id, "tmdb_id": record.tmdb_id, "mt": record.media_type},
    ).first()
    if holder is None:
        return record.imdb_id
    log.warning(
        "imdb_id %s already belongs to tmdb %s %s; storing tmdb %s %s without it",
        record.imdb_id,
        holder.media_type,
        holder.tmdb_id,
        record.media_type,
        record.tmdb_id,
    )
    return None


_UPSERT_TITLE = sa.text("""
INSERT INTO app.titles (tmdb_id, media_type, imdb_id, name_en, name_he, overview_en, overview_he,
    year_start, year_end, runtime_min, season_count, poster_path, imdb_rating, imdb_votes,
    rt_score, metacritic, tmdb_rating, raw_tmdb, raw_omdb, fetched_at)
VALUES (:tmdb_id, :media_type, :imdb_id, :name_en, :name_he, :overview_en, :overview_he,
    :year_start, :year_end, :runtime_min, :season_count, :poster_path, :imdb_rating, :imdb_votes,
    :rt_score, :metacritic, :tmdb_rating, CAST(:raw_tmdb AS jsonb), CAST(:raw_omdb AS jsonb),
    :fetched_at)
ON CONFLICT (tmdb_id, media_type) DO UPDATE SET
    imdb_id = EXCLUDED.imdb_id, name_en = EXCLUDED.name_en, name_he = EXCLUDED.name_he,
    overview_en = EXCLUDED.overview_en, overview_he = EXCLUDED.overview_he,
    year_start = EXCLUDED.year_start, year_end = EXCLUDED.year_end,
    runtime_min = EXCLUDED.runtime_min, season_count = EXCLUDED.season_count,
    poster_path = EXCLUDED.poster_path, imdb_rating = EXCLUDED.imdb_rating,
    imdb_votes = EXCLUDED.imdb_votes, rt_score = EXCLUDED.rt_score,
    metacritic = EXCLUDED.metacritic, tmdb_rating = EXCLUDED.tmdb_rating,
    raw_tmdb = EXCLUDED.raw_tmdb, raw_omdb = EXCLUDED.raw_omdb, fetched_at = EXCLUDED.fetched_at
RETURNING id
""")

# Season names/overviews in Hebrew are filled later (Phase 3); a refresh keeps them.
_UPSERT_SEASON = sa.text("""
INSERT INTO app.title_seasons (title_id, season_number, name_en, overview_en, poster_path,
    air_date, episode_count)
VALUES (:title_id, :season_number, :name_en, :overview_en, :poster_path, :air_date, :episode_count)
ON CONFLICT (title_id, season_number) DO UPDATE SET
    name_en = EXCLUDED.name_en, overview_en = EXCLUDED.overview_en,
    poster_path = EXCLUDED.poster_path, air_date = EXCLUDED.air_date,
    episode_count = EXCLUDED.episode_count
""")


def _json(value: dict | None) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def upsert_title(
    conn: Connection,
    record: TitleRecord,
    ratings: OmdbRatings,
    raw_omdb: dict | None,
    fetched_at: datetime,
) -> int:
    title_id = conn.execute(
        _UPSERT_TITLE,
        {
            "tmdb_id": record.tmdb_id,
            "media_type": record.media_type,
            "imdb_id": _free_imdb_id(conn, record),
            "name_en": record.name_en,
            "name_he": record.name_he,
            "overview_en": record.overview_en,
            "overview_he": record.overview_he,
            "year_start": record.year_start,
            "year_end": record.year_end,
            "runtime_min": record.runtime_min,
            "season_count": record.season_count,
            "poster_path": record.poster_path,
            "imdb_rating": ratings.imdb_rating,
            "imdb_votes": ratings.imdb_votes,
            "rt_score": ratings.rt_score,
            "metacritic": ratings.metacritic,
            "tmdb_rating": record.tmdb_rating,
            "raw_tmdb": _json(record.raw_tmdb),
            "raw_omdb": _json(raw_omdb),
            "fetched_at": fetched_at,
        },
    ).scalar_one()

    conn.execute(sa.text("DELETE FROM app.title_genres WHERE title_id = :id"), {"id": title_id})
    if record.genre_ids:
        conn.execute(
            sa.text(
                "INSERT INTO app.title_genres (title_id, genre_id) VALUES (:title_id, :genre_id)"
            ),
            [{"title_id": title_id, "genre_id": g} for g in dict.fromkeys(record.genre_ids)],
        )

    numbers = [s.season_number for s in record.seasons]
    conn.execute(
        sa.text(
            "DELETE FROM app.title_seasons WHERE title_id = :id "
            "AND NOT (season_number = ANY(:numbers))"
        ),
        {"id": title_id, "numbers": numbers},
    )
    if record.seasons:
        conn.execute(
            _UPSERT_SEASON,
            [
                {
                    "title_id": title_id,
                    "season_number": s.season_number,
                    "name_en": s.name_en,
                    "overview_en": s.overview_en,
                    "poster_path": s.poster_path,
                    "air_date": s.air_date,
                    "episode_count": s.episode_count,
                }
                for s in record.seasons
            ],
        )
    return title_id


def missing_genre_ids(conn: Connection, ids: Iterable[int]) -> set[int]:
    wanted = set(ids)
    if not wanted:
        return set()
    found = conn.execute(
        sa.text("SELECT id FROM app.genres WHERE id = ANY(:ids)"), {"ids": list(wanted)}
    ).scalars()
    return wanted - set(found)


def upsert_genres(conn: Connection, rows: Iterable[GenreRow]) -> None:
    params = [{"id": r.id, "name_en": r.name_en, "name_he": r.name_he} for r in rows]
    if not params:
        return
    conn.execute(
        sa.text(
            "INSERT INTO app.genres (id, name_en, name_he) VALUES (:id, :name_en, :name_he) "
            "ON CONFLICT (id) DO UPDATE SET name_en = EXCLUDED.name_en, name_he = EXCLUDED.name_he"
        ),
        params,
    )
