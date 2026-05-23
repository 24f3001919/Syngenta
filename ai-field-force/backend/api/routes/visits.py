# backend/api/routes/visits.py
from fastapi import APIRouter, Depends, HTTPException, Header
from datetime import datetime
from typing import Optional
from services.visit_service import VisitService
from core.auth.dependencies import get_current_rep
from models.db.rep import Rep

router = APIRouter()
service = VisitService()


def _require_linked_rep(current: Rep) -> str:
    if not current.rep_id:
        raise HTTPException(
            status_code=403,
            detail="Account not linked to a Syngenta rep ID. Contact your administrator."
        )
    return current.rep_id


def _parse_lang(accept_language: Optional[str]) -> str:
    """Map an Accept-Language header value to one of our 4 supported language codes.
    Accepts headers like 'hi', 'hi-IN', 'hi-IN,en;q=0.9', etc."""
    if not accept_language:
        return "en"
    primary = accept_language.split(",")[0].strip().lower()
    base = primary.split("-")[0]
    return base if base in ("en", "hi", "gu", "bn") else "en"


@router.get("/today")
def get_today_visits(current: Rep = Depends(get_current_rep)):
    rep_id = _require_linked_rep(current)
    return service.generate_daily_priority_list(rep_id)


@router.get("/{entity_id}/brief")
def get_visit_brief(
    entity_id: str,
    current: Rep = Depends(get_current_rep),
    accept_language: Optional[str] = Header(None, alias="Accept-Language"),
):
    rep_id = _require_linked_rep(current)
    lang = _parse_lang(accept_language)
    print(f"🌍 BRIEF REQUEST → accept_language='{accept_language}' parsed_lang='{lang}'")
    return service.get_visit_brief(entity_id, rep_id, lang=lang)


@router.get("/{entity_id}/explain")
def get_visit_explanation(
    entity_id: str,
    rank: int = 1,
    current: Rep = Depends(get_current_rep),
):
    _require_linked_rep(current)
    return service.get_visit_explanation(entity_id, rank)


@router.get("/today/export")
def export_today_visits(current: Rep = Depends(get_current_rep)):
    rep_id = _require_linked_rep(current)
    visits = service.generate_daily_priority_list(rep_id)
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "rep_id":      rep_id,
        "total":       len(visits),
        "visits":      visits,
    }