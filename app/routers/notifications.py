from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..database import get_session
from ..auth import get_current_user, require_owner
from ..models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


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




