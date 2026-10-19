from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner, require_company_owner
from ..models import Conversation, Message, CandidateProfile, Company, User

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(get_current_user)])


class ConversationStart(BaseModel):
    candidate_id: int
    company_id: int


@router.post("/conversations", response_model=Conversation)
def start_conversation(payload: ConversationStart, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """CrÃ©Ã©e automatiquement au premier message, ou depuis 'Contacter' sur DetailsCandidatScreen."""
    if current_user.account_type.value == "candidate":
        require_candidate_owner(payload.candidate_id, session, current_user)
    elif current_user.account_type.value == "recruiter":
        require_company_owner(payload.company_id, session, current_user)
    elif current_user.account_type.value != "admin":
        raise HTTPException(status_code=403, detail="Accès interdit")
    existing = session.exec(
        select(Conversation).where(
            Conversation.candidate_id == payload.candidate_id,
            Conversation.company_id == payload.company_id,
        )
    ).first()
    if existing:
        return existing

    conv = Conversation(candidate_id=payload.candidate_id, company_id=payload.company_id)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@router.get("/conversations/candidate/{candidate_id}")
def list_candidate_conversations(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  MessagesScreen cÃ´tÃ© candidat : liste des conversations avec dernier message."""
    require_candidate_owner(candidate_id, session, current_user)
    conversations = session.exec(select(Conversation).where(Conversation.candidate_id == candidate_id)).all()
    return _build_conversation_list(conversations, session)


@router.get("/conversations/company/{company_id}")
def list_company_conversations(company_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  la messagerie cÃ´tÃ© recruteur."""
    require_company_owner(company_id, session, current_user)
    conversations = session.exec(select(Conversation).where(Conversation.company_id == company_id)).all()
    return _build_conversation_list(conversations, session)


def _build_conversation_list(conversations, session: Session):
    results = []
    for conv in conversations:
        company = session.get(Company, conv.company_id)
        last_message = session.exec(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc())
        ).first()
        unread_count = len(session.exec(
            select(Message).where(Message.conversation_id == conv.id, Message.read == False)
        ).all())
        results.append({
            "conversation_id": conv.id,
            "company_name": company.name if company else None,
            "last_message": last_message.text if last_message else None,
            "last_message_at": last_message.created_at.isoformat() if last_message else None,
            "unread_count": unread_count,
        })
    return results


class MessageCreate(BaseModel):
    sender_user_id: int
    text: str


@router.post("/{conversation_id}", response_model=Message)
def send_message(conversation_id: int, payload: MessageCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton d'envoi de DiscussionScreen."""
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    if current_user.account_type.value == "candidate":
        require_candidate_owner(conv.candidate_id, session, current_user)
    elif current_user.account_type.value == "recruiter":
        require_company_owner(conv.company_id, session, current_user)
    elif current_user.account_type.value != "admin":
        raise HTTPException(status_code=403, detail="Accès interdit")
    if payload.sender_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Expéditeur invalide")
    message = Message(conversation_id=conversation_id, sender_user_id=current_user.id, text=payload.text)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@router.get("/{conversation_id}", response_model=list[Message])
def get_messages(conversation_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au fil de discussion de DiscussionScreen."""
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    if current_user.account_type.value == "candidate":
        require_candidate_owner(conv.candidate_id, session, current_user)
    elif current_user.account_type.value == "recruiter":
        require_company_owner(conv.company_id, session, current_user)
    elif current_user.account_type.value != "admin":
        raise HTTPException(status_code=403, detail="Accès interdit")
    return session.exec(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    ).all()







