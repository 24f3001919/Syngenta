# backend/api/routes/signals.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
 
from db.session                  import get_db
from services.signal_service     import SignalService
from core.auth.dependencies      import get_current_rep
from core.auth.roles             import require_role
from models.db.rep               import Rep
from models.db.farmers           import FarmerRetailer
from core.integrations.ndvi      import fetch_ndvi_detail
from core.integrations.icar_pest import fetch_pest_detail
 
router = APIRouter()
 
 
@router.get("/anomalies",
            summary="All growers with one or more detected anomalies")
def get_anomalies(
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    if not current.rep_id:
        raise HTTPException(
            status_code=403,
            detail="Account not linked to a Syngenta rep ID. Contact your administrator.",
        )
    service = SignalService(db)
    return service.get_anomalies(current.rep_id)
 
 
@router.post(
    "/refresh",
    summary="Trigger a live refresh of NDVI + ICAR pest signals (manager/admin only)",
)
def refresh_signals(
    background_tasks: BackgroundTasks,
    current: Rep = Depends(require_role("manager", "admin")),
):
    """
    Queues a background job that:
      1. Fetches fresh Sentinel-2 NDVI scores for every entity via Element84 STAC.
      2. Fetches district-level pest severity from ICAR/NCIPM and IMD AAS.
      3. Updates Signal.payload rows in place.
 
    Returns immediately; the job runs asynchronously.
    Check startup logs or /weights/history for evidence of updated data.
    """
    from tasks.signal_refresh import run_once
    background_tasks.add_task(run_once)
    return {
        "status":  "queued",
        "message": (
            "Signal refresh started in the background. "
            "Sources: Sentinel-2 L2A (Element84) + ICAR-NCIPM + IMD AAS."
        ),
    }
 
 
@router.get(
    "/ndvi/{entity_id}",
    summary="Live NDVI detail for one entity — scene date, raw value, stress score",
)
def ndvi_detail(
    entity_id: str,
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    """
    Fetches a fresh Sentinel-2 NDVI reading for the entity's coordinates and
    returns the full breakdown (raw NDVI, stress score, scene date, cloud %).
    Useful for the 'why is this grower flagged?' explainer screen.
 
    Note: makes a live STAC API call — expect ~1–3 s latency.
    """
    entity = db.query(FarmerRetailer).filter(FarmerRetailer.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
 
    if entity.lat is None or entity.lng is None:
        raise HTTPException(status_code=422, detail="Entity has no coordinates")
 
    detail = fetch_ndvi_detail(entity.lat, entity.lng)
    if not detail:
        raise HTTPException(
            status_code=503,
            detail="NDVI data currently unavailable (Sentinel-2 STAC or rasterio issue)",
        )
    return {"entity_id": entity_id, "name": entity.name, **detail}
 
 
@router.get(
    "/pest/{entity_id}",
    summary="Live ICAR pest advisory detail for one entity's district",
)
def pest_detail(
    entity_id: str,
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    """
    Returns the current district-level pest advisory (severity + source + timestamp)
    for the entity's region, fetched from ICAR-NCIPM / IMD AAS.
    """
    entity = db.query(FarmerRetailer).filter(FarmerRetailer.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
 
    detail = fetch_pest_detail(entity.region or "")
    if not detail:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not parse region '{entity.region}' to a known district. "
                "Region must be of the form 'District, State'."
            ),
        )
    return {"entity_id": entity_id, "name": entity.name, "region": entity.region, **detail}