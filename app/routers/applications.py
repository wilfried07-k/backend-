from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner, require_job_company_owner, require_application_candidate_owner, require_application_company_owner
from ..models import Application, JobOffer, CandidateProfile, User
from ..routers.matching import compute_match_score

router = APIRouter(prefix="/applications", tags=["applications"], dependencies=[Depends(get_current_user)])


class ApplicationCreate(BaseModel):
    candidate_id: int
    job_offer_id: int
    motivation_message: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    status: str   # EnvoyÃ©e / En examen / Entretien / RefusÃ©e / AcceptÃ©e


class ApplicationDetail(BaseModel):
    id: int
    job_offer_id: int
    job_title: str
    company_name: Optional[str]
    company_id: Optional[int] = None
    status: str
    match_score: Optional[float]
    created_at: str


class CompanyApplicationSummary(BaseModel):
    application_id: int
    candidate_id: int
    full_name: Optional[str]
    job_title: Optional[str]
    status: str
    match_score: Optional[float]
    job_offer_id: int


@router.post("", response_model=Application)
def apply(payload: ApplicationCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton d'envoi de CandidatureRapideScreen / CandidatureSpontaneeScreen."""
    candidate = require_candidate_owner(payload.candidate_id, session, current_user)
    job = session.get(JobOffer, payload.job_offer_id)
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidat ou offre introuvable")

    existing = session.exec(
        select(Application).where(
            Application.candidate_id == payload.candidate_id,
            Application.job_offer_id == payload.job_offer_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vous avez dÃ©jÃ  postulÃ© Ã  cette offre")

    candidate_text = " ".join(filter(None, [candidate.job_title, candidate.summary, candidate.skills]))
    job_text = " ".join(filter(None, [job.title, job.description, job.requirements]))
    score = compute_match_score(candidate_text, job_text)

    application = Application(
        candidate_id=payload.candidate_id,
        job_offer_id=payload.job_offer_id,
        motivation_message=payload.motivation_message,
        match_score=score,
    )
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


@router.get("/candidate/{candidate_id}", response_model=list[ApplicationDetail])
def list_candidate_applications(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  SuiviCandidaturesScreen (liste + statistiques)."""
    require_candidate_owner(candidate_id, session, current_user)
    applications = session.exec(select(Application).where(Application.candidate_id == candidate_id)).all()

    results = []
    for app_ in applications:
        job = session.get(JobOffer, app_.job_offer_id)
        from ..models import Company
        company = session.get(Company, job.company_id) if job else None
        results.append(ApplicationDetail(
            id=app_.id,
            job_offer_id=app_.job_offer_id,
            job_title=job.title if job else "Offre supprimÃ©e",
            company_name=company.name if company else None,
            company_id=job.company_id if job else None,
            status=app_.status,
            match_score=app_.match_score,
            created_at=app_.created_at.isoformat(),
        ))
    return results


@router.get("/job/{job_offer_id}")
def list_job_applications(job_offer_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au pipeline de GestionDesCandidatsScreen (candidats pour une offre)."""
    require_job_company_owner(job_offer_id, session, current_user)
    applications = session.exec(select(Application).where(Application.job_offer_id == job_offer_id)).all()

    results = []
    for app_ in applications:
        candidate = session.get(CandidateProfile, app_.candidate_id)
        user = session.get(User, candidate.user_id) if candidate else None
        results.append({
            "application_id": app_.id,
            "candidate_id": app_.candidate_id,
            "full_name": user.full_name if user else "Candidat",
            "job_title": candidate.job_title if candidate else None,
            "status": app_.status,
            "match_score": app_.match_score,
        })
    return results


@router.patch("/{application_id}/status", response_model=Application)
def update_application_status(
    application_id: int, payload: ApplicationStatusUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)
):
    """
    Correspond au bouton 'Avancer' dans le pipeline Kanban de
    GestionDesCandidatsScreen, et dÃ©clenche la notification au candidat
    (Ã  brancher : crÃ©ation d'une Notification ici).
    """
    application = require_application_company_owner(application_id, session, current_user)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")

    application.status = payload.status
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


@router.delete("/{application_id}")
def withdraw_application(application_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton 'Retirer ma candidature' de DetailsCandidatureScreen."""
    application = require_application_candidate_owner(application_id, session, current_user)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    session.delete(application)
    session.commit()
    return {"withdrawn": True}





