from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import CandidateProfile, Company, CompanyReview, User

router = APIRouter(prefix="/reviews", tags=["company reviews"], dependencies=[Depends(get_current_user)])


class ReviewCreate(BaseModel):
    company_id: int
    rating: int = PydanticField(ge=1, le=5)
    role: Optional[str] = PydanticField(default=None, max_length=255)
    body: str = PydanticField(min_length=20, max_length=4000)


class ReviewResponse(BaseModel):
    id: int
    rating: int
    role: Optional[str]
    body: str
    created_at: datetime


@router.get("/company/{company_id}", response_model=list[ReviewResponse])
def list_company_reviews(company_id: int, session: Session = Depends(get_session)):
    if not session.get(Company, company_id):
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    return session.exec(
        select(CompanyReview)
        .where(CompanyReview.company_id == company_id)
        .order_by(CompanyReview.created_at.desc())
    ).all()


@router.post("", response_model=ReviewResponse)
def create_review(payload: ReviewCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.account_type.value != "candidate":
        raise HTTPException(status_code=403, detail="Un compte candidat est requis")
    if not session.get(Company, payload.company_id):
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    candidate = session.exec(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="Complétez votre profil candidat avant de publier un avis")
    review = CompanyReview(
        company_id=payload.company_id,
        author_user_id=current_user.id,
        rating=payload.rating,
        role=(payload.role.strip() or None) if payload.role else None,
        body=payload.body.strip(),
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review