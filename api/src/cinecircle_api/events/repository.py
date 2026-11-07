"""The owner-only event log (plan P9, R3.4). Events are analytics rows the caller writes about
their own actions; nothing reads them back into the product and no trigger turns one into a
notification. Every function takes the request's `UserDb` connection (`auth.uid()` is the owner)
and the caller owns the transaction (never commit or roll back here)."""

import json
from dataclasses import dataclass
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import Connection

EventType = Literal[
    "post_created",
    "post_viewed",
    "title_viewed",
    "saved",
    "watched",
    "onboarding_done",
    "discover_opened",
]

_INSERT = "INSERT INTO app.events (user_id, event_type, title_id, post_id, props) VALUES "
_ROW = "(auth.uid(), :type{n}, :title{n}, :post{n}, CAST(:props{n} AS jsonb))"


@dataclass(frozen=True)
class Event:
    event_type: EventType
    title_id: int | None = None
    post_id: int | None = None
    props: dict[str, Any] | None = None


def log(conn: Connection, *events: Event) -> None:
    """Append the events to the caller's log in one statement; a no-op for none. The statement
    text is built from fixed fragments and the event count only: every value is a bind."""
    if not events:
        return
    params: dict[str, Any] = {}
    for n, event in enumerate(events):
        params[f"type{n}"] = event.event_type
        params[f"title{n}"] = event.title_id
        params[f"post{n}"] = event.post_id
        params[f"props{n}"] = json.dumps(event.props) if event.props is not None else None
    values = ", ".join(_ROW.format(n=n) for n in range(len(events)))
    conn.execute(sa.text(_INSERT + values), params)
