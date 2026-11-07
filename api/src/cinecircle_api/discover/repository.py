"""Hand-written SQL for Discover's cache and the external reviews. Service session only: the
caller passes an open Connection and owns the transaction."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.catalog.parse import GenreRow, MediaType, ReviewRecord


@dataclass(frozen=True)
class CachedList:
    payload: list[dict]
    fetched_at: datetime


def get_cached_list(conn: Connection, list_key: str, locale: str) -> CachedList | None:
    row = conn.execute(
        sa.text(
            "SELECT payload, fetched_at FROM app.discover_cache "
            "WHERE list_key = :key AND locale = :locale"
        ),
        {"key": list_key, "locale": locale},
    ).first()
    return None if row is None else CachedList(payload=row.payload, fetched_at=row.fetched_at)


def put_cached_list(
    conn: Connection, list_key: str, locale: str, payload: list[dict], fetched_at: datetime
) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO app.discover_cache (list_key, locale, payload, fetched_at) "
            "VALUES (:key, :locale, CAST(:payload AS jsonb), :fetched_at) "
            "ON CONFLICT (list_key, locale) DO UPDATE SET "
            "payload = EXCLUDED.payload, fetched_at = EXCLUDED.fetched_at"
        ),
        {
            "key": list_key,
            "locale": locale,
            "payload": json.dumps(payload, ensure_ascii=False),
            "fetched_at": fetched_at,
        },
    )


def imdb_ratings(
    conn: Connection, media_type: MediaType, tmdb_ids: Iterable[int]
) -> dict[int, float | None]:
    """tmdb_id -> imdb_rating for the ids already cached in app.titles (others are absent)."""
    ids = list(set(tmdb_ids))
    if not ids:
        return {}
    rows = conn.execute(
        sa.text(
            "SELECT tmdb_id, imdb_rating FROM app.titles "
            "WHERE media_type = :mt AND tmdb_id = ANY(:ids)"
        ),
        {"mt": media_type, "ids": ids},
    )
    return {r.tmdb_id: None if r.imdb_rating is None else float(r.imdb_rating) for r in rows}


def genre_rows(conn: Connection, ids: Iterable[int]) -> dict[int, GenreRow]:
    """id -> GenreRow for the genre ids app.genres knows (unknown ids are absent)."""
    wanted = list(set(ids))
    if not wanted:
        return {}
    rows = conn.execute(
        sa.text("SELECT id, name_en, name_he FROM app.genres WHERE id = ANY(:ids)"),
        {"ids": wanted},
    )
    return {r.id: GenreRow(r.id, r.name_en, r.name_he) for r in rows}


@dataclass(frozen=True)
class TitleReviewState:
    id: int
    tmdb_id: int
    media_type: MediaType
    reviews_fetched_at: datetime | None


def review_state(conn: Connection, title_id: int) -> TitleReviewState | None:
    row = conn.execute(
        sa.text(
            "SELECT id, tmdb_id, media_type, reviews_fetched_at FROM app.titles WHERE id = :id"
        ),
        {"id": title_id},
    ).first()
    return None if row is None else TitleReviewState(**row._asdict())


@dataclass(frozen=True)
class ReviewRow:
    author_name: str
    excerpt: str
    url: str
    author_rating: float | None
    source: str


def store_reviews(
    conn: Connection, title_id: int, records: Iterable[ReviewRecord], fetched_at: datetime
) -> None:
    """Make `records` the title's stored reviews and remember the fetch (also when there were
    none): rows TMDB no longer returned are deleted, the rest upserted. One transaction, and only
    called after a successful TMDB answer, so a failed refresh never loses reviews."""
    records = list(records)
    params = [
        {
            "title_id": title_id,
            "rid": r.source_review_id,
            "author": r.author_name,
            "excerpt": r.excerpt,
            "url": r.url,
            "rating": r.author_rating,
            "language": r.language,
            "published_at": r.published_at,
            "fetched_at": fetched_at,
        }
        for r in records
    ]
    conn.execute(
        sa.text(
            "DELETE FROM app.external_reviews WHERE title_id = :id AND source = 'tmdb' "
            "AND NOT (source_review_id = ANY(:keep))"
        ),
        {"id": title_id, "keep": [r.source_review_id for r in records]},
    )
    if params:
        conn.execute(
            sa.text(
                "INSERT INTO app.external_reviews (title_id, source, source_review_id, "
                "author_name, excerpt, url, author_rating, language, published_at, fetched_at) "
                "VALUES (:title_id, 'tmdb', :rid, :author, :excerpt, :url, :rating, :language, "
                ":published_at, :fetched_at) "
                "ON CONFLICT (source, source_review_id) DO UPDATE SET "
                "author_name = EXCLUDED.author_name, excerpt = EXCLUDED.excerpt, "
                "url = EXCLUDED.url, author_rating = EXCLUDED.author_rating, "
                "language = EXCLUDED.language, published_at = EXCLUDED.published_at, "
                "fetched_at = EXCLUDED.fetched_at"
            ),
            params,
        )
    conn.execute(
        sa.text("UPDATE app.titles SET reviews_fetched_at = :at WHERE id = :id"),
        {"at": fetched_at, "id": title_id},
    )


def newest_reviews(conn: Connection, title_id: int, limit: int) -> list[ReviewRow]:
    rows = conn.execute(
        sa.text(
            "SELECT author_name, excerpt, url, author_rating, source FROM app.external_reviews "
            "WHERE title_id = :id ORDER BY published_at DESC NULLS LAST, id DESC LIMIT :limit"
        ),
        {"id": title_id, "limit": limit},
    )
    return [
        ReviewRow(
            author_name=r.author_name,
            excerpt=r.excerpt,
            url=r.url,
            author_rating=None if r.author_rating is None else float(r.author_rating),
            source=r.source,
        )
        for r in rows
    ]
