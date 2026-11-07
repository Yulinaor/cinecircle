"""Hand-written SQL for posts. Every function takes the request's `UserDb` connection: it runs as
the signed-in user, so RLS decides which posts exist for the caller (own posts, plus approved
followees' shared ones) and only the author may change one. The caller owns the transaction
(never commit or roll back here)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from cinecircle_api.catalog.parse import GenreRow, MediaType, TypeFilter
from cinecircle_api.pagination import PAGE_SIZE, Cursor
from cinecircle_api.people.repository import CardRow, card_columns, card_join_follow, pop_card_row
from cinecircle_api.posts.models import CreatePost

_UNIQUE = "posts_author_id_title_id_season_number_key"
_TITLE_FKEY = "posts_title_id_fkey"
_SEASON_VALID = "posts_season_valid"
EDITABLE = frozenset({"rating", "opinion", "contains_spoilers", "is_shared"})


class PostExists(Exception):
    """The caller already posted on this title and season."""

    def __init__(self, post_id: int) -> None:
        super().__init__(post_id)
        self.post_id = post_id


class TitleMissing(Exception):
    """No cached title has this id."""


class SeasonInvalid(Exception):
    """The season is negative, or the title is a movie or has no such season (plan P1)."""


@dataclass(frozen=True)
class PostRow:
    """Everything `post_card` needs: the post, its author's card, its title and season."""

    id: int
    title_id: int
    season_number: int
    rating: Decimal
    opinion: str | None
    contains_spoilers: bool
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    author: CardRow
    media_type: MediaType
    name_he: str | None
    name_en: str | None
    overview_he: str | None
    overview_en: str | None
    poster_path: str | None
    year_start: int | None
    runtime_min: int | None
    imdb_rating: Decimal | None
    tmdb_rating: Decimal | None
    genres: tuple[GenreRow, ...]
    season_name_he: str | None
    season_name_en: str | None
    season_overview_he: str | None
    season_overview_en: str | None
    season_poster_path: str | None

    @property
    def cursor(self) -> Cursor:
        return Cursor(self.created_at, self.id)


# The title columns of a card query (alias `t`): exactly what `card_title` reads, genres as
# [id, name_en, name_he] triples that `genre_rows` unpacks. Shared with the wishlist query.
TITLE_COLUMNS = (
    "t.media_type, t.name_he, t.name_en, t.overview_he, t.overview_en, t.poster_path,"
    " t.year_start, t.runtime_min, t.imdb_rating, t.tmdb_rating,"
    " COALESCE((SELECT json_agg(json_build_array(g.id, g.name_en, g.name_he) ORDER BY g.id)"
    "           FROM app.title_genres tg JOIN app.genres g ON g.id = tg.genre_id"
    "           WHERE tg.title_id = t.id), '[]') AS genres"
)

# The shared card query: `p` = the post, `pr` = its author, `f` = the viewer's follow row
# towards the author, `t` = the title, `s` = the season (no row for season 0). Callers append
# WHERE / ORDER BY / LIMIT and turn each row into a PostRow with `post_row`.
POST_SELECT = (
    "SELECT p.id, p.title_id, p.season_number, p.rating, p.opinion, p.contains_spoilers,"
    " p.is_shared, p.created_at, p.updated_at, "
    + card_columns("pr", "author_")
    + ", "
    + TITLE_COLUMNS
    + ", s.name_he AS season_name_he, s.name_en AS season_name_en,"
    " s.overview_he AS season_overview_he, s.overview_en AS season_overview_en,"
    " s.poster_path AS season_poster_path"
    " FROM app.posts p"
    " JOIN app.titles t ON t.id = p.title_id"
    " JOIN app.profiles pr ON pr.id = p.author_id"
    + card_join_follow("pr")
    + " LEFT JOIN app.title_seasons s"
    " ON s.title_id = p.title_id AND s.season_number = p.season_number AND p.season_number > 0"
)

_GET = sa.text(POST_SELECT + " WHERE p.id = :id")
_NEWEST_FIRST = " ORDER BY p.created_at DESC, p.id DESC LIMIT :limit"
_AFTER = " AND (p.created_at, p.id) < (:c_at, :c_id)"
_BY_AUTHOR = " WHERE p.author_id = :author_id"
_BY_TITLE = " WHERE p.title_id = :title_id"
# Home (plan P4): shared posts of the caller and of accepted followees. The explicit author
# filter lets the planner use posts_feed_idx; RLS stays the lock.
_FEED = (
    " WHERE p.is_shared AND (p.author_id = auth.uid() OR p.author_id IN ("
    "SELECT followee_id FROM app.follows WHERE follower_id = auth.uid() AND status = 'accepted'))"
)
_OF_TYPE = " AND t.media_type = :media_type"
_INSERT = sa.text(
    "INSERT INTO app.posts"
    " (author_id, title_id, season_number, rating, opinion, contains_spoilers, is_shared)"
    " VALUES (auth.uid(), :title_id, :season_number, :rating, :opinion, :contains_spoilers,"
    " :is_shared)"
    " RETURNING id"
)
_EXISTING = sa.text(
    "SELECT id FROM app.posts"
    " WHERE author_id = auth.uid() AND title_id = :title_id AND season_number = :season_number"
)
# The explicit author filter is belt and braces: RLS already limits writes to the author.
_IS_MINE = sa.text("SELECT 1 FROM app.posts WHERE id = :id AND author_id = auth.uid()")
_DELETE = sa.text("DELETE FROM app.posts WHERE id = :id AND author_id = auth.uid()")


def genre_rows(raw: list[list[Any]]) -> tuple[GenreRow, ...]:
    """The `genres` column of `TITLE_COLUMNS` as rows."""
    return tuple(GenreRow(*genre) for genre in raw)


def post_row(row: sa.Row) -> PostRow:
    fields = row._asdict()
    author = pop_card_row(fields, "author_")
    genres = genre_rows(fields.pop("genres"))
    return PostRow(**fields, author=author, genres=genres)


def _rating(value: float) -> Decimal:
    return Decimal(str(value))  # half steps are exact; NUMERIC(3,1) gets the decimal text


def get_post(conn: Connection, post_id: int) -> PostRow | None:
    """The post, or None when it does not exist or RLS hides it from the caller."""
    row = conn.execute(_GET, {"id": post_id}).one_or_none()
    return post_row(row) if row else None


def _newest_first(
    conn: Connection, where: str, params: dict[str, Any], after: Cursor | None, limit: int
) -> list[PostRow]:
    """`where` is one of the fixed fragments above, never user text; values go in `params`."""
    query = POST_SELECT + where
    params = {**params, "limit": limit}
    if after is not None:
        query += _AFTER
        params |= {"c_at": after.created_at, "c_id": after.id}
    return [post_row(row) for row in conn.execute(sa.text(query + _NEWEST_FIRST), params)]


def feed(
    conn: Connection, type_filter: TypeFilter, after: Cursor | None, limit: int
) -> list[PostRow]:
    """The caller's Home: shared posts by the caller and the people they follow, newest first."""
    where, params = _FEED, {}
    if type_filter != "all":
        where, params = where + _OF_TYPE, {"media_type": type_filter}
    return _newest_first(conn, where, params, after, limit)


def author_posts(
    conn: Connection, author_id: UUID, after: Cursor | None, limit: int
) -> list[PostRow]:
    """The author's posts the caller may see, newest first, after the `after` cursor."""
    return _newest_first(conn, _BY_AUTHOR, {"author_id": author_id}, after, limit)


def title_posts(conn: Connection, title_id: int, limit: int = PAGE_SIZE) -> list[PostRow]:
    """Posts on the title the caller may see (their own, plus followees' shared), newest first."""
    return _newest_first(conn, _BY_TITLE, {"title_id": title_id}, None, limit)


def create_post(conn: Connection, data: CreatePost) -> int:
    """Insert the caller's post and return its id. The savepoint keeps an expected violation
    from poisoning the request transaction."""
    values = data.model_dump()
    values["rating"] = _rating(data.rating)
    try:
        with conn.begin_nested():
            return conn.execute(_INSERT, values).scalar_one()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == _UNIQUE:
            existing = conn.scalar(
                _EXISTING, {"title_id": data.title_id, "season_number": data.season_number}
            )
            if existing is not None:  # None only if it was deleted in the meantime
                raise PostExists(existing) from None
        if constraint == _TITLE_FKEY:
            raise TitleMissing from None
        if constraint == _SEASON_VALID:
            raise SeasonInvalid from None
        raise


def update_post(conn: Connection, post_id: int, changes: dict[str, Any]) -> bool:
    """Change the given fields of the caller's post. False when no such post is the caller's
    (missing, hidden or someone else's). No changes is a successful no-op."""
    unknown = set(changes) - EDITABLE
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    if not changes:
        return conn.execute(_IS_MINE, {"id": post_id}).first() is not None
    values = dict(changes)
    if "rating" in values:
        values["rating"] = _rating(values["rating"])
    assignments = ", ".join(f"{column} = :{column}" for column in sorted(values))
    result = conn.execute(
        sa.text(f"UPDATE app.posts SET {assignments} WHERE id = :id AND author_id = auth.uid()"),
        {**values, "id": post_id},
    )
    return result.rowcount > 0


def delete_post(conn: Connection, post_id: int) -> bool:
    """Delete the caller's post. False when no such post is the caller's."""
    return conn.execute(_DELETE, {"id": post_id}).rowcount > 0
