"""The viewer's own side of Discover: the titles that seed "Because you rated X" (plan P2) and
the titles to keep out of the recommendations. Every function takes a `user_transaction`
connection: it runs as the signed-in user and only ever reads that user's own posts
(`author_id = auth.uid()`), whatever RLS would also let through (spec 00 R4.5). The caller owns
the transaction (never commit or roll back here)."""

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.catalog.parse import MediaType

SEED_MIN_RATING = 8.0
MAX_SEEDS = 2

# One rating per title (03 section 2): the whole-title rating when there is one, else the average
# of the season ratings. Highest first, then the title with the newest post.
_SEEDS = sa.text(
    "WITH my AS ("
    " SELECT title_id,"
    "  COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r,"
    "  MAX(created_at) AS newest"
    " FROM app.posts WHERE author_id = auth.uid() GROUP BY title_id)"
    " SELECT t.id AS title_id, t.tmdb_id, t.name_he, t.name_en, my.r AS rating"
    " FROM my JOIN app.titles t ON t.id = my.title_id"
    " WHERE t.media_type = :media_type AND my.r >= :min_rating"
    " ORDER BY my.r DESC, my.newest DESC, t.id DESC LIMIT :limit"
)
_RATED = sa.text(
    "SELECT DISTINCT t.tmdb_id, t.media_type"
    " FROM app.posts p JOIN app.titles t ON t.id = p.title_id WHERE p.author_id = auth.uid()"
)


@dataclass(frozen=True)
class SeedRow:
    title_id: int
    tmdb_id: int
    name_he: str | None
    name_en: str
    rating: float  # 1-10, one decimal


def my_seeds(conn: Connection, media_type: MediaType) -> list[SeedRow]:
    """Up to two of the caller's own titles of this type rated 8.0 or more, best first."""
    rows = conn.execute(
        _SEEDS, {"media_type": media_type, "min_rating": SEED_MIN_RATING, "limit": MAX_SEEDS}
    )
    return [
        SeedRow(r.title_id, r.tmdb_id, r.name_he, r.name_en, round(float(r.rating), 1))
        for r in rows
    ]


def my_rated(conn: Connection) -> set[tuple[int, MediaType]]:
    """(tmdb_id, media_type) of every title the caller has rated, of either type."""
    return {(r.tmdb_id, r.media_type) for r in conn.execute(_RATED)}
