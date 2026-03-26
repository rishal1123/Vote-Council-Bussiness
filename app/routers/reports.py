import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.models import User, Voter, Box, Focal, Candidate
from app.models.voter import VoteStatus, PledgeStatus
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
    pledged_count = db.query(Voter).filter(Voter.is_pledged == PledgeStatus.yes).count()
    non_pledged_count = db.query(Voter).filter(Voter.is_pledged != PledgeStatus.yes).count()

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
    """Get voting statistics by box (optimized single query)."""
    rows = db.query(
        Voter.box_id,
        func.count(Voter.id).label('total'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_pledged, 1), else_=0)).label('voted_pledged'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_other, 1), else_=0)).label('voted_other'),
        func.sum(case((Voter.vote_status == VoteStatus.undecided, 1), else_=0)).label('undecided'),
        func.sum(case((Voter.vote_status == VoteStatus.not_voted, 1), else_=0)).label('not_voted'),
        func.sum(case((Voter.is_pledged == PledgeStatus.yes, 1), else_=0)).label('pledged_voters'),
    ).group_by(Voter.box_id).all()

    box_map = {row.box_id: row for row in rows}
    boxes = db.query(Box).all()

    data = []
    for box in boxes:
        row = box_map.get(box.id)
        if not row or row.total == 0:
            continue
        t, vp, vo, u, nv, pv = row.total, row.voted_pledged or 0, row.voted_other or 0, row.undecided or 0, row.not_voted or 0, row.pledged_voters or 0
        data.append({
            "id": box.id, "name": box.name, "total": t,
            "voted_pledged": vp, "voted_other": vo, "undecided": u, "not_voted": nv,
            "pledged_voters": pv,
            "turnout_pct": round((t - nv) / t * 100, 1),
            "pledged_conversion_pct": round(vp / pv * 100, 1) if pv > 0 else 0
        })

    data.sort(key=lambda x: x["turnout_pct"], reverse=True)
    return data


@router.get("/data/by-focal")
async def get_focal_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get voting statistics by focal (optimized single query)."""
    from app.models.voter import voter_focal

    rows = db.query(
        voter_focal.c.focal_id,
        func.count(voter_focal.c.voter_id).label('total'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_pledged, 1), else_=0)).label('voted_pledged'),
        func.sum(case((Voter.vote_status == VoteStatus.voted_other, 1), else_=0)).label('voted_other'),
        func.sum(case((Voter.vote_status == VoteStatus.undecided, 1), else_=0)).label('undecided'),
        func.sum(case((Voter.vote_status == VoteStatus.not_voted, 1), else_=0)).label('not_voted'),
        func.sum(case((Voter.is_pledged == PledgeStatus.yes, 1), else_=0)).label('pledged_voters'),
    ).join(Voter, Voter.id == voter_focal.c.voter_id
    ).group_by(voter_focal.c.focal_id).all()

    focal_map = {row.focal_id: row for row in rows}
    focals = db.query(Focal).all()

    data = []
    for f in focals:
        row = focal_map.get(f.id)
        if not row or row.total == 0:
            continue
        t, vp, vo, u, nv, pv = row.total, row.voted_pledged or 0, row.voted_other or 0, row.undecided or 0, row.not_voted or 0, row.pledged_voters or 0
        data.append({
            "id": f.id, "name": f.name, "total": t,
            "voted_pledged": vp, "voted_other": vo, "undecided": u, "not_voted": nv,
            "pledged_voters": pv,
            "turnout_pct": round((t - nv) / t * 100, 1),
            "pledged_conversion_pct": round(vp / pv * 100, 1) if pv > 0 else 0
        })

    data.sort(key=lambda x: x["turnout_pct"], reverse=True)
    return data


@router.get("/data/pledged-performance")
async def get_pledged_performance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get performance metrics for pledged voters."""
    pledged_voters = db.query(Voter).filter(Voter.is_pledged == PledgeStatus.yes)
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


@router.get("/data/candidates")
async def get_candidate_votes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get vote counts per candidate."""
    candidates = db.query(Candidate).all()
    total_voted = db.query(Voter).filter(Voter.vote_status != VoteStatus.not_voted).count()

    result = []
    accounted = 0
    for c in candidates:
        count = db.query(Voter).filter(Voter.voted_for == str(c.id)).count()
        accounted += count
        result.append({
            "id": c.id,
            "name": c.name,
            "party": c.party,
            "number": c.number,
            "is_pledged": c.is_pledged,
            "votes": count
        })

    # Undisclosed
    undisclosed = total_voted - accounted
    if undisclosed > 0:
        result.append({
            "id": 0,
            "name": "Not Disclosed",
            "party": None,
            "number": None,
            "is_pledged": False,
            "votes": undisclosed
        })

    result.sort(key=lambda x: x["votes"], reverse=True)
    return {"candidates": result, "total_voted": total_voted}


@router.get("/export/voters")
async def export_voters_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Export all voters data as CSV."""
    voters = db.query(Voter).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "EC#", "#", "ID", "Name", "Gender", "Age", "Party",
        "Address", "Contact", "New Contact", "Previous Island",
        "Previous Address", "Current Location", "Box", "Box#",
        "Zone", "Focal(s)", "Focal Comment", "Remarks",
        "Pledged", "Vote Status", "Voted For"
    ])

    for v in voters:
        focals = ", ".join(f.name for f in v.focals) if v.focals else ""
        writer.writerow([
            v.ec_number or "", v.voter_id or "", v.national_id or "",
            v.name, v.gender or "", v.age or "", v.party or "",
            v.address or "", v.contact or "", v.new_contact or "",
            v.previous_island or "", v.previous_address or "",
            v.current_location or "",
            v.box.name if v.box else "", v.box_number or "",
            v.zone or "", focals, v.focal_comment or "", v.remarks or "",
            v.is_pledged.value.title() if v.is_pledged else "No",
            v.vote_status.value.replace("_", " ").title(),
            v.voted_for or ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=voters_export.csv"}
    )


@router.get("/export/votes")
async def export_votes_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Export vote status data as CSV."""
    voters = db.query(Voter).filter(Voter.vote_status != VoteStatus.not_voted).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "EC#", "#", "ID", "Name", "Gender", "Age",
        "Box", "Box#", "Pledged", "Vote Status", "Voted For",
        "Focal(s)"
    ])

    for v in voters:
        focals = ", ".join(f.name for f in v.focals) if v.focals else ""
        writer.writerow([
            v.ec_number or "", v.voter_id or "", v.national_id or "",
            v.name, v.gender or "", v.age or "",
            v.box.name if v.box else "", v.box_number or "",
            v.is_pledged.value.title() if v.is_pledged else "No",
            v.vote_status.value.replace("_", " ").title(),
            v.voted_for or "", focals
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=votes_export.csv"}
    )
