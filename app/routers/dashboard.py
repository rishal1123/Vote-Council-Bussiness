from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import Voter, Box, Focal, Candidate, User
from app.models.voter import VoteStatus, PledgeStatus, voter_focal
from app.models.user import UserRole
from app.services.auth import get_current_user_required

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


def _get_focal_for_user(db: Session, user: User) -> Optional[Focal]:
    """If user has focal role, look up their linked Focal record."""
    if user.role == UserRole.focal:
        return db.query(Focal).filter(Focal.user_id == user.id).first()
    return None


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Render the dashboard page."""
    focal = _get_focal_for_user(db, user)
    stats = get_dashboard_stats(db, focal=focal)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "stats": stats, "focal_view": focal is not None}
    )


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get dashboard statistics."""
    focal = _get_focal_for_user(db, user)
    return get_dashboard_stats(db, focal=focal)


def get_dashboard_stats(db: Session, focal: Optional[Focal] = None) -> dict:
    """Calculate all dashboard statistics.

    If focal is provided, all voter queries are scoped to that focal's assigned voters.
    """

    def _base_query():
        """Return a base Voter query, filtered by focal if applicable."""
        q = db.query(Voter)
        if focal:
            q = q.join(voter_focal, Voter.id == voter_focal.c.voter_id).filter(
                voter_focal.c.focal_id == focal.id
            )
        return q

    # Total counts
    total_voters = _base_query().count()
    total_pledged = _base_query().filter(Voter.is_pledged == PledgeStatus.yes).count()

    # Vote status counts
    not_voted = _base_query().filter(Voter.vote_status == VoteStatus.not_voted).count()
    voted_pledged = _base_query().filter(Voter.vote_status == VoteStatus.voted_pledged).count()
    voted_other = _base_query().filter(Voter.vote_status == VoteStatus.voted_other).count()
    undecided = _base_query().filter(Voter.vote_status == VoteStatus.undecided).count()

    total_voted = voted_pledged + voted_other + undecided

    # Stats by box
    box_stats = []
    boxes = db.query(Box).all()
    for box in boxes:
        box_total = _base_query().filter(Voter.box_id == box.id).count()
        if box_total == 0 and focal:
            continue  # Skip boxes with no voters for this focal
        box_voted = _base_query().filter(
            Voter.box_id == box.id,
            Voter.vote_status != VoteStatus.not_voted
        ).count()
        box_pledged_voted = _base_query().filter(
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

    # Stats by focal (only for non-focal users)
    focal_stats = []
    if not focal:
        focals_list = db.query(Focal).all()
        for f in focals_list:
            focal_voters = f.voters
            focal_total = len(focal_voters)
            focal_voted = sum(1 for v in focal_voters if v.vote_status != VoteStatus.not_voted)
            focal_pledged_voted = sum(1 for v in focal_voters if v.vote_status == VoteStatus.voted_pledged)
            focal_stats.append({
                "id": f.id,
                "name": f.name,
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

    # Candidate vote counts
    candidate_stats = []
    candidates = db.query(Candidate).all()
    for candidate in candidates:
        vote_count = _base_query().filter(Voter.voted_for == str(candidate.id)).count()
        candidate_stats.append({
            "id": candidate.id,
            "name": candidate.name,
            "party": candidate.party,
            "number": candidate.number,
            "is_pledged": candidate.is_pledged,
            "votes": vote_count
        })
    # Count undisclosed votes (voted but didn't disclose candidate, or selected "Unknown"/0)
    total_with_candidate = sum(c["votes"] for c in candidate_stats)
    undisclosed_count = total_voted - total_with_candidate
    if undisclosed_count > 0:
        candidate_stats.append({
            "id": 0,
            "name": "Undisclosed",
            "party": "Did not disclose",
            "number": None,
            "is_pledged": False,
            "votes": undisclosed_count
        })

    candidate_stats.sort(key=lambda x: x["votes"], reverse=True)

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
        "candidate_stats": candidate_stats,
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
