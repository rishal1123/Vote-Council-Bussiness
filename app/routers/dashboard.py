from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, case, literal_column
from typing import Optional

from app.database import get_db
from app.models import Voter, Box, Focal, Candidate, User
from app.models.voter import VoteStatus, voter_focal
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
    stats = get_dashboard_stats(db, focal=focal)
    db.close()  # Release connection immediately
    return stats


def get_dashboard_stats(db: Session, focal: Optional[Focal] = None) -> dict:
    """Calculate all dashboard statistics using optimized aggregate queries."""

    def _base_query():
        q = db.query(Voter)
        if focal:
            q = q.join(voter_focal, Voter.id == voter_focal.c.voter_id).filter(
                voter_focal.c.focal_id == focal.id
            )
        return q

    # Single aggregate query for all vote status counts + pledge count
    stats_row = _base_query().with_entities(
        func.count(Voter.id).label('total'),
        func.sum(case((Voter.is_pledged == True, 1), else_=0)).label('pledged'),
        func.sum(case((Voter.vote_status == VoteStatus.not_voted, 1), else_=0)).label('not_voted'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_pledged, 1), else_=0)).label('voted_pledged'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_other, 1), else_=0)).label('voted_other'),
        func.sum(case((Voter.vote_status == VoteStatus.undecided, 1), else_=0)).label('undecided'),
    ).first()

    total_voters = stats_row.total or 0
    total_pledged = stats_row.pledged or 0
    not_voted = stats_row.not_voted or 0
    voted_pledged = stats_row.voted_pledged or 0
    voted_other = stats_row.voted_other or 0
    undecided = stats_row.undecided or 0
    total_voted = voted_pledged + voted_other + undecided

    # Box stats - single aggregate query
    box_query = _base_query().with_entities(
        Voter.box_id,
        func.count(Voter.id).label('total'),
        func.sum(case((Voter.vote_status != VoteStatus.not_voted, 1), else_=0)).label('voted'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_pledged, 1), else_=0)).label('pledged_voted'),
    ).group_by(Voter.box_id)

    box_data = {row.box_id: row for row in box_query.all()}
    boxes = db.query(Box).all()
    box_stats = []
    for box in boxes:
        row = box_data.get(box.id)
        if not row:
            if focal:
                continue
            box_stats.append({"id": box.id, "name": box.name, "total": 0, "voted": 0, "remaining": 0, "pledged_voted": 0, "percentage": 0})
            continue
        bt, bv, bp = row.total or 0, row.voted or 0, row.pledged_voted or 0
        box_stats.append({
            "id": box.id, "name": box.name, "total": bt, "voted": bv,
            "remaining": bt - bv, "pledged_voted": bp,
            "percentage": round((bv / bt * 100) if bt > 0 else 0, 1)
        })

    # Focal stats - single aggregate query (only for non-focal users)
    focal_stats = []
    if not focal:
        focal_rows = db.query(
            voter_focal.c.focal_id,
            func.count(voter_focal.c.voter_id).label('total'),
            func.sum(case((Voter.vote_status != VoteStatus.not_voted, 1), else_=0)).label('voted'),
            func.sum(case((Voter.vote_status == VoteStatus.voted_pledged, 1), else_=0)).label('pledged_voted'),
        ).join(Voter, Voter.id == voter_focal.c.voter_id
        ).group_by(voter_focal.c.focal_id).all()

        focal_data = {row.focal_id: row for row in focal_rows}
        focals_list = db.query(Focal).all()
        for f in focals_list:
            row = focal_data.get(f.id)
            ft = row.total if row else 0
            fv = row.voted if row else 0
            fp = row.pledged_voted if row else 0
            focal_stats.append({
                "id": f.id, "name": f.name, "total": ft, "voted": fv,
                "remaining": ft - fv, "pledged_voted": fp,
                "percentage": round((fv / ft * 100) if ft > 0 else 0, 1)
            })
        focal_stats.sort(key=lambda x: x["name"])

    # Pledged candidate
    pledged_candidate = db.query(Candidate).filter(Candidate.is_pledged == True).first()

    # Candidate vote counts - single aggregate query
    candidate_rows = _base_query().with_entities(
        Voter.voted_for, func.count(Voter.id)
    ).filter(Voter.voted_for != None).group_by(Voter.voted_for).all()

    vote_counts = {str(row[0]): row[1] for row in candidate_rows}
    candidates = db.query(Candidate).all()
    candidate_stats = []
    total_with_candidate = 0
    for c in candidates:
        count = vote_counts.get(str(c.id), 0)
        total_with_candidate += count
        candidate_stats.append({
            "id": c.id, "name": c.name, "party": c.party,
            "number": c.number, "color": c.color, "is_pledged": c.is_pledged, "votes": count
        })

    undisclosed_count = total_voted - total_with_candidate
    if undisclosed_count > 0:
        candidate_stats.append({
            "id": 0, "name": "Undisclosed", "party": "Did not disclose",
            "number": None, "color": "#8D99AE", "is_pledged": False, "votes": undisclosed_count
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
