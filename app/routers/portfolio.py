from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import CandidateProfile, CandidateProject, User

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


class CandidateProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    skills: list[str] = Field(default_factory=list)
    url: str | None = Field(default=None, max_length=500)


def get_candidate(current_user: User, session: Session) -> CandidateProfile:
    if current_user.account_type.value != "candidate":
        raise HTTPException(status_code=403, detail="Un compte candidat est requis")
    candidate = session.exec(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="Complétez votre profil candidat avant de gérer votre portfolio")
    return candidate


@router.get("/me", response_model=list[CandidateProject])
def list_my_projects(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    return session.exec(
        select(CandidateProject).where(CandidateProject.candidate_id == candidate.id).order_by(CandidateProject.created_at.desc())
    ).all()


@router.post("/me", response_model=CandidateProject)
def create_project(payload: CandidateProjectCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    url = payload.url.strip() if payload.url else None
    if url and not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Le lien doit commencer par http:// ou https://")
    project = CandidateProject(
        candidate_id=candidate.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        skills=", ".join(dict.fromkeys(skill.strip() for skill in payload.skills if skill.strip())) or None,
        url=url or None,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/me/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    candidate = get_candidate(current_user, session)
    project = session.get(CandidateProject, project_id)
    if not project or project.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    session.delete(project)
    session.commit()
    return {"deleted": True}