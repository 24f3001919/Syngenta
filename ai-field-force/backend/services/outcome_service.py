# backend/services/outcome_service.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from models.db.outcome import Outcome
from models.db.farmers import FarmerRetailer
from models.db.signal import Signal
from models.schemas.outcome import (
    OutcomeRecord,
    SyncRequest,
    SyncOutcomeItem,
    SyncResponse,
    SyncResultItem,
)
from services.device_service import DeviceService
from services.weight_service import WeightService
from core.ml.weight_updater import update_weights


# Signal keys that the weight updater understands. Boolean/string signals
# are converted to numeric before being fed in (the updater multiplies them).
_NUMERIC_SIGNAL_KEYS = {
    "pest_alert_severity",      # string -> 0/0.33/0.66/1.0
    "inventory_shortage_level", # already 0.0-1.0
    "days_since_last_visit",    # int days -> normalized 0-1 (capped at 90 days)
    "weather_risk_score",       # already 0.0-1.0
    "complaint_open",           # bool -> 0/1
    "crop_stage_sensitivity",   # already 0.0-1.0
    "revenue_potential",        # 0-100000 -> normalized 0-1
    "competitor_activity",      # bool -> 0/1
}

_PEST_SEVERITY_NUMERIC = {
    "none": 0.0, "low": 0.33, "medium": 0.66, "high": 1.0,
}


def _normalize_signal_payload(payload: dict) -> dict:
    """Convert the raw Signal.payload dict into numeric values the updater
    can multiply against weights. Anything missing or odd → 0.0.
    """
    if not payload:
        return {k: 0.0 for k in _NUMERIC_SIGNAL_KEYS}

    out = {}
    out["pest_alert_severity"] = _PEST_SEVERITY_NUMERIC.get(
        str(payload.get("pest_alert_severity") or "none").lower(), 0.0
    )
    out["inventory_shortage_level"] = float(payload.get("inventory_shortage_level") or 0.0)
    days = int(payload.get("days_since_last_visit") or 0)
    out["days_since_last_visit"] = min(1.0, days / 90.0)  # 90+ days → max
    out["weather_risk_score"] = float(payload.get("weather_risk_score") or 0.0)
    out["complaint_open"] = 1.0 if payload.get("complaint_open") else 0.0
    out["crop_stage_sensitivity"] = float(payload.get("crop_stage_sensitivity") or 0.0)
    rev = float(payload.get("revenue_potential") or 0.0)
    out["revenue_potential"] = min(1.0, rev / 100000.0)
    out["competitor_activity"] = 1.0 if payload.get("competitor_activity") else 0.0
    return out


class OutcomeService:
    """All outcome paths funnel through sync_outcomes() — it handles idempotency,
    device tracking, weight updates (with real signal context), AND weight
    history snapshots.

    Identifier conventions:
      - rep_pk     : Rep.id (uuid) — used for Device foreign keys
      - rep_id_str : Rep.rep_id (e.g. 'REP_0338') — used for business filtering
    """
    def __init__(self, db: Session):
        self.db = db
        self.weight_svc = WeightService(db)

    def _load_signals_at_visit(self, entity_id: str) -> tuple[dict, dict]:
        """Returns (raw_payload, normalized_numeric_payload) for the given entity.
        Raw is stored on the Outcome row for the demo; normalized is fed to the updater.
        """
        sig = (
            self.db.query(Signal)
            .filter(Signal.entity_id == entity_id)
            .order_by(Signal.created_at.desc())
            .first()
        )
        raw = sig.payload if sig and sig.payload else {}
        return raw, _normalize_signal_payload(raw)

    # ---------- batch sync ----------

    def sync_outcomes(self, rep_pk: str, rep_id_str: str, payload: SyncRequest) -> SyncResponse:
        device_svc = DeviceService(self.db)
        device = device_svc.upsert_device(
            device_id=payload.device_id,
            rep_pk=rep_pk,
            name=payload.device_name,
            platform=payload.device_platform,
        )

        results: list[SyncResultItem] = []
        created = duplicate = failed = 0

        running_weights = self.weight_svc.get_current_weights()

        for item in payload.outcomes:
            try:
                raw_signals, numeric_signals = self._load_signals_at_visit(item.entity_id)

                outcome, was_duplicate = self._upsert_outcome(
                    rep_id_str=rep_id_str,
                    device_id=device.id,
                    item=item,
                    raw_signals_snapshot=raw_signals,
                )
                if was_duplicate:
                    duplicate += 1
                    results.append(SyncResultItem(
                        client_outcome_id=item.client_outcome_id,
                        server_outcome_id=outcome.id,
                        status="duplicate",
                    ))
                    continue

                # REAL weight update — uses the signals that were active at this entity
                running_weights = update_weights(
                    current_weights=running_weights,
                    signals_at_visit=numeric_signals,
                    outcome_rating=item.outcome_rating,
                )
                self.weight_svc.record_snapshot(
                    weights=running_weights,
                    trigger="outcome_logged",
                    rep_id=rep_id_str,
                    outcome_id=outcome.id,
                )

                created += 1
                results.append(SyncResultItem(
                    client_outcome_id=item.client_outcome_id,
                    server_outcome_id=outcome.id,
                    status="created",
                ))
            except Exception as e:
                failed += 1
                results.append(SyncResultItem(
                    client_outcome_id=item.client_outcome_id,
                    server_outcome_id=None,
                    status="failed",
                    error=str(e),
                ))

        if created > 0:
            device_svc.mark_sync(device, created)

        return SyncResponse(
            synced_at=datetime.utcnow(),
            device_id=device.id,
            total=len(payload.outcomes),
            created_count=created,
            duplicate_count=duplicate,
            failed_count=failed,
            results=results,
        )
    def _mark_competitor_activity(self, entity_id: str) -> None:
        """Set the grower's competitor_activity flag based on rep observation.

        Updates only the latest composite Signal so the next /visits/today call
        reflects the rep's input. Existing inferred values are overwritten by
        this observed truth; the `competitor_source` field tracks lineage.
        """
        latest = (
            self.db.query(Signal)
            .filter(Signal.entity_id == entity_id, Signal.signal_type == "composite")
            .order_by(Signal.created_at.desc())
            .first()
        )
        if not latest:
            return
        payload = dict(latest.payload or {})
        payload["competitor_activity"] = True
        payload["competitor_source"] = "rep_observed"
        latest.payload = payload
        flag_modified(latest, "payload")  # JSON column needs explicit dirty-flag
        self.db.commit()

    def _upsert_outcome(
        self,
        *,
        rep_id_str: str,
        device_id: Optional[str],
        item: SyncOutcomeItem,
        raw_signals_snapshot: dict,
    ) -> tuple[Outcome, bool]:
        if device_id and item.client_outcome_id:
            existing = (
                self.db.query(Outcome)
                .filter(
                    Outcome.device_id == device_id,
                    Outcome.client_outcome_id == item.client_outcome_id,
                )
                .first()
            )
            if existing:
                return existing, True

        entity = (
            self.db.query(FarmerRetailer)
            .filter(FarmerRetailer.id == item.entity_id)
            .first()
        )
        if not entity:
            raise ValueError(f"Entity {item.entity_id} not found")

        outcome = Outcome(
            client_outcome_id=item.client_outcome_id,
            device_id=device_id,
            entity_id=item.entity_id,
            rep_id=rep_id_str,
            visited_at=item.recorded_at or datetime.utcnow(),
            recorded_at=item.recorded_at or datetime.utcnow(),
            synced_at=datetime.utcnow(),
            outcome_rating=item.outcome_rating,
            outcome_type=item.outcome_type,
            actions_taken=item.actions_taken + item.actions_accepted,
            notes=item.notes,
            signals_at_visit=raw_signals_snapshot,  # captured for audit / demo
            competitor_seen=bool(getattr(item, "competitor_seen", False)),
        )
        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)        


        # If the rep observed a competitor product, update the grower's signal
        # payload so future Today's Priorities scoring reflects real observed
        # pressure (not the inferred proxy). Source marker lets the manager
        # dashboard distinguish observed vs inferred competitor activity.
        if outcome.competitor_seen:
            self._mark_competitor_activity(item.entity_id)


        return outcome, False

    # ---------- legacy single-outcome path ----------

    def record_outcome(self, rep_pk: str, rep_id_str: str, outcome: OutcomeRecord) -> dict:
        device_id = outcome.device_id or f"legacy:{rep_id_str}"
        client_outcome_id = outcome.client_outcome_id or str(uuid.uuid4())

        sync_req = SyncRequest(
            device_id=device_id,
            device_name="Legacy online client" if not outcome.device_id else None,
            device_platform="web" if not outcome.device_id else None,
            outcomes=[SyncOutcomeItem(
                client_outcome_id=client_outcome_id,
                entity_id=outcome.entity_id,
                outcome_rating=outcome.outcome_rating,
                outcome_type=outcome.outcome_type,
                actions_taken=outcome.actions_taken,
                actions_accepted=outcome.actions_accepted,
                notes=outcome.notes,
                competitor_seen=outcome.competitor_seen,
                recorded_at=outcome.recorded_at,
            )],
        )
        sync_resp = self.sync_outcomes(rep_pk, rep_id_str, sync_req)

        result = sync_resp.results[0]
        success = result.status == "created" and outcome.outcome_rating >= 4
        acceptance_rate = (
            round(len(outcome.actions_accepted) / len(outcome.actions_taken), 2)
            if outcome.actions_taken else 0.0
        )

        return {
            "status":                        result.status,
            "outcome_id":                    result.server_outcome_id,
            "entity_id":                     outcome.entity_id,
            "outcome_rating":                outcome.outcome_rating,
            "success":                       success,
            "recommendation_acceptance_rate": acceptance_rate,
            "client_outcome_id":             client_outcome_id,
            "device_id":                     device_id,
        }