from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user, require_candidate_owner
from ..database import get_session
from ..models import CandidateProfile, SkillAssessment, User

router = APIRouter(prefix="/assessments", tags=["skills assessments"], dependencies=[Depends(get_current_user)])

TESTS = [
    {
        "id": "javascript_basics",
        "name": "JavaScript — fondamentaux",
        "questions": [
            {"id": "js1", "prompt": "Quel mot-clé déclare une variable réassignable avec une portée de bloc ?", "options": ["const", "let", "static", "global"], "answer": 1},
            {"id": "js2", "prompt": "Que renvoie Array.prototype.map() ?", "options": ["Un tableau transformé", "Un booléen", "Le premier élément", "Une chaîne"], "answer": 0},
            {"id": "js3", "prompt": "Quel opérateur compare valeur et type sans conversion ?", "options": ["==", "=", "===", "!="], "answer": 2},
        ],
    },
    {
        "id": "agile_basics",
        "name": "Gestion de projet agile",
        "questions": [
            {"id": "ag1", "prompt": "Quel est l’objectif principal d’une rétrospective ?", "options": ["Évaluer les personnes", "Améliorer la façon de travailler", "Valider le budget", "Distribuer les tâches futures"], "answer": 1},
            {"id": "ag2", "prompt": "Qui priorise généralement le backlog produit en Scrum ?", "options": ["Product Owner", "Scrum Master", "Chaque développeur séparément", "Le client après chaque sprint"], "answer": 0},
            {"id": "ag3", "prompt": "Que représente un sprint ?", "options": ["Une période de travail limitée", "Une réunion quotidienne", "Un document de spécifications", "Une version majeure obligatoire"], "answer": 0},
        ],
    },
    {
        "id": "excel_basics",
        "name": "Excel — analyse de données",
        "questions": [
            {"id": "ex1", "prompt": "Quelle formule additionne les cellules A1 à A5 ?", "options": ["=COUNT(A1:A5)", "=SUM(A1:A5)", "=ADD(A1-A5)", "=TOTAL(A1:A5)"], "answer": 1},
            {"id": "ex2", "prompt": "À quoi sert un tableau croisé dynamique ?", "options": ["À résumer et analyser des données", "À verrouiller un fichier", "À créer une macro automatiquement", "À supprimer les doublons du classeur"], "answer": 0},
            {"id": "ex3", "prompt": "Quel outil permet de ne montrer que les lignes répondant à un critère ?", "options": ["Fusionner", "Filtrer", "Transposer", "Consolider"], "answer": 1},
        ],
    },
]


class AnswerInput(BaseModel):
    question_id: str
    selected_option: int = Field(ge=0, le=10)


class AssessmentSubmit(BaseModel):
    test_id: str
    answers: list[AnswerInput]


def get_candidate(current_user: User, session: Session) -> CandidateProfile:
    if current_user.account_type.value != "candidate":
        raise HTTPException(status_code=403, detail="Un compte candidat est requis")
    candidate = session.exec(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="Complétez votre profil candidat avant de passer un test")
    return candidate


def public_test(test: dict):
    return {
        "id": test["id"],
        "name": test["name"],
        "questions": [
            {"id": question["id"], "prompt": question["prompt"], "options": question["options"]}
            for question in test["questions"]
        ],
    }


@router.get("/tests")
def list_tests():
    return [public_test(test) for test in TESTS]


@router.get("/me", response_model=list[SkillAssessment])
def list_my_assessments(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    return session.exec(
        select(SkillAssessment)
        .where(SkillAssessment.candidate_id == candidate.id)
        .order_by(SkillAssessment.created_at.desc())
    ).all()


@router.get("/{assessment_id}", response_model=SkillAssessment)
def get_assessment(assessment_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    assessment = session.get(SkillAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Résultat introuvable")
    require_candidate_owner(assessment.candidate_id, session, current_user)
    return assessment


@router.post("/submit", response_model=SkillAssessment)
def submit_assessment(payload: AssessmentSubmit, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    test = next((item for item in TESTS if item["id"] == payload.test_id), None)
    if not test:
        raise HTTPException(status_code=404, detail="Test introuvable")
    expected = {question["id"]: question for question in test["questions"]}
    received = {answer.question_id: answer.selected_option for answer in payload.answers}
    if len(received) != len(payload.answers) or set(received) != set(expected):
        raise HTTPException(status_code=400, detail="Réponds une seule fois à chaque question")
    if any(option >= len(expected[question_id]["options"]) for question_id, option in received.items()):
        raise HTTPException(status_code=400, detail="Réponse invalide")
    score = sum(received[question_id] == question["answer"] for question_id, question in expected.items())
    percentage = round(score * 100 / len(expected))
    badge = "Expert" if percentage >= 90 else "Confirmé" if percentage >= 70 else "Débutant"
    result = SkillAssessment(
        candidate_id=candidate.id,
        test_id=test["id"],
        test_name=test["name"],
        score=score,
        total_questions=len(expected),
        percentage=percentage,
        badge=badge,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result