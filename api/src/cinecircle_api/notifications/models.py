"""Response bodies for /notifications."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from cinecircle_api.people.models import UserCard

NotificationType = Literal["follow_request", "follow_accepted"]


class NotificationItem(BaseModel):
    id: int
    type: NotificationType
    actor: UserCard
    created_at: datetime
    read: bool
    request_pending: bool  # a follow_request whose follow row is still pending


class NotificationsResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int
