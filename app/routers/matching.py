from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ..database import get_session
from ..auth import get_current_user, require_job_company_owner
from ..models import CandidateProfile, JobOffer

router = APIRouter(prefix="/matching", tags=["matching"], dependencies=[Depends(get_current_user)])


def compute_match_score(candidate_text: str, job_text: str) -> float:
    """
    Calcule un score de correspondance entre 0 et 100.

    Approche : TF-IDF + similaritÃ© cosinus. C'est une mÃ©thode simple et
    entiÃ¨rement locale (pas d'appel API payant), suffisante pour un premier
    systÃ¨me de matching fonctionnel. Pour aller plus loin, on peut remplacer
    ceci par des embeddings sÃ©mantiques (ex: sentence-transformers ou l'API
    d'embeddings d'un fournisseur LLM) qui captent mieux le sens que le simple
    recoupement de mots-clÃ©s du TF-IDF.
    """
    if not candidate_text.strip() or not job_text.strip():
        return 0.0

    vectorizer = TfidfVectorizer(stop_words=None)
    try:
        tfidf_matrix = vectorizer.fit_transform([candidate_text, job_text])
    except ValueError:
        # Survient si les deux textes n'ont aucun mot en commun avec le vocabulaire
        return 0.0

    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(similarity) * 100, 1)


class MatchScoreResponse(BaseModel):
    candidate_id: int
    job_offer_id: int
    match_score: float


@router.get("/score", response_model=MatchScoreResponse)
def get_match_score(
    candidate_id: int,
    job_offer_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """
    UtilisÃ© par DetailsCandidatScreen pour afficher le badge de score IA
    (ex: '94% de correspondance') cÃ´tÃ© recruteur.
    """
    candidate = session.get(CandidateProfile, candidate_id)
    job = session.get(JobOffer, job_offer_id)
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidat ou offre introuvable")

    candidate_text = " ".join(filter(None, [
        candidate.job_title, candidate.summary, candidate.skills,
    ]))
    require_job_company_owner(job_offer_id, session, current_user)
    job_text = " ".join(filter(None, [job.title, job.description, job.requirements]))

    score = compute_match_score(candidate_text, job_text)
    return MatchScoreResponse(candidate_id=candidate_id, job_offer_id=job_offer_id, match_score=score)


class RankedCandidate(BaseModel):
    candidate_id: int
    full_name: str
    job_title: str | None
    match_score: float


@router.get("/recommendations/{job_offer_id}", response_model=list[RankedCandidate])
def get_recommended_candidates(job_offer_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """
    UtilisÃ© par RecommandationsIARecruteurScreen : renvoie tous les candidats
    triÃ©s par score de correspondance dÃ©croissant pour une offre donnÃ©e.
    """
    job = session.get(JobOffer, job_offer_id)
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    require_job_company_owner(job_offer_id, session, current_user)
    job_text = " ".join(filter(None, [job.title, job.description, job.requirements]))
    candidates = session.exec(select(CandidateProfile)).all()

    results = []
    for c in candidates:
        candidate_text = " ".join(filter(None, [c.job_title, c.summary, c.skills]))
        score = compute_match_score(candidate_text, job_text)
        # Import diffÃ©rÃ© pour Ã©viter une dÃ©pendance circulaire avec le modÃ¨le User
        from ..models import User
        user = session.get(User, c.user_id)
        results.append(RankedCandidate(
            candidate_id=c.id,
            full_name=user.full_name if user else "Candidat",
            job_title=c.job_title,
            match_score=score,
        ))

    results.sort(key=lambda r: r.match_score, reverse=True)
    return results






