from datetime import datetime
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from ..models import CandidateProfile, Company, DipeDeclaration, User
from ..database import get_session
from ..auth import get_current_user, require_admin, require_company_owner

router = APIRouter(prefix="/cnps", tags=["cnps"], dependencies=[Depends(get_current_user)])

# Taux rÃ©els CNPS Cameroun (vÃ©rifiÃ©s â€” Ã  reconfirmer pÃ©riodiquement sur cnps.cm
# car ces barÃ¨mes peuvent Ã©voluer par arrÃªtÃ© ministÃ©riel).
PF_RATE = 0.07                 # Prestations familiales â€” employeur
PVID_EMPLOYER_RATE = 0.028     # Pension vieillesse â€” part employeur
PVID_EMPLOYEE_RATE = 0.014     # Pension vieillesse â€” part salariÃ© (retenue Ã  la source)
SALARY_CAP = 300_000           # Plafond de cotisation mensuel, en FCFA


class ContributionRequest(BaseModel):
    employee_count: int
    average_gross_salary: int
    risk_rate_percent: float   # ex: 1.75, 2.5, 3.5, 5 selon le secteur


class ContributionBreakdown(BaseModel):
    capped_salary: int
    pf_total: float
    pvid_employer_total: float
    pvid_employee_total: float
    atmp_total: float
    employer_total: float
    employee_total: float
    grand_total: float


@router.get("/admin/summary", dependencies=[Depends(require_admin)])
def cnps_admin_summary(session: Session = Depends(get_session)):
    from sqlalchemy import func
    return {
        "dipe_declarations_total": session.exec(select(func.count(DipeDeclaration.id))).one(),
        "dipe_pending_transmission": session.exec(select(func.count(DipeDeclaration.id)).where(DipeDeclaration.status != "Transmise à la CNPS")).one(),
        "companies_total": session.exec(select(func.count(Company.id))).one(),
        "companies_verified": session.exec(select(func.count(Company.id)).where(Company.kyc_verified == True)).one(),
    }

@router.post("/cotisations/calculer", response_model=ContributionBreakdown)
def calculer_cotisations(payload: ContributionRequest):
    """
    Correspond au calculateur de PaiementCotisationsCNPSScreen.
    Reproduit exactement le calcul dÃ©jÃ  prÃ©sent cÃ´tÃ© app (mÃªmes taux), pour
    que le calcul soit fait une seule fois cÃ´tÃ© serveur et reste la source
    de vÃ©ritÃ© â€” l'app affiche le rÃ©sultat renvoyÃ© ici plutÃ´t que de recalculer
    elle-mÃªme.
    """
    capped_salary = min(payload.average_gross_salary, SALARY_CAP)
    count = payload.employee_count
    atmp_rate = payload.risk_rate_percent / 100

    pf_total = capped_salary * PF_RATE * count
    pvid_employer_total = capped_salary * PVID_EMPLOYER_RATE * count
    pvid_employee_total = capped_salary * PVID_EMPLOYEE_RATE * count
    atmp_total = capped_salary * atmp_rate * count

    employer_total = pf_total + pvid_employer_total + atmp_total
    employee_total = pvid_employee_total

    return ContributionBreakdown(
        capped_salary=capped_salary,
        pf_total=round(pf_total, 2),
        pvid_employer_total=round(pvid_employer_total, 2),
        pvid_employee_total=round(pvid_employee_total, 2),
        atmp_total=round(atmp_total, 2),
        employer_total=round(employer_total, 2),
        employee_total=round(employee_total, 2),
        grand_total=round(employer_total + employee_total, 2),
    )


class DipeDeclarationRequest(BaseModel):
    candidate_id: int
    company_id: int
    contract_type: str
    start_date: str
    gross_salary: int
    risk_rate_percent: float
    existing_matricule: str | None = None
    candidate_cni: str | None = None


class DipeDeclarationResponse(BaseModel):
    id: int
    declaration_id: str
    candidate_id: int
    candidate_name: Optional[str] = None
    contract_type: str
    start_date: str
    gross_salary: int
    risk_rate_percent: float
    status: str
    created_at: datetime
    message: Optional[str] = None


@router.post("/declarations/dipe", response_model=DipeDeclarationResponse)
def declarer_embauche(payload: DipeDeclarationRequest, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    require_company_owner(payload.company_id, session, current_user)
    candidate = session.get(CandidateProfile, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Profil candidat introuvable")
    if payload.gross_salary <= 0:
        raise HTTPException(status_code=422, detail="Le salaire doit être supérieur à zéro")
    try:
        start_date = datetime.strptime(payload.start_date, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail="La date doit être au format AAAA-MM-JJ")
    if payload.risk_rate_percent not in (1.75, 2.5, 3.5, 5.0):
        raise HTTPException(status_code=422, detail="Catégorie de risque invalide")
    company = session.get(Company, payload.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")

    declaration = DipeDeclaration(
        reference=f"DIPE-{payload.company_id}-{uuid4().hex[:12].upper()}",
        company_id=payload.company_id,
        candidate_id=payload.candidate_id,
        declared_by_user_id=current_user.id,
        contract_type=payload.contract_type,
        start_date=start_date,
        gross_salary=payload.gross_salary,
        risk_rate_percent=payload.risk_rate_percent,
        existing_matricule=payload.existing_matricule,
        candidate_cni=payload.candidate_cni,
    )
    session.add(declaration)
    session.commit()
    session.refresh(declaration)
    user = session.get(User, candidate.user_id)
    return DipeDeclarationResponse(
        id=declaration.id,
        declaration_id=declaration.reference,
        candidate_id=declaration.candidate_id,
        candidate_name=user.full_name if user else None,
        contract_type=declaration.contract_type,
        start_date=declaration.start_date,
        gross_salary=declaration.gross_salary,
        risk_rate_percent=declaration.risk_rate_percent,
        status=declaration.status,
        created_at=declaration.created_at,
        message="Déclaration enregistrée dans l'application. Elle doit encore être transmise à la CNPS.",
    )


@router.get("/declarations/company/{company_id}", response_model=list[DipeDeclarationResponse])
def list_company_dipe_declarations(company_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    require_company_owner(company_id, session, current_user)
    declarations = session.exec(
        select(DipeDeclaration).where(DipeDeclaration.company_id == company_id).order_by(DipeDeclaration.created_at.desc())
    ).all()
    results = []
    for declaration in declarations:
        candidate = session.get(CandidateProfile, declaration.candidate_id)
        user = session.get(User, candidate.user_id) if candidate else None
        results.append(DipeDeclarationResponse(
            id=declaration.id,
            declaration_id=declaration.reference,
            candidate_id=declaration.candidate_id,
            candidate_name=user.full_name if user else None,
            contract_type=declaration.contract_type,
            start_date=declaration.start_date,
            gross_salary=declaration.gross_salary,
            risk_rate_percent=declaration.risk_rate_percent,
            status=declaration.status,
            created_at=declaration.created_at,
        ))
    return results
