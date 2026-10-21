from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel
from sqlalchemy import func, or_
from ..database import get_session
from ..auth import get_current_user, require_company_owner, require_job_company_owner
from ..models import JobOffer, BillingSubscription, Company

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


class JobOfferResponse(BaseModel):
    id: int
    company_id: int
    title: str
    description: str
    requirements: str
    city: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    status: str
    created_at: datetime
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    company_kyc_verified: bool = False


class JobOfferCreate(BaseModel):
    company_id: int
    title: str
    description: str
    requirements: str
    city: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


class JobOfferUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    city: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    status: Optional[str] = None


@router.post("", response_model=JobOffer)
def create_job(payload: JobOfferCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond ÃƒÂ  PublierOffreScreen (ÃƒÂ©tape finale du formulaire 3 ÃƒÂ©tapes)."""
    company = require_company_owner(payload.company_id, session, current_user)
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")

    subscription = session.exec(select(BillingSubscription).where(BillingSubscription.company_id == company.id)).first()
    premium_active = bool(subscription and subscription.status == "Actif" and subscription.expires_at > datetime.utcnow())
    if not premium_active:
        open_jobs = session.exec(select(func.count(JobOffer.id)).where(JobOffer.company_id == company.id, JobOffer.status == "Ouvert")).one()
        if open_jobs >= 2:
            raise HTTPException(status_code=403, detail="Le plan gratuit est limité à 2 offres actives. Passez à Premium pour en publier davantage.")
    job = JobOffer(**payload.dict())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("", response_model=list[JobOfferResponse])
def list_jobs(
    keyword: Optional[str] = None,
    city: Optional[str] = None,
    contract_type: Optional[list[str]] = Query(default=None),
    sector: Optional[str] = None,
    minimum_salary: Optional[int] = None,
    status: str = "Ouvert",
    session: Session = Depends(get_session),
):
    """
    Correspond ÃƒÂ  la recherche de TableauDeBordScreen / RechercheAvanceeScreen.
    Filtre simple par mot-clÃƒÂ© (titre), ville, type de contrat et statut.
    """
    query = select(JobOffer).where(JobOffer.status == status)
    if city:
        query = query.where(func.lower(JobOffer.city).contains(city.lower()))
    if contract_type:
        query = query.where(or_(*[
            func.lower(JobOffer.contract_type) == value.lower()
            for value in contract_type
        ]))
    if sector:
        query = query.join(Company, Company.id == JobOffer.company_id).where(
            func.lower(Company.sector).contains(sector.lower())
        )
    if minimum_salary is not None:
        query = query.where(or_(
            JobOffer.salary_min >= minimum_salary,
            JobOffer.salary_max >= minimum_salary,
        ))

    jobs = session.exec(query).all()
    if keyword:
        keyword_lower = keyword.lower()
        jobs = [j for j in jobs if keyword_lower in j.title.lower() or keyword_lower in j.description.lower() or keyword_lower in j.requirements.lower()]

    results = []
    for job in jobs:
        company = session.get(Company, job.company_id)
        results.append(JobOfferResponse(
            id=job.id,
            company_id=job.company_id,
            title=job.title,
            description=job.description,
            requirements=job.requirements,
            city=job.city,
            contract_type=job.contract_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            status=job.status,
            created_at=job.created_at,
            company_name=company.name if company else None,
            company_description=company.description if company else None,
            company_kyc_verified=company.kyc_verified if company else False,
        ))
    return results


@router.get("/{job_id}", response_model=JobOfferResponse)
def get_job(job_id: int, session: Session = Depends(get_session)):
    """Correspond ÃƒÂ  DetailOffreScreen."""
    job = session.get(JobOffer, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    company = session.get(Company, job.company_id)
    return JobOfferResponse(
        id=job.id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        city=job.city,
        contract_type=job.contract_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        status=job.status,
        created_at=job.created_at,
        company_name=company.name if company else None,
            company_description=company.description if company else None,
            company_kyc_verified=company.kyc_verified if company else False,
    )


@router.patch("/{job_id}", response_model=JobOffer)
def update_job(job_id: int, payload: JobOfferUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond ÃƒÂ  la modification de statut dans GestionDesOffresScreen."""
    require_job_company_owner(job_id, session, current_user)
    job = session.get(JobOffer, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(job, field, value)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/company/{company_id}", response_model=list[JobOffer])
def list_company_jobs(company_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond ÃƒÂ  GestionDesOffresScreen cÃƒÂ´tÃƒÂ© recruteur (liste 'Mes offres')."""
    require_company_owner(company_id, session, current_user)
    return session.exec(select(JobOffer).where(JobOffer.company_id == company_id)).all()


@router.delete("/{job_id}")
def delete_job(job_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    require_job_company_owner(job_id, session, current_user)
    job = session.get(JobOffer, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    session.delete(job)
    session.commit()
    return {"deleted": True}




