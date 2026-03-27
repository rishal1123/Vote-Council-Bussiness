from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Candidate, User
from app.models.user import UserRole
from app.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateResponse
from app.services.auth import get_current_user_required, require_role

router = APIRouter(prefix="/candidates", tags=["Candidates"])
templates = Jinja2Templates(directory="app/templates")


# HTML Page route
@router.get("/list", response_class=HTMLResponse)
async def candidates_list_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render candidates management page."""
    return templates.TemplateResponse(
        "manage/candidates.html",
        {"request": request, "user": user}
    )


# API routes
@router.get("", response_model=List[CandidateResponse])
async def list_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """List all candidates."""
    return db.query(Candidate).order_by(Candidate.number).all()


@router.get("/pledged", response_model=CandidateResponse)
async def get_pledged_candidate(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get the pledged candidate."""
    candidate = db.query(Candidate).filter(Candidate.is_pledged == True).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="No pledged candidate set")
    return candidate


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get a specific candidate."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.post("", response_model=CandidateResponse)
async def create_candidate(
    candidate_data: CandidateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Create a new candidate (admin only)."""
    # If setting as pledged, unset other pledged candidates
    if candidate_data.is_pledged:
        db.query(Candidate).filter(Candidate.is_pledged == True).update({"is_pledged": False})

    candidate = Candidate(**candidate_data.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: int,
    candidate_data: CandidateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Update a candidate (admin only)."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    update_data = candidate_data.model_dump(exclude_unset=True)

    # If setting as pledged, unset other pledged candidates
    if update_data.get("is_pledged"):
        db.query(Candidate).filter(
            Candidate.is_pledged == True,
            Candidate.id != candidate_id
        ).update({"is_pledged": False})

    for key, value in update_data.items():
        setattr(candidate, key, value)

    db.commit()
    db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete a candidate (admin only)."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted"}
