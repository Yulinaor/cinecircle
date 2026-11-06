"""Hand-written SQL for the signed-in user's notifications. They run as that user, so RLS
shows only their own (the explicit recipient filter is belt and braces). The caller owns the
transaction (never commit or roll back here). Rows are created by database triggers."""

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Connection

from cinecircle_api.notifications.models import NotificationType
from cinecircle_api.people.repository import CARD_COLUMNS, CARD_JOIN_FOLLOW, CardRow


@dataclass(frozen=True)
class NotificationRow:
    id: int
    type: NotificationType
    created_at: datetime
    read: bool
    request_pending: bool
    actor: CardRow


# `inc` is the actor's own row towards me: it is what makes a follow_request still actionable.
_LIST = sa.text(
    "SELECT n.id AS notification_id, n.type, n.created_at, (n.read_at IS NOT NULL) AS read,"
    " (n.type = 'follow_request' AND inc.status = 'pending') AS request_pending, "
    + CARD_COLUMNS
    + " FROM app.notifications n JOIN app.profiles p ON p.id = n.actor_id"
    + CARD_JOIN_FOLLOW
    + " LEFT JOIN app.follows inc ON inc.follower_id = n.actor_id AND inc.followee_id = auth.uid()"
    " WHERE n.recipient_id = auth.uid()"
    " ORDER BY n.created_at DESC, n.id DESC"
    " LIMIT :limit"
)
_UNREAD = sa.text(
    "SELECT count(*) FROM app.notifications WHERE recipient_id = auth.uid() AND read_at IS NULL"
)
_MARK_ALL_READ = sa.text(
    "UPDATE app.notifications SET read_at = now()"
    " WHERE recipient_id = auth.uid() AND read_at IS NULL"
)


def list_notifications(conn: Connection, limit: int = 50) -> tuple[list[NotificationRow], int]:
    """The newest `limit` notifications, and how many of all of them are unread."""
    items = []
    for row in conn.execute(_LIST, {"limit": limit}):
        fields = row._asdict()
        actor = CardRow(
            **{
                key: fields[key]
                for key in ("id", "username", "display_name", "avatar_url", "follow_state")
            }
        )
        items.append(
            NotificationRow(
                id=fields["notification_id"],
                type=fields["type"],
                created_at=fields["created_at"],
                read=fields["read"],
                request_pending=bool(fields["request_pending"]),
                actor=actor,
            )
        )
    return items, int(conn.scalar(_UNREAD) or 0)


def mark_all_read(conn: Connection) -> None:
    conn.execute(_MARK_ALL_READ)
