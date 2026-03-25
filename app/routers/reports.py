from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Voter, Box, Focal
from app.models.voter import VoteStatus
from app.services.auth import get_current_user_required

router = APIRouter(prefix="/reports", tags=["Reports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    user: User = Depends(get_current_user_required)
):
    """Render reports page with charts."""
    return templates.TemplateResponse(
        "reports/index.html",
        {"request": request, "user": user}
    )


@router.get("/data/overview")
async def get_overview_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get overview statistics for charts."""
    # Vote status breakdown
    status_counts = db.query(
        Voter.vote_status,
        func.count(Voter.id)
    ).group_by(Voter.vote_status).all()

    vote_status_data = {
        "not_voted": 0,
        "voted_pledged": 0,
        "voted_other": 0,
        "undecided": 0
    }
    for status, count in status_counts:
        vote_status_data[status.value] = count

    # Pledged vs non-pledged
    pledged_count = db.query(Voter).filter(Voter.is_pledged == True).count()
    non_pledged_count = db.query(Voter).filter(Voter.is_pledged == False).count()

    # Gender breakdown
    gender_counts = db.query(
        Voter.gender,
        func.count(Voter.id)
    ).group_by(Voter.gender).all()

    gender_data = {}
    for gender, count in gender_counts:
        key = gender if gender else "Unknown"
        gender_data[key] = count

    # Age distribution
    age_ranges = [
        ("18-25", 18, 25),
        ("26-35", 26, 35),
        ("36-45", 36, 45),
        ("46-55", 46, 55),
        ("56-65", 56, 65),
        ("65+", 66, 200),
        ("Unknown", None, None)
    ]

    age_data = {}
    for label, min_age, max_age in age_ranges:
        if min_age is None:
            count = db.query(Voter).filter(Voter.age == None).count()
        else:
            count = db.query(Voter).filter(
                Voter.age >= min_age,
                Voter.age <= max_age
            ).count()
        age_data[label] = count

    # Turnout by hour (if we had timestamps for vote status changes)
    # For now, just return overall stats

    return {
        "vote_status": vote_status_data,
        "pledged": {
            "pledged": pledged_count,
            "not_pledged": non_pledged_count
        },
        "gender": gender_data,
        "age": age_data,
        "totals": {
            "total_voters": pledged_count + non_pledged_count,
            "total_voted": vote_status_data["voted_pledged"] + vote_status_data["voted_other"] + vote_status_data["undecided"],
            "total_remaining": vote_status_data["not_voted"]
        }
    }


@router.get("/data/by-box")
async def get_box_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get voting statistics by box."""
    boxes = db.query(Box).all()

    data = []
    for box in boxes:
        voters = db.query(Voter).filter(Voter.box_id == box.id)
        total = voters.count()

        if total == 0:
            continue

        voted_pledged = voters.filter(Voter.vote_status == VoteStatus.voted_pledged).count()
        voted_other = voters.filter(Voter.vote_status == VoteStatus.voted_other).count()
        undecided = voters.filter(Voter.vote_status == VoteStatus.undecided).count()
        not_voted = voters.filter(Voter.vote_status == VoteStatus.not_voted).count()
        pledged_voters = voters.filter(Voter.is_pledged == True).count()

        data.append({
            "id": box.id,
            "name": box.name,
            "total": total,
            "voted_pledged": voted_pledged,
            "voted_other": voted_other,
            "undecided": undecided,
            "not_voted": not_voted,
            "pledged_voters": pledged_voters,
            "turnout_pct": round((total - not_voted) / total * 100, 1),
            "pledged_conversion_pct": round(voted_pledged / pledged_voters * 100, 1) if pledged_voters > 0 else 0
        })

    # Sort by turnout
    data.sort(key=lambda x: x["turnout_pct"], reverse=True)

    return data


@router.get("/data/by-focal")
async def get_focal_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get voting statistics by focal."""
    focals = db.query(Focal).all()

    data = []
    for focal in focals:
        voters = focal.voters
        total = len(voters)

        if total == 0:
            continue

        voted_pledged = sum(1 for v in voters if v.vote_status == VoteStatus.voted_pledged)
        voted_other = sum(1 for v in voters if v.vote_status == VoteStatus.voted_other)
        undecided = sum(1 for v in voters if v.vote_status == VoteStatus.undecided)
        not_voted = sum(1 for v in voters if v.vote_status == VoteStatus.not_voted)
        pledged_voters = sum(1 for v in voters if v.is_pledged)

        data.append({
            "id": focal.id,
            "name": focal.name,
            "total": total,
            "voted_pledged": voted_pledged,
            "voted_other": voted_other,
            "undecided": undecided,
            "not_voted": not_voted,
            "pledged_voters": pledged_voters,
            "turnout_pct": round((total - not_voted) / total * 100, 1),
            "pledged_conversion_pct": round(voted_pledged / pledged_voters * 100, 1) if pledged_voters > 0 else 0
        })

    # Sort by turnout
    data.sort(key=lambda x: x["turnout_pct"], reverse=True)

    return data


@router.get("/data/pledged-performance")
async def get_pledged_performance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get performance metrics for pledged voters."""
    pledged_voters = db.query(Voter).filter(Voter.is_pledged == True)
    total_pledged = pledged_voters.count()

    if total_pledged == 0:
        return {
            "total_pledged": 0,
            "voted_as_pledged": 0,
            "voted_other": 0,
            "not_voted": 0,
            "conversion_rate": 0
        }

    voted_pledged = pledged_voters.filter(Voter.vote_status == VoteStatus.voted_pledged).count()
    voted_other = pledged_voters.filter(Voter.vote_status == VoteStatus.voted_other).count()
    undecided = pledged_voters.filter(Voter.vote_status == VoteStatus.undecided).count()
    not_voted = pledged_voters.filter(Voter.vote_status == VoteStatus.not_voted).count()

    return {
        "total_pledged": total_pledged,
        "voted_as_pledged": voted_pledged,
        "voted_other": voted_other,
        "undecided": undecided,
        "not_voted": not_voted,
        "conversion_rate": round(voted_pledged / total_pledged * 100, 1),
        "turnout_rate": round((total_pledged - not_voted) / total_pledged * 100, 1)
    }
