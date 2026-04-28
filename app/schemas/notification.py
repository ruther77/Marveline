"""Schémas Pydantic — Notifications."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    tenant_id: int
    user_id: Optional[int]
    type: str
    title: str
    message: Optional[str]
    link: Optional[str]
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]

    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    items: list[NotificationRead]
    total: int
    skip: int
    limit: int
    unread_count: int
