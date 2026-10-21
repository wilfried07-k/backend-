from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from ..auth import get_current_user
from ..database import get_session
from ..models import ProductFeedback, SupportTicket, User

router = APIRouter(tags=["support"], dependencies=[Depends(get_current_user)])


class SupportTicketCreate(BaseModel):
    category: str
    subject: str
    body: str


class ProductFeedbackCreate(BaseModel):
    applications_rating: int
    usability_rating: int
    value_rating: int
    comment: str | None = None


@router.post("/support/tickets", response_model=SupportTicket)
def create_support_ticket(payload: SupportTicketCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    category = payload.category.strip()
    subject = payload.subject.strip()
    body = payload.body.strip()
    if not category or not subject or not body:
        raise HTTPException(status_code=422, detail="La catégorie, le sujet et le message sont obligatoires")
    if len(body) > 4000:
        raise HTTPException(status_code=422, detail="Le message est trop long")
    ticket = SupportTicket(user_id=current_user.id, category=category, subject=subject, body=body)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@router.get("/support/tickets/me", response_model=list[SupportTicket])
def list_my_support_tickets(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return session.exec(select(SupportTicket).where(SupportTicket.user_id == current_user.id).order_by(SupportTicket.created_at.desc())).all()


@router.post("/feedback", response_model=ProductFeedback)
def submit_product_feedback(payload: ProductFeedbackCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    ratings = [payload.applications_rating, payload.usability_rating, payload.value_rating]
    if any(rating < 1 or rating > 5 for rating in ratings):
        raise HTTPException(status_code=422, detail="Chaque note doit être comprise entre 1 et 5")
    feedback = ProductFeedback(
        user_id=current_user.id,
        applications_rating=payload.applications_rating,
        usability_rating=payload.usability_rating,
        value_rating=payload.value_rating,
        comment=payload.comment.strip() if payload.comment else None,
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback


@router.get("/admin/support/tickets", response_model=list[SupportTicket])
def list_support_tickets(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.account_type.value != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé à l'administration")
    return session.exec(select(SupportTicket).order_by(SupportTicket.created_at.desc())).all()
