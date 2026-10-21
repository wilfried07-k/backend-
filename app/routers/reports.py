from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..auth import get_current_user
from ..database import get_session
from ..models import Company, JobOffer, ModerationReport, User

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


class ReportCreate(BaseModel):
    job_offer_id: int | None = None
    reported_user_id: int | None = None
    reason: str = Field(min_length=5, max_length=2000)


@router.post("", response_model=ModerationReport)
def create_report(payload: ReportCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if (payload.job_offer_id is None) == (payload.reported_user_id is None):
        raise HTTPException(status_code=422, detail="Signale une seule offre ou un seul compte")
    if payload.job_offer_id is not None:
        job = session.get(JobOffer, payload.job_offer_id)
        if not job:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        company = session.get(Company, job.company_id)
        if company and company.owner_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Tu ne peux pas signaler ta propre offre")
    if payload.reported_user_id is not None:
        reported_user = session.get(User, payload.reported_user_id)
        if not reported_user:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        if reported_user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Tu ne peux pas signaler ton propre compte")
    report = ModerationReport(
        job_offer_id=payload.job_offer_id,
        reported_user_id=payload.reported_user_id,
        reported_by_user_id=current_user.id,
        reason=payload.reason.strip(),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report