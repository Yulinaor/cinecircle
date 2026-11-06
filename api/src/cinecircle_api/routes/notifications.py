"""The signed-in user's notifications (sign-in is enforced in main.py; a profile is required)."""

from fastapi import APIRouter, Depends, Response

from cinecircle_api.db import UserDb
from cinecircle_api.notifications import repository
from cinecircle_api.notifications.models import NotificationItem, NotificationsResponse
from cinecircle_api.people.deps import require_profile

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_profile)]
)


@router.get("")
def list_notifications(db: UserDb) -> NotificationsResponse:
    rows, unread_count = repository.list_notifications(db)
    items = [
        NotificationItem(
            id=row.id,
            type=row.type,
            actor=row.actor.card(),
            created_at=row.created_at,
            read=row.read,
            request_pending=row.request_pending,
        )
        for row in rows
    ]
    return NotificationsResponse(items=items, unread_count=unread_count)


@router.post("/read", status_code=204)
def mark_all_read(db: UserDb) -> Response:
    repository.mark_all_read(db)
    return Response(status_code=204)
