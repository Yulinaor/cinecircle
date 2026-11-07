"""Hand-written SQL for the wishlist. Every function takes the request's `UserDb` connection: it
runs as the signed-in user, so RLS limits every row to the caller's own list and `auth.uid()` is
the owner. The caller owns the transaction (never commit or roll back here)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from cinecircle_api.catalog.parse import GenreRow, MediaType
from cinecircle_api.pagination import Cursor
from cinecircle_api.people.repository import CardRow, card_join_follow, follow_state_sql
from cinecircle_api.wishlist.models import SaveTitle, WishlistSource, WishlistStatus

_SOURCE_VALID = "wishlist_source_valid"  # raised by the app.wishlist_check_source trigger
_TITLE_FKEY = "wishlist_items_title_id_fkey"
_VIA_FIELDS = ("id", "username", "display_name", "avatar_url", "follow_state")

# For other queries: whether the caller's own list holds a title. `{title}` is a column
# reference (or a bind parameter). It reflects nobody else's list (plan P5).
IN_WISHLIST_SQL = (
    "EXISTS (SELECT 1 FROM app.wishlist_items w"
    " WHERE w.owner_id = auth.uid() AND w.title_id = {title})"
)


class TitleMissing(Exception):
    """No cached title has this id."""


class SourceInvalid(Exception):
    """The source post is missing, hidden from the caller, on another title, or not allowed with
    this source. One error for all of them, so the answer does not leak which (plan P1)."""


@dataclass(frozen=True)
class WishlistRow:
    """Everything `wishlist_item` needs: the item, its title, the post it came from (only while
    the owner can see that post) and the owner's own newest post on the title."""

    title_id: int
    status: WishlistStatus
    source: WishlistSource
    added_at: datetime
    watched_at: datetime | None
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
    via_post_id: int | None
    via_author: CardRow | None
    my_post_id: int | None
    my_rating: Decimal | None

    @property
    def cursor(self) -> Cursor:
        """Watched items are listed by when they were watched, the rest by when they were added."""
        stamp = self.watched_at if self.status == "watched" and self.watched_at else self.added_at
        return Cursor(stamp, self.title_id)


# `w` = the item, `t` = its title, `vp` = the source post (RLS hides it unless the owner may see
# it), `pr` = that post's author, `f` = the owner's follow row towards the author, `mp` = the
# owner's newest post on the title. Callers append more conditions, ORDER BY and LIMIT.
_SELECT = (
    "SELECT w.title_id, w.status, w.source, w.added_at, w.watched_at,"
    " t.media_type, t.name_he, t.name_en, t.overview_he, t.overview_en, t.poster_path,"
    " t.year_start, t.runtime_min, t.imdb_rating, t.tmdb_rating,"
    " COALESCE((SELECT json_agg(json_build_array(g.id, g.name_en, g.name_he) ORDER BY g.id)"
    "           FROM app.title_genres tg JOIN app.genres g ON g.id = tg.genre_id"
    "           WHERE tg.title_id = t.id), '[]') AS genres,"
    " vp.id AS via_post_id,"
    " pr.id AS via_author_id, pr.username AS via_author_username,"
    " pr.display_name AS via_author_display_name, pr.avatar_url AS via_author_avatar_url, "
    + follow_state_sql("pr")
    + " AS via_author_follow_state,"
    " mp.id AS my_post_id, mp.rating AS my_rating"
    " FROM app.wishlist_items w"
    " JOIN app.titles t ON t.id = w.title_id"
    " LEFT JOIN app.posts vp ON vp.id = w.source_post_id"
    " LEFT JOIN app.profiles pr ON pr.id = vp.author_id"
    + card_join_follow("pr")
    + " LEFT JOIN LATERAL (SELECT p.id, p.rating FROM app.posts p"
    "   WHERE p.author_id = auth.uid() AND p.title_id = w.title_id"
    "   ORDER BY p.created_at DESC, p.id DESC LIMIT 1) mp ON true"
    " WHERE w.owner_id = auth.uid()"
)
_GET = sa.text(_SELECT + " AND w.title_id = :title_id")
# Fixed fragments, never user text: the list differs by status only in these.
_WANT = " AND w.status = 'want'"
_WATCHED = " AND w.status = 'watched'"
_AFTER_WANT = " AND (w.added_at, w.title_id) < (:c_at, :c_id)"
_AFTER_WATCHED = " AND (w.watched_at, w.title_id) < (:c_at, :c_id)"
_BY_ADDED = " ORDER BY w.added_at DESC, w.title_id DESC LIMIT :limit"
_BY_WATCHED = " ORDER BY w.watched_at DESC, w.title_id DESC LIMIT :limit"
# ON CONFLICT DO NOTHING: saving twice keeps the first row (plan P4). watched_at and the source
# check are the database's job (triggers). The explicit owner is belt and braces beside RLS.
_INSERT = sa.text(
    "INSERT INTO app.wishlist_items (owner_id, title_id, source, source_post_id)"
    " VALUES (auth.uid(), :title_id, :source, :source_post_id)"
    " ON CONFLICT (owner_id, title_id) DO NOTHING"
)
_SET_STATUS = sa.text(
    "UPDATE app.wishlist_items SET status = :status"
    " WHERE owner_id = auth.uid() AND title_id = :title_id"
)
_MARK_WATCHED = sa.text(
    "UPDATE app.wishlist_items SET status = 'watched'"
    " WHERE owner_id = auth.uid() AND title_id = :title_id AND status = 'want'"
)
_DELETE = sa.text(
    "DELETE FROM app.wishlist_items WHERE owner_id = auth.uid() AND title_id = :title_id"
)


def wishlist_row(row: sa.Row) -> WishlistRow:
    fields = row._asdict()
    via = {key: fields.pop(f"via_author_{key}") for key in _VIA_FIELDS}
    genres = tuple(GenreRow(*genre) for genre in fields.pop("genres"))
    via_author = CardRow(**via) if via["id"] is not None else None
    return WishlistRow(**fields, via_author=via_author, genres=genres)


def get_item(conn: Connection, title_id: int) -> WishlistRow | None:
    """The caller's item on the title, or None when it is not on their list."""
    row = conn.execute(_GET, {"title_id": title_id}).one_or_none()
    return wishlist_row(row) if row else None


def list_items(
    conn: Connection, status: WishlistStatus, after: Cursor | None, limit: int
) -> list[WishlistRow]:
    """The caller's items with this status, newest first (Want by when added, Watched by when
    watched), after the `after` cursor."""
    watched = status == "watched"
    query = _SELECT + (_WATCHED if watched else _WANT)
    params: dict[str, Any] = {"limit": limit}
    if after is not None:
        query += _AFTER_WATCHED if watched else _AFTER_WANT
        params |= {"c_at": after.created_at, "c_id": after.id}
    query += _BY_WATCHED if watched else _BY_ADDED
    return [wishlist_row(row) for row in conn.execute(sa.text(query), params)]


def save(conn: Connection, data: SaveTitle) -> bool:
    """Put the title on the caller's list. True when a row was added, False when the title was
    already there (its first source stays). The savepoint keeps an expected violation from
    poisoning the request transaction."""
    try:
        with conn.begin_nested():
            return conn.execute(_INSERT, data.model_dump()).rowcount > 0
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == _SOURCE_VALID:
            raise SourceInvalid from None
        if constraint == _TITLE_FKEY:
            raise TitleMissing from None
        raise


def set_status(conn: Connection, title_id: int, status: WishlistStatus) -> bool:
    """Move the caller's item to `status`. False when the title is not on their list."""
    return conn.execute(_SET_STATUS, {"title_id": title_id, "status": status}).rowcount > 0


def remove(conn: Connection, title_id: int) -> bool:
    """Take the title off the caller's list. False when it was not there."""
    return conn.execute(_DELETE, {"title_id": title_id}).rowcount > 0


def mark_watched_on_post(conn: Connection, title_id: int) -> None:
    """The caller posted on the title: their `want` item on it becomes `watched`, in the same
    transaction as the post (plan P9). A no-op when there is no such item."""
    conn.execute(_MARK_WATCHED, {"title_id": title_id})
