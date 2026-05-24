# backend/models/schemas/outcome.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# ---- legacy schemas (kept for backward compatibility) ----

class VisitOutcome(BaseModel):
    entity_id:        str
    rep_id:           str
    visited_at:       datetime
    vps_at_visit:     float
    actions_taken:    list[str]
    outcome_rating:   int
    outcome_type:     str
    notes:            str
    competitor_seen:  bool = False
    signals_at_visit: dict


class OutcomeRecord(BaseModel):
    """Single-outcome submission. Routes that accept this internally convert it
    to a single-item SyncRequest before storing — same code path, idempotency
    benefits if a `client_outcome_id` is supplied.
    """
    entity_id:        str
    rep_id:           Optional[str] = None   # supplied by JWT server-side; client value is ignored
    outcome_rating:   int
    outcome_type:     str
    actions_taken:    list[str]
    actions_accepted: list[str] = []
    notes:            Optional[str] = None
    competitor_seen:   bool = False
    # Optional sync hints — if supplied, this submission gets idempotency too
    client_outcome_id: Optional[str] = None
    device_id:         Optional[str] = None
    recorded_at:       Optional[datetime] = None


# ---- new sync schemas ----

class SyncOutcomeItem(BaseModel):
    """One outcome in a batch sync request."""
    client_outcome_id: str = Field(..., description="UUID generated on the device when recorded")
    entity_id:         str
    outcome_rating:    int
    outcome_type:      str
    actions_taken:     List[str]
    actions_accepted:  List[str] = []
    notes:             Optional[str] = None
    competitor_seen:   bool = False
    recorded_at:       Optional[datetime] = None   # when it happened on-device


class SyncRequest(BaseModel):
    device_id: str = Field(..., description="Client-generated device UUID")
    device_name:     Optional[str] = Field(None, description="Human label e.g. 'Ravi's phone'")
    device_platform: Optional[Literal["android", "ios", "web"]] = None
    outcomes: List[SyncOutcomeItem] = Field(..., min_length=1, max_length=200)


class SyncResultItem(BaseModel):
    client_outcome_id: str
    server_outcome_id: Optional[int] = None
    status: Literal["created", "duplicate", "failed"]
    error: Optional[str] = None


class SyncResponse(BaseModel):
    synced_at: datetime
    device_id: str
    total: int
    created_count: int
    duplicate_count: int
    failed_count: int
    results: List[SyncResultItem]


# ---- device schemas ----

class DeviceOut(BaseModel):
    id: str
    name: Optional[str] = None
    platform: Optional[str] = None
    is_revoked: bool
    first_seen_at: datetime
    last_seen_at: datetime
    last_sync_at: Optional[datetime] = None
    sync_count: str

    class Config:
        from_attributes = True