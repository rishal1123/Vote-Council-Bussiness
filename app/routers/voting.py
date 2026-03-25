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
from app.services.auth import get_current_user_required
from app.services.logging import log_activity, Actions

router = APIRouter(prefix="/voting", tags=["Voting Day"])
templates = Jinja2Templates(directory="app/templates")


class VoteMarkRequest(BaseModel):
    vote_status: str
    voted_for: Optional[int] = None


@router.get("", response_class=HTMLResponse)
async def voting_page(
    request: Request,
    user: User = Depends(get_current_user_required)
):
    """Render the voting day mark page."""
    return templates.TemplateResponse(
        "voting/mark.html",
        {"request": request, "user": user}
    )


@router.get("/search")
async def search_voter(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Search for a voter by national ID number."""
    query = q.strip()

    # Search by national_id only
    voter = db.query(Voter).filter(Voter.national_id == query).first()

    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    # Get box name
    box_name = None
    if voter.box:
        box_name = voter.box.name

    return {
        "id": voter.id,
        "voter_id": voter.voter_id,
        "name": voter.name,
        "gender": voter.gender,
        "age": voter.age,
        "photo_path": voter.photo_path,
        "is_pledged": voter.is_pledged.value if voter.is_pledged else "no",
        "vote_status": voter.vote_status.value,
        "voted_for": voter.voted_for,
        "contact": voter.contact,
        "new_contact": voter.new_contact,
        "box_name": box_name
    }


@router.post("/mark/{voter_id}")
async def mark_vote(
    voter_id: int,
    data: VoteMarkRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Mark a voter's vote status."""
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
