from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_  # kept for potential future use
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import User, Voter, Box, Candidate
from app.models.voter import VoteStatus
from app.models.user import UserRole
from app.services.auth import get_current_user_required, require_role
from app.services.logging import log_activity, Actions
from app.services.settings import is_voting_open

router = APIRouter(prefix="/voting", tags=["Voting Day"])
templates = Jinja2Templates(directory="app/templates")


class VoteMarkRequest(BaseModel):
    vote_status: str
    voted_for: Optional[int] = None


@router.get("", response_class=HTMLResponse)
async def voting_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Render the voting day mark page (admin/operator only)."""
    return templates.TemplateResponse(
        "voting/mark.html",
        {"request": request, "user": user, "voting_open": is_voting_open() or user.role == UserRole.admin}
    )


@router.get("/search")
async def search_voters_by_box(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Search for voters by Box# number."""
    query = q.strip()

    voters = db.query(Voter).filter(
        Voter.box_number == query
    ).order_by(Voter.name).all()

    if not voters:
        raise HTTPException(status_code=404, detail="No voters found for this Box#")

    return [
        {
            "id": v.id,
            "voter_id": v.voter_id,
            "national_id": v.national_id,
            "name": v.name,
            "gender": v.gender,
            "age": v.age,
            "photo_path": v.photo_path,
            "is_pledged": v.is_pledged.value if v.is_pledged else "no",
            "vote_status": v.vote_status.value,
            "voted_for": v.voted_for,
            "contact": v.contact,
            "new_contact": v.new_contact,
            "box_name": v.box.name if v.box else None,
            "box_number": v.box_number
        }
        for v in voters
    ]


@router.post("/mark/{voter_id}")
async def mark_vote(
    voter_id: int,
    data: VoteMarkRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Mark a voter's vote status (admin/operator only)."""
    if not is_voting_open() and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Voting is currently closed")

    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    # Validate status
    try:
        new_status = VoteStatus(data.vote_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vote status")

    # Update voter
    old_status = voter.vote_status.value
    voter.vote_status = new_status
    voter.voted_for = data.voted_for if data.voted_for else None

    # Track vote timestamp
    if new_status != VoteStatus.not_voted and old_status == VoteStatus.not_voted.value:
        voter.voted_at = datetime.utcnow()
    elif new_status == VoteStatus.not_voted:
        voter.voted_at = None

    db.commit()

    # Log the action
    log_activity(
        db, Actions.VOTER_STATUS_UPDATE, user,
        entity_type="voter",
        entity_id=voter.id,
        details=f"Changed status from {old_status} to {data.vote_status}",
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Vote status updated", "voter_id": voter_id}
