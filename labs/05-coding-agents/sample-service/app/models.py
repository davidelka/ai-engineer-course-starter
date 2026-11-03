"""Request and response models for the access-request service."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AccessLevel = Literal["read", "standard", "write", "admin"]
Route = Literal["auto_approve", "needs_manager", "needs_security"]
Status = Literal["pending", "approved", "denied"]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AccessRequestIn(BaseModel):
    """What an employee submits."""

    model_config = ConfigDict(extra="forbid")

    requester_email: str = Field(pattern=EMAIL_PATTERN)
    tool: str = Field(min_length=1, max_length=80)
    access_level: AccessLevel
    reason: str = Field(min_length=5, max_length=1000)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    production: bool = False
    customer_data: bool = False
    financial_data: bool = False
    external_sharing: bool = False


class AccessRequest(AccessRequestIn):
    """A stored request, with the route the policy chose and its current status."""

    id: str
    route: Route
    status: Status
    created_at: datetime
