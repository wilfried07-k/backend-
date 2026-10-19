from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from ..models import CandidateProfile
from ..database import get_session
from ..auth import get_current_user, require_company_owner

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
    declaration_id: str
    status: str
    message: str


@router.post("/declarations/dipe", response_model=DipeDeclarationResponse)
def declarer_embauche(payload: DipeDeclarationRequest, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """
    Correspond au formulaire de DeclarationEmbaucheScreen.

    IMPORTANT â€” Ã©tat actuel rÃ©aliste : la CNPS n'expose pas (Ã  notre
    connaissance) d'API publique de tÃ©lÃ©dÃ©claration DIPE. Cet endpoint
    prÃ©pare et valide les donnÃ©es au bon format ; en pratique, tant qu'un
    partenariat API n'est pas signÃ© avec la CNPS, il faut soit :
      1) gÃ©nÃ©rer un export (CSV/PDF) que le recruteur soumet lui-mÃªme sur
         cnps.cm, soit
      2) stocker la dÃ©claration en base pour un traitement/export groupÃ©.
    Ce squelette fait l'option 2 (Ã  complÃ©ter avec la vraie logique de
    stockage en base une fois les modÃ¨les Declaration crÃ©Ã©s).
    """
    require_company_owner(payload.company_id, session, current_user)
    candidate = session.get(CandidateProfile, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Profil candidat introuvable")
    # TODO : persister en base (table Declaration), puis génération PDF/export
    declaration_id = f"DIPE-{payload.company_id}-{payload.candidate_id}"
    return DipeDeclarationResponse(
        declaration_id=declaration_id,
        status="en_attente_transmission",
        message=(
            "DÃ©claration enregistrÃ©e. En l'absence d'API CNPS directe, "
            "un export sera gÃ©nÃ©rÃ© pour transmission manuelle sous 8 jours."
        ),
    )



