from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Voter, Box, Focal, Candidate, User
from app.models.voter import VoteStatus
from app.services.auth import get_current_user_required

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Render the dashboard page."""
    stats = get_dashboard_stats(db)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "stats": stats}
    )


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get dashboard statistics."""
    return get_dashboard_stats(db)


def get_dashboard_stats(db: Session) -> dict:
    """Calculate all dashboard statistics."""
    # Total counts
    total_voters = db.query(Voter).count()
    total_pledged = db.query(Voter).filter(Voter.is_pledged == True).count()

    # Vote status counts
    not_voted = db.query(Voter).filter(Voter.vote_status == VoteStatus.not_voted).count()
    voted_pledged = db.query(Voter).filter(Voter.vote_status == VoteStatus.voted_pledged).count()
    voted_other = db.query(Voter).filter(Voter.vote_status == VoteStatus.voted_other).count()
    undecided = db.query(Voter).filter(Voter.vote_status == VoteStatus.undecided).count()

    total_voted = voted_pledged + voted_other + undecided

    # Stats by box
    box_stats = []
    boxes = db.query(Box).all()
    for box in boxes:
        box_total = db.query(Voter).filter(Voter.box_id == box.id).count()
        box_voted = db.query(Voter).filter(
            Voter.box_id == box.id,
            Voter.vote_status != VoteStatus.not_voted
        ).count()
        box_pledged_voted = db.query(Voter).filter(
            Voter.box_id == box.id,
            Voter.vote_status == VoteStatus.voted_pledged
        ).count()
        box_stats.append({
            "id": box.id,
            "name": box.name,
            "total": box_total,
            "voted": box_voted,
            "remaining": box_total - box_voted,
            "pledged_voted": box_pledged_voted,
            "percentage": round((box_voted / box_total * 100) if box_total > 0 else 0, 1)
        })

    # Stats by focal
    focal_stats = []
    focals = db.query(Focal).all()
    for focal in focals:
        focal_voters = focal.voters
        focal_total = len(focal_voters)
        focal_voted = sum(1 for v in focal_voters if v.vote_status != VoteStatus.not_voted)
        focal_pledged_voted = sum(1 for v in focal_voters if v.vote_status == VoteStatus.voted_pledged)
        focal_stats.append({
            "id": focal.id,
            "name": focal.name,
            "total": focal_total,
            "voted": focal_voted,
            "remaining": focal_total - focal_voted,
            "pledged_voted": focal_pledged_voted,
            "percentage": round((focal_voted / focal_total * 100) if focal_total > 0 else 0, 1)
        })

    # Sort focal stats alphabetically by name
    focal_stats.sort(key=lambda x: x["name"])

    # Get pledged candidate
    pledged_candidate = db.query(Candidate).filter(Candidate.is_pledged == True).first()

    return {
        "total_voters": total_voters,
        "total_pledged": total_pledged,
        "total_voted": total_voted,
        "remaining": not_voted,
        "vote_breakdown": {
            "not_voted": not_voted,
            "voted_pledged": voted_pledged,
            "voted_other": voted_other,
            "undecided": undecided
        },
        "turnout_percentage": round((total_voted / total_voters * 100) if total_voters > 0 else 0, 1),
        "pledged_conversion": round((voted_pledged / total_pledged * 100) if total_pledged > 0 else 0, 1),
        "box_stats": box_stats,
        "focal_stats": focal_stats,
        "pledged_candidate": {
            "id": pledged_candidate.id,
            "name": pledged_candidate.name,
            "party": pledged_candidate.party
        } if pledged_candidate else None
    }


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, user: User = Depends(get_current_user_required)):
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=302)
