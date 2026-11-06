"""Hand-written SQL for follow requests and the follower/following lists. Every function takes the
request's `UserDb` connection: it runs as the signed-in user, so RLS and the column grants decide
what may change and `auth.uid()` is the caller. The caller owns the transaction (never commit or
roll back here). Notifications are written by database triggers, not here."""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.people.models import FollowState
from cinecircle_api.people.repository import CARD_COLUMNS, CARD_FROM, CardRow

_REQUEST = sa.text(
    "INSERT INTO app.follows (follower_id, followee_id) VALUES (auth.uid(), :target)"
    " ON CONFLICT DO NOTHING"
)
_MY_STATUS = sa.text(
    "SELECT status FROM app.follows WHERE follower_id = auth.uid() AND followee_id = :target"
)
_DELETE_MINE = sa.text(
    "DELETE FROM app.follows WHERE follower_id = auth.uid() AND followee_id = :target"
)
_ACCEPT = sa.text(
    "UPDATE app.follows SET status = 'accepted'"
    " WHERE follower_id = :follower AND followee_id = auth.uid() AND status = 'pending'"
)
_INCOMING_EXISTS = sa.text(
    "SELECT EXISTS (SELECT 1 FROM app.follows"
    " WHERE follower_id = :follower AND followee_id = auth.uid() AND status = 'accepted')"
)
_DELETE_INCOMING = sa.text(
    "DELETE FROM app.follows"
    " WHERE follower_id = :follower AND followee_id = auth.uid() AND status = :status"
)

# Lists: `p` is the person on the card, `x` the follows row that puts them in the list.
_LIST = (
    "SELECT "
    + CARD_COLUMNS
    + CARD_FROM
    + " JOIN app.follows x ON {join}"
    + " WHERE x.status = ANY(:statuses)"
    + " ORDER BY x.created_at DESC, p.username"
)
_FOLLOWERS = sa.text(_LIST.format(join="x.follower_id = p.id AND x.followee_id = auth.uid()"))
_FOLLOWING = sa.text(_LIST.format(join="x.followee_id = p.id AND x.follower_id = auth.uid()"))


def request_follow(conn: Connection, target_id: UUID) -> FollowState:
    """Ask to follow `target_id`. Idempotent: an existing request or follow is left untouched."""
    conn.execute(_REQUEST, {"target": target_id})
    status = conn.scalar(_MY_STATUS, {"target": target_id})
    return "following" if status == "accepted" else "requested"


def delete_my_follow(conn: Connection, target_id: UUID) -> None:
    """Cancel my request or stop following (a no-op when there is neither)."""
    conn.execute(_DELETE_MINE, {"target": target_id})


def accept_request(conn: Connection, follower_id: UUID) -> bool:
    """Accept a pending request to follow me. False when `follower_id` has no row towards me.
    An already-accepted row counts as success and is not updated again."""
    if conn.execute(_ACCEPT, {"follower": follower_id}).rowcount:
        return True
    return bool(conn.scalar(_INCOMING_EXISTS, {"follower": follower_id}))


def decline_request(conn: Connection, follower_id: UUID) -> bool:
    """Delete a *pending* request to follow me. False when there is none."""
    result = conn.execute(_DELETE_INCOMING, {"follower": follower_id, "status": "pending"})
    return bool(result.rowcount)


def remove_follower(conn: Connection, follower_id: UUID) -> bool:
    """Delete an *accepted* follower of mine. False when they are not one."""
    result = conn.execute(_DELETE_INCOMING, {"follower": follower_id, "status": "accepted"})
    return bool(result.rowcount)


def _cards(conn: Connection, query: sa.TextClause, statuses: list[str]) -> list[CardRow]:
    rows = conn.execute(query, {"statuses": statuses})
    return [CardRow(**row._asdict()) for row in rows]


def list_followers(conn: Connection) -> list[CardRow]:
    return _cards(conn, _FOLLOWERS, ["accepted"])


def list_following(conn: Connection) -> list[CardRow]:
    """Everyone I follow or have asked to follow (`follow_state` tells which)."""
    return _cards(conn, _FOLLOWING, ["accepted", "pending"])


def list_requests(conn: Connection) -> list[CardRow]:
    """Incoming pending requests, newest first."""
    return _cards(conn, _FOLLOWERS, ["pending"])
