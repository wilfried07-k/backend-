from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, Field
from ..database import get_session
from ..models import User, AccountType, ReferralCode, Referral, CandidateProfile
from ..auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    account_type: AccountType
    referral_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    account_type: AccountType


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_type: AccountType
    user_id: int


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


@router.post("/password/change")
def change_password(payload: PasswordChangeRequest, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Le mot de passe actuel est incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    session.add(current_user)
    session.commit()
    return {"updated": True}

@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    """Correspond au bouton 'CrÃ©er mon compte' de InscriptionScreen."""
    if payload.account_type == AccountType.admin:
        raise HTTPException(status_code=403, detail="La création de comptes administrateur est désactivée")

    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe dÃ©jÃ  avec cet email")

    referral_code = None
    if payload.referral_code and payload.referral_code.strip():
        code = payload.referral_code.strip().upper()
        referral_code = session.exec(select(ReferralCode).where(ReferralCode.code == code)).first()
        if not referral_code:
            raise HTTPException(status_code=400, detail="Code de parrainage invalide")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        account_type=payload.account_type,
    )
    session.add(user)
    session.flush()
    if referral_code:
        session.add(Referral(referrer_user_id=referral_code.user_id, referred_user_id=user.id, referral_code=referral_code.code))
    if user.account_type == AccountType.candidate:
        session.add(CandidateProfile(user_id=user.id))
    session.commit()
    session.refresh(user)

    token = create_access_token(user.id, user.account_type)
    return TokenResponse(access_token=token, account_type=user.account_type, user_id=user.id)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    """Correspond au bouton 'Se connecter' de ConnexionScreen (avec le sÃ©lecteur candidat/recruteur)."""
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if user.account_type != payload.account_type:
        raise HTTPException(
            status_code=403,
            detail=f"Ce compte est un compte {user.account_type.value}, pas {payload.account_type.value}",
        )

    token = create_access_token(user.id, user.account_type)
    return TokenResponse(access_token=token, account_type=user.account_type, user_id=user.id)



