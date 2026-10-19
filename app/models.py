from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


# ============================================================
# ENUMS
# ============================================================

class AccountType(str, Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


# ============================================================
# USER
# ============================================================

class User(SQLModel, table=True):
    """
    Compte utilisateur :
    candidat / recruteur / administrateur.
    """

    __tablename__ = "users"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    full_name: str = Field(
        max_length=255
    )

    email: str = Field(
        max_length=255,
        unique=True,
        index=True
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=30
    )

    hashed_password: str = Field(
        max_length=255
    )

    account_type: AccountType = Field(
        default=AccountType.candidate,
        max_length=20
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# CANDIDATE PROFILE
# ============================================================

class CandidateProfile(SQLModel, table=True):
    """
    Profil détaillé d'un candidat.
    """

    __tablename__ = "candidate_profiles"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    job_title: Optional[str] = Field(
        default=None,
        max_length=255
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    summary: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    skills: Optional[str] = Field(
        default=None,
        max_length=2000
    )

    years_experience: Optional[int] = None

    cnps_matricule: Optional[str] = Field(
        default=None,
        max_length=100
    )


# ============================================================
# COMPANY
# ============================================================

class Company(SQLModel, table=True):
    """
    Profil entreprise lié au compte recruteur.
    """

    __tablename__ = "companies"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    owner_user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    name: str = Field(
        max_length=255
    )

    sector: Optional[str] = Field(
        default=None,
        max_length=255
    )

    description: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    cnps_employer_matricule: Optional[str] = Field(
        default=None,
        max_length=100
    )

    kyc_verified: bool = Field(
        default=False
    )


# ============================================================
# JOB OFFER
# ============================================================

class JobOffer(SQLModel, table=True):
    """
    Offre d'emploi publiée par un recruteur.
    """

    __tablename__ = "job_offers"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    company_id: int = Field(
        foreign_key="companies.id"
    )

    title: str = Field(
        max_length=255
    )

    description: str = Field(
        max_length=4000
    )

    requirements: str = Field(
        max_length=4000
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    contract_type: Optional[str] = Field(
        default=None,
        max_length=100
    )

    salary_min: Optional[int] = None

    salary_max: Optional[int] = None

    status: str = Field(
        default="Ouvert",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# APPLICATION
# ============================================================

class Application(SQLModel, table=True):
    """
    Candidature d'un candidat à une offre.
    """

    __tablename__ = "applications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    job_offer_id: int = Field(
        foreign_key="job_offers.id"
    )

    status: str = Field(
        default="Envoyée",
        max_length=50
    )

    match_score: Optional[float] = None

    motivation_message: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# SAVED JOB
# ============================================================

class SavedJob(SQLModel, table=True):
    """
    Offre sauvegardée en favori par un candidat.
    """

    __tablename__ = "saved_jobs"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    job_offer_id: int = Field(
        foreign_key="job_offers.id"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# CONVERSATION
# ============================================================

class Conversation(SQLModel, table=True):
    """
    Discussion entre un candidat et une entreprise.
    """

    __tablename__ = "conversations"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    company_id: int = Field(
        foreign_key="companies.id"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# MESSAGE
# ============================================================

class Message(SQLModel, table=True):
    """
    Message individuel dans une conversation.
    """

    __tablename__ = "messages"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    conversation_id: int = Field(
        foreign_key="conversations.id"
    )

    sender_user_id: int = Field(
        foreign_key="users.id"
    )

    text: str = Field(
        max_length=4000
    )

    read: bool = Field(
        default=False
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# INTERVIEW
# ============================================================

class Interview(SQLModel, table=True):
    """
    Entretien planifié pour une candidature.
    """

    __tablename__ = "interviews"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    application_id: int = Field(
        foreign_key="applications.id"
    )

    scheduled_at: datetime

    mode: str = Field(
        default="video",
        max_length=30
    )

    location_or_link: Optional[str] = Field(
        default=None,
        max_length=500
    )

    status: str = Field(
        default="Planifié",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(SQLModel, table=True):
    """
    Notification utilisateur.
    """

    __tablename__ = "notifications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id"
    )

    type: str = Field(
        max_length=50
    )

    title: str = Field(
        max_length=255
    )

    body: str = Field(
        max_length=4000
    )

    read: bool = Field(
        default=False
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# JOB ALERT
# ============================================================

class JobAlert(SQLModel, table=True):
    """
    Alerte emploi d'un candidat.
    """

    __tablename__ = "job_alerts"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    title: str = Field(
        max_length=255
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    frequency: str = Field(
        default="instant",
        max_length=30
    )

    active: bool = Field(
        default=True
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# MODERATION REPORT
# ============================================================

class ModerationReport(SQLModel, table=True):
    """
    Signalement d'une offre ou d'un utilisateur.
    """

    __tablename__ = "moderation_reports"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    job_offer_id: Optional[int] = Field(
        default=None,
        foreign_key="job_offers.id"
    )

    reported_user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id"
    )

    reported_by_user_id: int = Field(
        foreign_key="users.id"
    )

    reason: str = Field(
        max_length=2000
    )

    status: str = Field(
        default="En attente",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# BANNED ACCOUNT
# ============================================================

class BannedAccount(SQLModel, table=True):
    """
    Compte utilisateur banni.
    """

    __tablename__ = "banned_accounts"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    reason: str = Field(
        max_length=2000
    )

    definitive: bool = Field(
        default=False
    )

    banned_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    active: bool = Field(
        default=True
    )