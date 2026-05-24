# backend/models/db/outcome.py
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, UniqueConstraint, Boolean
from datetime import datetime
from db.session import Base


class Outcome(Base):
    """A logged visit outcome. Created either via the online /outcomes/record path
    (which internally calls sync with one item) or via /outcomes/sync (batch).
    Idempotency key is (device_id, client_outcome_id): the SAME outcome submitted
    twice from the same device will resolve to the same DB row.
    """
    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("device_id", "client_outcome_id", name="uq_device_client_outcome"),
    )

    # Primary key (server-assigned)
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Idempotency: client-side UUID generated on the device when the outcome was
    # recorded offline. NULL for outcomes that were submitted directly without a
    # device (legacy / non-device clients). When present, the unique constraint
    # above prevents double-insertion.
    client_outcome_id = Column(String, nullable=True, index=True)
    device_id         = Column(String, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)

    # Business fields
    entity_id        = Column(String, index=True)
    rep_id           = Column(String, index=True)
    visited_at       = Column(DateTime, default=datetime.utcnow)  # legacy field
    recorded_at      = Column(DateTime, default=datetime.utcnow)  # when it actually happened on-device
    outcome_rating   = Column(Integer)
    outcome_type     = Column(String)
    actions_taken    = Column(JSON)
    notes            = Column(String, nullable=True)
    signals_at_visit = Column(JSON, default=dict)
    synced_at        = Column(DateTime, default=datetime.utcnow)  # when server received it
    # Rep observation: was a competitor product seen at this visit? When True,
    # the outcome handler sets the grower's signal.payload.competitor_activity
    # so future priority scores reflect rep-observed competitive pressure.
    competitor_seen  = Column(Boolean, default=False, nullable=False)