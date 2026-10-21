from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from ..database import get_session
from ..auth import get_current_user, require_owner
from ..models import Notification, NotificationPreference, User

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])



class NotificationPreferenceUpdate(BaseModel):
    push_enabled: bool = True
    email_enabled: bool = True
    jobs: bool = True
    messages: bool = True
    applications: bool = True
    interviews: bool = True
    news: bool = False
    marketing: bool = False


@router.get("/preferences/me", response_model=NotificationPreference)
def get_my_notification_preferences(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    preference = session.exec(select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)).first()
    if preference:
        return preference
    preference = NotificationPreference(user_id=current_user.id)
    session.add(preference)
    session.commit()
    session.refresh(preference)
    return preference


@router.put("/preferences/me", response_model=NotificationPreference)
def update_my_notification_preferences(payload: NotificationPreferenceUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    preference = session.exec(select(NotificationPreference).where(NotificationPreference.user_id == current_user.id)).first()
    if not preference:
        preference = NotificationPreference(user_id=current_user.id)
    for key, value in payload.model_dump().items():
        setattr(preference, key, value)
    preference.updated_at = datetime.utcnow()
    session.add(preference)
    session.commit()
    session.refresh(preference)
    return preference

@router.get("/{user_id}", response_model=list[Notification])
def list_notifications(user_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  NotificationsScreen."""
    require_owner(user_id, current_user)
    return session.exec(
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    ).all()


@router.patch("/{notification_id}/read", response_model=Notification)
def mark_as_read(notification_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    notification = session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    require_owner(notification.user_id, current_user)
    notification.read = True
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


@router.patch("/user/{user_id}/read-all")
def mark_all_as_read(user_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton 'Tout marquer comme lu' de NotificationsScreen."""
    require_owner(user_id, current_user)
    notifications = session.exec(select(Notification).where(Notification.user_id == user_id)).all()
    for n in notifications:
        n.read = True
        session.add(n)
    session.commit()
    return {"updated": len(notifications)}




