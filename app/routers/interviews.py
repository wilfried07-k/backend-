from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner, require_company_owner, require_job_company_owner
from ..models import Interview, Application, JobOffer, Company, CandidateProfile, User

router = APIRouter(prefix="/interviews", tags=["interviews"], dependencies=[Depends(get_current_user)])


class InterviewCreate(BaseModel):
    application_id: int
    scheduled_at: datetime
    mode: str = "video"
    location_or_link: Optional[str] = None


@router.post("", response_model=Interview)
def schedule_interview(payload: InterviewCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """
    Correspond au bouton 'Confirmer l'entretien' de PlanifierEntretienScreen.
    Met aussi la candidature au statut 'Entretien'.
    """
    application = session.get(Application, payload.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")

    require_job_company_owner(application.job_offer_id, session, current_user)
    interview = Interview(**payload.dict())
    session.add(interview)

    application.status = "Entretien"
    session.add(application)

    session.commit()
    session.refresh(interview)
    return interview


@router.get("/candidate/{candidate_id}")
def list_candidate_interviews(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  CalendrierCandidatScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    applications = session.exec(select(Application).where(Application.candidate_id == candidate_id)).all()
    application_ids = [a.id for a in applications]
    if not application_ids:
        return []

    interviews = session.exec(select(Interview).where(Interview.application_id.in_(application_ids))).all()

    results = []
    for interview in interviews:
        application = session.get(Application, interview.application_id)
        job = session.get(JobOffer, application.job_offer_id) if application else None
        company = session.get(Company, job.company_id) if job else None
        results.append({
            "interview_id": interview.id,
            "job_title": job.title if job else None,
            "company_name": company.name if company else None,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "mode": interview.mode,
            "location_or_link": interview.location_or_link,
            "status": interview.status,
        })
    return results


@router.get("/company/{company_id}")
def list_company_interviews(company_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  GestionEntretiensVideoScreen cÃ´tÃ© recruteur."""
    require_company_owner(company_id, session, current_user)
    jobs = session.exec(select(JobOffer).where(JobOffer.company_id == company_id)).all()
    job_ids = [j.id for j in jobs]
    if not job_ids:
        return []

    applications = session.exec(select(Application).where(Application.job_offer_id.in_(job_ids))).all()
    application_ids = [a.id for a in applications]
    if not application_ids:
        return []

    interviews = session.exec(select(Interview).where(Interview.application_id.in_(application_ids))).all()

    results = []
    for interview in interviews:
        application = session.get(Application, interview.application_id)
        candidate = session.get(CandidateProfile, application.candidate_id) if application else None
        user = session.get(User, candidate.user_id) if candidate else None
        results.append({
            "interview_id": interview.id,
            "candidate_name": user.full_name if user else None,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "mode": interview.mode,
            "status": interview.status,
        })
    return results


class InterviewStatusUpdate(BaseModel):
    status: str   # PlanifiÃ© / TerminÃ© / AnnulÃ©


@router.patch("/{interview_id}", response_model=Interview)
def update_interview_status(interview_id: int, payload: InterviewStatusUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    interview = session.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien introuvable")
    application = session.get(Application, interview.application_id)
    if application:
        if current_user.account_type.value == "candidate":
            require_candidate_owner(application.candidate_id, session, current_user)
        else:
            require_job_company_owner(application.job_offer_id, session, current_user)
    interview.status = payload.status
    session.add(interview)
    session.commit()
    session.refresh(interview)
    return interview



