from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import require_admin
from ..models import ModerationReport, BannedAccount, Company, JobOffer, User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class ReportCreate(BaseModel):
    job_offer_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    reported_by_user_id: int
    reason: str


@router.post("/reports", response_model=ModerationReport)
def create_report(payload: ReportCreate, session: Session = Depends(get_session)):
    """Point d'entrÃ©e utilisÃ© par les utilisateurs pour signaler (bouton 'Signaler')."""
    report = ModerationReport(**payload.dict())
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@router.get("/reports", response_model=list[ModerationReport])
def list_reports(status: str = "En attente", session: Session = Depends(get_session)):
    """Correspond Ã  la file de ModerationLitigesScreen / ModerationOffresFrauduleusesScreen."""
    return session.exec(select(ModerationReport).where(ModerationReport.status == status)).all()


class ReportResolve(BaseModel):
    status: str            # RÃ©solu / EscaladÃ©
    remove_job: bool = False


@router.patch("/reports/{report_id}")
def resolve_report(report_id: int, payload: ReportResolve, session: Session = Depends(get_session)):
    """Correspond aux boutons 'Ignorer' / 'Supprimer l'offre' de ModerationLitigesScreen."""
    report = session.get(ModerationReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Signalement introuvable")

    report.status = payload.status
    session.add(report)

    if payload.remove_job and report.job_offer_id:
        job = session.get(JobOffer, report.job_offer_id)
        if job:
            job.status = "FermÃ©"
            session.add(job)

    session.commit()
    return {"updated": True}


@router.get("/kyc/pending", response_model=list[Company])
def list_pending_kyc(session: Session = Depends(get_session)):
    """Correspond Ã  la file de ModerationKYCScreen."""
    return session.exec(select(Company).where(Company.kyc_verified == False)).all()


@router.patch("/kyc/{company_id}")
def review_kyc(company_id: int, approve: bool, session: Session = Depends(get_session)):
    """Correspond aux boutons 'Approuver' / 'ComplÃ©ments requis' de ModerationKYCScreen."""
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    company.kyc_verified = approve
    session.add(company)
    session.commit()
    return {"company_id": company_id, "kyc_verified": company.kyc_verified}


class BanRequest(BaseModel):
    user_id: int
    reason: str
    definitive: bool = False


@router.post("/ban", response_model=BannedAccount)
def ban_user(payload: BanRequest, session: Session = Depends(get_session)):
    """Correspond Ã  GestionBannissementsScreen et BannissementDefinitifScreen (double confirmation faite cÃ´tÃ© app)."""
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    existing = session.exec(select(BannedAccount).where(BannedAccount.user_id == payload.user_id)).first()
    if existing:
        existing.reason = payload.reason
        existing.definitive = payload.definitive
        existing.active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    banned = BannedAccount(user_id=payload.user_id, reason=payload.reason, definitive=payload.definitive)
    session.add(banned)
    session.commit()
    session.refresh(banned)
    return banned


@router.get("/banned", response_model=list[BannedAccount])
def list_banned(session: Session = Depends(get_session)):
    """Correspond Ã  la liste de GestionBannissementsScreen."""
    return session.exec(select(BannedAccount).where(BannedAccount.active == True)).all()


@router.patch("/unban/{user_id}")
def unban_user(user_id: int, session: Session = Depends(get_session)):
    """Correspond au bouton 'RÃ©habiliter' de GestionBannissementsScreen."""
    banned = session.exec(select(BannedAccount).where(BannedAccount.user_id == user_id)).first()
    if not banned:
        raise HTTPException(status_code=404, detail="Compte non banni")
    if banned.definitive:
        raise HTTPException(status_code=403, detail="Bannissement dÃ©finitif, rÃ©habilitation impossible")
    banned.active = False
    session.add(banned)
    session.commit()
    return {"unbanned": True}






