from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner
from ..models import JobAlert, JobOffer

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


class JobAlertCreate(BaseModel):
    candidate_id: int
    title: str
    city: Optional[str] = None
    frequency: str = "instant"


@router.post("", response_model=JobAlert)
def create_alert(payload: JobAlertCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton 'CrÃ©er l'alerte' de CreerAlerteEmploiScreen."""
    require_candidate_owner(payload.candidate_id, session, current_user)
    alert = JobAlert(**payload.dict())
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


@router.get("/{candidate_id}", response_model=list[JobAlert])
def list_alerts(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  GestionAlertesEmploiScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    return session.exec(select(JobAlert).where(JobAlert.candidate_id == candidate_id)).all()


class JobAlertUpdate(BaseModel):
    title: Optional[str] = None
    city: Optional[str] = None
    frequency: Optional[str] = None
    active: Optional[bool] = None


@router.patch("/{alert_id}", response_model=JobAlert)
def update_alert(alert_id: int, payload: JobAlertUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  la modification ou au toggle actif/inactif dans GestionAlertesEmploiScreen."""
    alert = session.get(JobAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    require_candidate_owner(alert.candidate_id, session, current_user)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(alert, field, value)
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    alert = session.get(JobAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    require_candidate_owner(alert.candidate_id, session, current_user)
    session.delete(alert)
    session.commit()
    return {"deleted": True}


@router.get("/{alert_id}/matches")
def get_alert_matches(alert_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  la liste 'DerniÃ¨res offres correspondantes' de DetailsAlerteEmploiScreen."""
    alert = session.get(JobAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable")

    require_candidate_owner(alert.candidate_id, session, current_user)
    query = select(JobOffer).where(JobOffer.status == "Ouvert")
    if alert.city:
        query = query.where(JobOffer.city == alert.city)
    jobs = session.exec(query).all()

    keyword = alert.title.lower()
    return [j for j in jobs if keyword in j.title.lower()]




