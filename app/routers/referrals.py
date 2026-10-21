import secrets
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import Referral, ReferralCode, User

router = APIRouter(prefix="/referrals", tags=["referrals"], dependencies=[Depends(get_current_user)])


class ReferralSignup(BaseModel):
    account_type: str
    created_at: datetime


class ReferralSummary(BaseModel):
    code: str
    total_signups: int
    signups: list[ReferralSignup]


@router.get("/me", response_model=ReferralSummary)
def get_my_referrals(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    code_record = session.exec(select(ReferralCode).where(ReferralCode.user_id == current_user.id)).first()
    if not code_record:
        code_record = ReferralCode(user_id=current_user.id, code="EC" + secrets.token_hex(5).upper())
        session.add(code_record)
        session.commit()
        session.refresh(code_record)

    referrals = session.exec(
        select(Referral).where(Referral.referrer_user_id == current_user.id).order_by(Referral.created_at.desc())
    ).all()
    signups = []
    for referral in referrals:
        user = session.get(User, referral.referred_user_id)
        if user:
            signups.append(ReferralSignup(account_type=user.account_type.value, created_at=referral.created_at))
    return ReferralSummary(code=code_record.code, total_signups=len(signups), signups=signups)