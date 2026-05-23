from core.deterministic.override_rules  import apply_overrides
from core.deterministic.anomaly_detector import run_anomaly_checks
from core.deterministic.nba_engine      import get_next_best_actions
from core.deterministic.explainer       import extract_top_reasons
from core.ml.feature_builder            import build_feature_vector
from core.ml.priority_scorer            import compute_vps
from core.ml.confidence                 import compute_confidence
from core.ml.weights                    import SIGNAL_WEIGHTS
from models.db.farmers                  import FarmerRetailer
from models.db.signal                   import Signal
from db.session                         import SessionLocal
from core.llm.briefing_chain import run_briefing_chain
from core.llm.explainer_chain import run_explainer_chain

class VisitService:

    def __init__(self):
        self.weights = SIGNAL_WEIGHTS

    def generate_daily_priority_list(self, rep_id: str) -> list[dict]:
        db = SessionLocal()

        # 1. Fetch all entities for this rep
        entities = db.query(FarmerRetailer).filter(
            FarmerRetailer.rep_id == rep_id
        ).all()

        # 2. Fetch all signals for these entities
        entity_ids = [e.id for e in entities]
        signal_rows = db.query(Signal).filter(
            Signal.entity_id.in_(entity_ids)
        ).all()
        db.close()

        # 3. Build signals dict keyed by entity_id
        signals_map = {s.entity_id: s.payload for s in signal_rows}

        scored = []
        for entity in entities:
            entity_dict = {
                "id":               entity.id,
                "name":             entity.name,
                "type":             entity.type,
                "lat":              entity.lat,
                "lng":              entity.lng,
                "region":           entity.region,
                "last_visited_at":  entity.last_visited_at,
            }

            payload = signals_map.get(entity.id, {})

            # merge entity + payload for override/anomaly checks
            context = {**entity_dict, **payload}

            # 4. Build feature vector
            features = build_feature_vector(entity_dict, signals_map)

            # 5. Compute VPS
            vps = compute_vps(features, self.weights)

            # 6. Apply hard overrides
            vps, overrides = apply_overrides(context, vps)

            # 7. Anomaly detection
            anomalies = run_anomaly_checks(context)

            # 8. Extract reasons
            reasons = extract_top_reasons(features, self.weights, overrides)

            # 9. Confidence
            confidence = compute_confidence(features, {})

            scored.append({
                "entity_id":              entity.id,
                "name":                   entity.name,
                "region":                 entity.region,
                "vps":                    vps,
                "reasons":                reasons,
                "confidence_label":       confidence["label"],
                "anomalies":              anomalies,
            })

        # 10. Sort by VPS
        ranked = sorted(scored, key=lambda x: x["vps"], reverse=True)

        # 11. Add rank and sequence position
        for i, item in enumerate(ranked):
            item["rank"] = i + 1
            item["visit_sequence_position"] = i + 1

        return ranked
    def get_visit_brief(self, entity_id: str, rep_id: str, lang: str = "en") -> dict:   
        db = SessionLocal()

        entity = db.query(FarmerRetailer).filter(
            FarmerRetailer.id == entity_id
        ).first()

        signal_row = db.query(Signal).filter(
            Signal.entity_id == entity_id
        ).first()

        db.close()

        if not entity:
            return {"error": "Entity not found"}

        payload = signal_row.payload if signal_row else {}

        context = {
            "id":     entity.id,
            "name":   entity.name,
            "type":   entity.type,
            "region": entity.region,
            **payload
        }

        nba_actions = get_next_best_actions(context)
        briefing    = run_briefing_chain(context, nba_actions, lang=lang)

        return {
            "entity_id":     entity_id,
            "name":          entity.name,
            "briefing":      briefing,
            "nba_actions":   nba_actions,
        }
    def get_visit_explanation(self, entity_id: str, rank: int) -> dict:
        db = SessionLocal()

        entity = db.query(FarmerRetailer).filter(
            FarmerRetailer.id == entity_id
        ).first()

        signal_row = db.query(Signal).filter(
            Signal.entity_id == entity_id
        ).first()

        db.close()

        if not entity:
            return {"error": "Entity not found"}

        payload = signal_row.payload if signal_row else {}

        context = {
            "id":       entity.id,
            "name":     entity.name,
            "type":     entity.type,
            "region":   entity.region,
            "rank":     rank,
            "overrides": [],
            **payload
        }

        features  = build_feature_vector({"id": entity.id, **payload}, {entity.id: payload})
        reasons   = extract_top_reasons(features, self.weights, [])
        explanation = run_explainer_chain(context, reasons)

        return {
            "entity_id":   entity_id,
            "name":        entity.name,
            "rank":        rank,
            "explanation": explanation,
            "reasons":     reasons
        }