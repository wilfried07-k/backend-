from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import CandidateProfile, CareerExperience, User

router = APIRouter(prefix="/career", tags=["career"], dependencies=[Depends(get_current_user)])


class ExperienceCreate(BaseModel):
    employer: str = Field(min_length=1, max_length=255)
    job_title: str = Field(min_length=1, max_length=255)
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=4000)


def get_candidate(current_user: User, session: Session) -> CandidateProfile:
    if current_user.account_type.value != "candidate":
        raise HTTPException(status_code=403, detail="Un compte candidat est requis")
    candidate = session.exec(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="Complétez votre profil candidat avant d’ajouter une expérience")
    return candidate


@router.get("/me", response_model=list[CareerExperience])
def list_experiences(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    return session.exec(
        select(CareerExperience)
        .where(CareerExperience.candidate_id == candidate.id)
        .order_by(CareerExperience.start_date.desc())
    ).all()


@router.post("/me", response_model=CareerExperience)
def create_experience(payload: ExperienceCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="La date de fin doit suivre la date de début")
    experience = CareerExperience(candidate_id=candidate.id, **payload.dict())
    session.add(experience)
    session.commit()
    session.refresh(experience)
    return experience


@router.delete("/me/{experience_id}")
def delete_experience(experience_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    experience = session.get(CareerExperience, experience_id)
    if not experience or experience.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Expérience introuvable")
    session.delete(experience)
    session.commit()
    return {"deleted": True}