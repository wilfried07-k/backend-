from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import BillingPayment, BillingSubscription, Company, User

router = APIRouter(prefix="/billing", tags=["billing"], dependencies=[Depends(get_current_user)])


class PaymentRequest(BaseModel):
    plan: Literal["Premium"] = "Premium"
    payment_method: Literal["MTN Mobile Money", "Orange Money"]


class PaymentReference(BaseModel):
    external_reference: str = Field(min_length=4, max_length=120)


def get_recruiter_company(current_user: User, session: Session) -> Company:
    if current_user.account_type.value != "recruiter":
        raise HTTPException(status_code=403, detail="Un compte recruteur est requis")
    company = session.exec(select(Company).where(Company.owner_user_id == current_user.id)).first()
    if not company:
        raise HTTPException(status_code=400, detail="Créez le profil de votre entreprise avant de demander un paiement")
    return company


@router.post("/payments", response_model=BillingPayment)
def create_payment(payload: PaymentRequest, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    company = get_recruiter_company(current_user, session)
    payment = BillingPayment(user_id=current_user.id, company_id=company.id, plan=payload.plan, amount_xaf=45000, payment_method=payload.payment_method)
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


@router.get("/payments/me", response_model=list[BillingPayment])
def list_my_payments(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    get_recruiter_company(current_user, session)
    return session.exec(select(BillingPayment).where(BillingPayment.user_id == current_user.id).order_by(BillingPayment.created_at.desc())).all()


@router.patch("/payments/{payment_id}/reference", response_model=BillingPayment)
def submit_payment_reference(payment_id: int, payload: PaymentReference, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    payment = session.get(BillingPayment, payment_id)
    if not payment or payment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Demande de paiement introuvable")
    if payment.status != "En attente de paiement":
        raise HTTPException(status_code=409, detail="Cette demande de paiement ne peut plus être modifiée")
    payment.external_reference = payload.external_reference.strip()
    payment.status = "À vérifier"
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment
@router.get("/subscription/me", response_model=BillingSubscription | None)
def get_my_subscription(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    company = get_recruiter_company(current_user, session)
    subscription = session.exec(select(BillingSubscription).where(BillingSubscription.company_id == company.id)).first()
    if subscription and subscription.expires_at <= datetime.utcnow():
        subscription.status = "Expiré"
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
    return subscription