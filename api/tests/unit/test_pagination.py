import base64
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from cinecircle_api.pagination import (
    PAGE_SIZE,
    Cursor,
    cursor_param,
    decode_cursor,
    encode_cursor,
    page_of,
)


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_cursor_roundtrip_and_junk():
    for cursor in (
        Cursor(datetime(2026, 11, 7, 9, 30, 1, 123456, tzinfo=UTC), 42),
        Cursor(datetime(2026, 11, 7, 12, 0, tzinfo=timezone(timedelta(hours=2))), 1),
    ):
        raw = encode_cursor(cursor)
        decoded = decode_cursor(raw)
        assert decoded == cursor
        assert decoded.created_at.utcoffset() == cursor.created_at.utcoffset()
        assert decoded.created_at.microsecond == cursor.created_at.microsecond
        assert "=" not in raw and "+" not in raw and "/" not in raw  # safe in a query string

    good = encode_cursor(Cursor(datetime(2026, 11, 7, 9, 30, 1, 123456, tzinfo=UTC), 42))
    for junk in (
        "garbage",
        "",
        good[: len(good) // 2],  # truncated
        good + "*",  # not base64
        _b64("x|1"),
        _b64("2026-11-07T00:00:00+00:00|abc"),
        _b64("2026-11-07T00:00:00+00:00|-1"),
        _b64("2026-11-07T00:00:00+00:00|99999999999999999999"),  # beyond BIGINT
        _b64("2026-11-07T00:00:00|1"),  # no offset
        _b64("2026-11-07T00:00:00+00:00"),  # no id
        "A" * 500,
    ):
        with pytest.raises(ValueError):
            decode_cursor(junk)


def test_cursor_param_answers_422_invalid_cursor():
    app = FastAPI()

    @app.get("/")
    def read(cursor: Annotated[Cursor | None, Depends(cursor_param)]) -> dict:
        return {"id": cursor.id if cursor else None}

    client = TestClient(app)
    assert client.get("/").json() == {"id": None}
    good = encode_cursor(Cursor(datetime(2026, 11, 7, tzinfo=UTC), 7))
    assert client.get("/", params={"cursor": good}).json() == {"id": 7}
    r = client.get("/", params={"cursor": "garbage"})
    assert (r.status_code, r.json()) == (422, {"detail": "invalid_cursor"})


def test_page_of():
    start = datetime(2026, 11, 7, tzinfo=UTC)
    rows = [Cursor(start - timedelta(minutes=n), 100 - n) for n in range(PAGE_SIZE + 1)]

    page, next_cursor = page_of(rows, key=lambda row: row)
    assert page == rows[:PAGE_SIZE]
    assert next_cursor is not None and decode_cursor(next_cursor) == rows[PAGE_SIZE - 1]

    page, next_cursor = page_of(rows[:PAGE_SIZE], key=lambda row: row)
    assert (page, next_cursor) == (rows[:PAGE_SIZE], None)

    assert page_of([], key=lambda row: row) == ([], None)
