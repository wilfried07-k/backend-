from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner
from ..models import SavedJob, JobOffer, Company

router = APIRouter(prefix="/favorites", tags=["favorites"], dependencies=[Depends(get_current_user)])


@router.post("/{candidate_id}/{job_offer_id}", response_model=SavedJob)
def save_job(candidate_id: int, job_offer_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  l'icÃ´ne bookmark de DetailOffreScreen / TableauDeBordScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    existing = session.exec(
        select(SavedJob).where(SavedJob.candidate_id == candidate_id, SavedJob.job_offer_id == job_offer_id)
    ).first()
    if existing:
        return existing

    saved = SavedJob(candidate_id=candidate_id, job_offer_id=job_offer_id)
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


@router.delete("/{candidate_id}/{job_offer_id}")
def unsave_job(candidate_id: int, job_offer_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton retirer des favoris de FavorisScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    saved = session.exec(
        select(SavedJob).where(SavedJob.candidate_id == candidate_id, SavedJob.job_offer_id == job_offer_id)
    ).first()
    if saved:
        session.delete(saved)
        session.commit()
    return {"removed": True}


@router.get("/{candidate_id}")
def list_favorites(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  la liste de FavorisScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    saved_jobs = session.exec(select(SavedJob).where(SavedJob.candidate_id == candidate_id)).all()

    results = []
    for s in saved_jobs:
        job = session.get(JobOffer, s.job_offer_id)
        if not job:
            continue
        company = session.get(Company, job.company_id)
        results.append({
            "job_offer_id": job.id,
            "title": job.title,
            "company_name": company.name if company else None,
            "city": job.city,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "saved_at": s.created_at.isoformat(),
        })
    return results



