"""Keyset pagination (plan P5): pages of 20, newest first by (created_at, id).

A cursor is the URL-safe base64 (no padding) of "<created_at ISO-8601 with µs and offset>|<id>",
naming the last row of the page before. Callers fetch `limit + 1` rows and hand them to
`page_of`, which cuts the page and says whether there is a next one.
"""

import base64
import binascii
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, Query

PAGE_SIZE = 20
_MAX_CURSOR_LENGTH = 200
BIGINT_MAX = 2**63 - 1  # Postgres BIGINT: larger ids would fail in SQL, not as a 422/404
_ID = re.compile(r"[0-9]{1,19}")


@dataclass(frozen=True)
class Cursor:
    created_at: datetime
    id: int


def encode_cursor(c: Cursor) -> str:
    raw = f"{c.created_at.isoformat(timespec='microseconds')}|{c.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(raw: str) -> Cursor:
    """The cursor `raw` names; ValueError for anything `encode_cursor` could not have made."""
    if not raw or len(raw) > _MAX_CURSOR_LENGTH:
        raise ValueError("cursor length")
    try:
        text = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
        created_text, _, id_text = text.decode().partition("|")
    except (binascii.Error, UnicodeDecodeError):
        raise ValueError("cursor encoding") from None
    created_at = datetime.fromisoformat(created_text)  # ValueError when malformed
    if created_at.tzinfo is None:
        raise ValueError("cursor time has no offset")
    if not _ID.fullmatch(id_text) or int(id_text) > BIGINT_MAX:
        raise ValueError("cursor id")
    return Cursor(created_at, int(id_text))


def cursor_param(cursor: str | None = Query(None)) -> Cursor | None:
    """Dependency: the `cursor` query parameter, or 422 invalid_cursor."""
    if cursor is None:
        return None
    try:
        return decode_cursor(cursor)
    except ValueError:
        raise HTTPException(422, "invalid_cursor") from None


def page_of[T](
    rows: list[T], key: Callable[[T], Cursor], limit: int = PAGE_SIZE
) -> tuple[list[T], str | None]:
    """The first `limit` rows, and the cursor of the last one when more rows follow."""
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, encode_cursor(key(page[-1]))
