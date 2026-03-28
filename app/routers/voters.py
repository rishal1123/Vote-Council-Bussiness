import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app.models import Voter, Box, Focal, User
from app.models.voter import VoteStatus, PledgeStatus
from app.models.user import UserRole
from app.schemas.voter import (
    VoterCreate, VoterUpdate, VoterResponse, VoterListResponse, VoterStatusUpdate,
    BulkStatusUpdate
)
from app.services.auth import get_current_user_required, require_role
from app.services.logging import log_activity, Actions
from app.services.photo import save_photo, delete_photo
from app.services.settings import get_visible_columns

router = APIRouter(prefix="/voters", tags=["Voters"])
templates = Jinja2Templates(directory="app/templates")


# HTML Page routes (must be before /{voter_id} to avoid conflicts)
@router.get("/list", response_class=HTMLResponse)
async def voters_list_page(
    request: Request,
    user: User = Depends(get_current_user_required)
):
    """Render voters list page."""
    return templates.TemplateResponse(
        "voters/list.html",
        {"request": request, "user": user}
    )


@router.get("/print", response_class=HTMLResponse)
async def voters_print_page(
    request: Request,
    box_id: Optional[int] = Query(None),
    focal_id: Optional[int] = Query(None),
    vote_status: Optional[VoteStatus] = Query(None),
    is_pledged: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Render print-friendly voter list."""
    query = db.query(Voter).options(
        joinedload(Voter.box),
        joinedload(Voter.focals)
    )

    filter_label = "All Voters"
    if box_id:
        query = query.filter(Voter.box_id == box_id)
        box = db.query(Box).filter(Box.id == box_id).first()
        if box:
            filter_label = f"Box: {box.name}"
    if focal_id:
        query = query.join(Voter.focals).filter(Focal.id == focal_id)
        focal_obj = db.query(Focal).filter(Focal.id == focal_id).first()
        if focal_obj:
            filter_label = f"Focal: {focal_obj.name}"
    if vote_status:
        query = query.filter(Voter.vote_status == vote_status)
    if is_pledged is not None:
        try:
            query = query.filter(Voter.is_pledged == PledgeStatus(is_pledged))
        except ValueError:
            pass

    voters = query.order_by(Voter.name).all()

    return templates.TemplateResponse(
        "voters/print.html",
        {
            "request": request,
            "voters": voters,
            "filter_label": filter_label,
            "voter_count": len(voters),
            "print_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "visible": get_visible_columns("print"),
        }
    )


@router.get("/export/pdf", response_class=HTMLResponse)
async def voters_export_pdf(
    request: Request,
    search: Optional[str] = Query(None),
    box_id: Optional[int] = Query(None),
    focal_id: Optional[int] = Query(None),
    vote_status: Optional[VoteStatus] = Query(None),
    is_pledged: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Render PDF-ready voter list (use browser Save as PDF)."""
    query = db.query(Voter).options(
        joinedload(Voter.box),
        joinedload(Voter.focals)
    )

    filter_label = "All Voters"
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Voter.name.ilike(search_term)) |
            (Voter.voter_id.ilike(search_term)) |
            (Voter.national_id.ilike(search_term)) |
            (Voter.contact.ilike(search_term))
        )
        filter_label = f"Search: {search}"
    if box_id:
        query = query.filter(Voter.box_id == box_id)
        box = db.query(Box).filter(Box.id == box_id).first()
        if box:
            filter_label = f"Box: {box.name}"
    if focal_id:
        query = query.join(Voter.focals).filter(Focal.id == focal_id)
        focal_obj = db.query(Focal).filter(Focal.id == focal_id).first()
        if focal_obj:
            filter_label = f"Focal: {focal_obj.name}"
    if vote_status:
        query = query.filter(Voter.vote_status == vote_status)
    if is_pledged is not None:
        try:
            query = query.filter(Voter.is_pledged == PledgeStatus(is_pledged))
        except ValueError:
            pass

    voters = query.order_by(Voter.name).all()

    return templates.TemplateResponse(
        "voters/pdf.html",
        {
            "request": request,
            "voters": voters,
            "filter_label": filter_label,
            "voter_count": len(voters),
            "print_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "visible": get_visible_columns("pdf"),
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def voters_new_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render new voter form."""
    return templates.TemplateResponse(
        "voters/form.html",
        {"request": request, "user": user, "voter": None}
    )


@router.get("/{voter_id}/view", response_class=HTMLResponse)
async def voter_detail_page(
    voter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Render voter detail page."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    return templates.TemplateResponse(
        "voters/detail.html",
        {"request": request, "user": user, "voter": voter, "visible": get_visible_columns("detail")}
    )


@router.get("/{voter_id}/edit", response_class=HTMLResponse)
async def voter_edit_page(
    voter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Render voter edit form."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")
    return templates.TemplateResponse(
        "voters/form.html",
        {"request": request, "user": user, "voter": voter}
    )


# API routes
@router.get("", response_model=List[VoterListResponse])
async def list_voters(
    search: Optional[str] = Query(None),
    box_id: Optional[int] = Query(None),
    focal_id: Optional[int] = Query(None),
    vote_status: Optional[VoteStatus] = Query(None),
    is_pledged: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """List voters with filtering options."""
    query = db.query(Voter).options(
        joinedload(Voter.box),
        joinedload(Voter.focals)
    )

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Voter.name.ilike(search_term)) |
            (Voter.voter_id.ilike(search_term)) |
            (Voter.national_id.ilike(search_term)) |
            (Voter.contact.ilike(search_term))
        )

    if box_id:
        query = query.filter(Voter.box_id == box_id)

    if focal_id:
        query = query.join(Voter.focals).filter(Focal.id == focal_id)

    if vote_status:
        query = query.filter(Voter.vote_status == vote_status)

    if is_pledged is not None:
        try:
            query = query.filter(Voter.is_pledged == PledgeStatus(is_pledged))
        except ValueError:
            pass

    # Order and paginate
    voters = query.order_by(Voter.name).offset(offset).limit(limit).all()

    return [
        VoterListResponse(
            id=v.id,
            name=v.name,
            voter_id=v.voter_id,
            national_id=v.national_id,
            photo_path=v.photo_path,
            box={"id": v.box.id, "name": v.box.name} if v.box else None,
            is_pledged=v.is_pledged,
            vote_status=v.vote_status,
            contact=v.contact,
            focals=[{"id": f.id, "name": f.name} for f in v.focals]
        )
        for v in voters
    ]


@router.get("/count")
async def count_voters(
    search: Optional[str] = Query(None),
    box_id: Optional[int] = Query(None),
    focal_id: Optional[int] = Query(None),
    vote_status: Optional[VoteStatus] = Query(None),
    is_pledged: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get count of voters matching filters."""
    query = db.query(Voter)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Voter.name.ilike(search_term)) |
            (Voter.voter_id.ilike(search_term)) |
            (Voter.national_id.ilike(search_term)) |
            (Voter.contact.ilike(search_term))
        )

    if box_id:
        query = query.filter(Voter.box_id == box_id)

    if focal_id:
        query = query.join(Voter.focals).filter(Focal.id == focal_id)

    if vote_status:
        query = query.filter(Voter.vote_status == vote_status)

    if is_pledged is not None:
        try:
            query = query.filter(Voter.is_pledged == PledgeStatus(is_pledged))
        except ValueError:
            pass

    return {"count": query.count()}


@router.get("/export/csv")
async def export_voters_csv(
    search: Optional[str] = Query(None),
    box_id: Optional[int] = Query(None),
    focal_id: Optional[int] = Query(None),
    vote_status: Optional[VoteStatus] = Query(None),
    is_pledged: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Export filtered voters as CSV."""
    query = db.query(Voter).options(
        joinedload(Voter.box),
        joinedload(Voter.focals)
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Voter.name.ilike(search_term)) |
            (Voter.voter_id.ilike(search_term)) |
            (Voter.national_id.ilike(search_term)) |
            (Voter.contact.ilike(search_term))
        )

    if box_id:
        query = query.filter(Voter.box_id == box_id)

    if focal_id:
        query = query.join(Voter.focals).filter(Focal.id == focal_id)

    if vote_status:
        query = query.filter(Voter.vote_status == vote_status)

    if is_pledged is not None:
        try:
            query = query.filter(Voter.is_pledged == PledgeStatus(is_pledged))
        except ValueError:
            pass

    voters = query.order_by(Voter.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "EC#", "#", "ID", "Name", "Gender", "Age", "Party",
        "Address", "Contact", "New Contact", "Previous Island",
        "Previous Address", "Current Location", "Box", "Box#",
        "Zone", "Focal(s)", "Focal Comment", "Remarks",
        "Pledged", "Vote Status", "Voted For", "Voted At"
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
            v.voted_for or "",
            v.voted_at.strftime("%Y-%m-%d %H:%M:%S") if v.voted_at else ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=voters_filtered.csv"}
    )


@router.get("/{voter_id}", response_model=VoterResponse)
async def get_voter(
    voter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get a specific voter."""
    voter = db.query(Voter).options(
        joinedload(Voter.box),
        joinedload(Voter.focals)
    ).filter(Voter.id == voter_id).first()

    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    return VoterResponse(
        id=voter.id,
        name=voter.name,
        voter_id=voter.voter_id,
        gender=voter.gender,
        age=voter.age,
        party=voter.party,
        address=voter.address,
        contact=voter.contact,
        new_contact=voter.new_contact,
        previous_island=voter.previous_island,
        previous_address=voter.previous_address,
        current_location=voter.current_location,
        zone=voter.zone,
        focal_comment=voter.focal_comment,
        photo_path=voter.photo_path,
        box_id=voter.box_id,
        box={"id": voter.box.id, "name": voter.box.name} if voter.box else None,
        is_pledged=voter.is_pledged,
        vote_status=voter.vote_status,
        voted_for=voter.voted_for,
        voted_at=voter.voted_at,
        focals=[{"id": f.id, "name": f.name} for f in voter.focals],
        created_at=voter.created_at,
        updated_at=voter.updated_at
    )


@router.post("", response_model=VoterResponse)
async def create_voter(
    voter_data: VoterCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Create a new voter."""
    # Check for duplicate voter_id
    if voter_data.voter_id:
        existing = db.query(Voter).filter(Voter.voter_id == voter_data.voter_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Voter ID already exists")

    # Get focals
    focals = []
    if voter_data.focal_ids:
        focals = db.query(Focal).filter(Focal.id.in_(voter_data.focal_ids)).all()

    voter = Voter(
        **voter_data.model_dump(exclude={"focal_ids"}),
        focals=focals
    )
    db.add(voter)
    db.commit()
    db.refresh(voter)

    log_activity(db, Actions.VOTER_CREATE, user=user, details=f"Created voter: {voter.name}", entity_type="Voter", entity_id=voter.id, ip_address=request.client.host if request.client else None)

    return await get_voter(voter.id, db, user)


@router.put("/{voter_id}", response_model=VoterResponse)
async def update_voter(
    voter_id: int,
    voter_data: VoterUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Update a voter."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    update_data = voter_data.model_dump(exclude_unset=True, exclude={"focal_ids"})
    for key, value in update_data.items():
        setattr(voter, key, value)

    # Update focals if provided
    if voter_data.focal_ids is not None:
        focals = db.query(Focal).filter(Focal.id.in_(voter_data.focal_ids)).all()
        voter.focals = focals

    db.commit()
    db.refresh(voter)

    log_activity(db, Actions.VOTER_UPDATE, user=user, details=f"Updated voter: {voter.name}", entity_type="Voter", entity_id=voter.id, ip_address=request.client.host if request.client else None)

    return await get_voter(voter.id, db, user)


@router.post("/{voter_id}/photo")
async def upload_voter_photo(
    voter_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Upload a photo for a voter."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    # Delete old photo if exists
    if voter.photo_path:
        delete_photo(voter.photo_path)

    # Save new photo
    filename = await save_photo(photo)
    voter.photo_path = filename
    db.commit()

    return {"message": "Photo uploaded", "photo_path": filename}


@router.delete("/{voter_id}/photo")
async def delete_voter_photo(
    voter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Delete a voter's photo."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    if voter.photo_path:
        delete_photo(voter.photo_path)
        voter.photo_path = None
        db.commit()

    return {"message": "Photo deleted"}


@router.patch("/{voter_id}/status")
async def update_vote_status(
    voter_id: int,
    status_data: VoterStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Quick update of vote status (admin/operator only)."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    old_status = voter.vote_status
    voter.vote_status = status_data.vote_status
    if status_data.voted_for:
        voter.voted_for = status_data.voted_for

    # Track vote timestamp
    if status_data.vote_status != VoteStatus.not_voted and old_status == VoteStatus.not_voted:
        voter.voted_at = datetime.utcnow()
    elif status_data.vote_status == VoteStatus.not_voted:
        voter.voted_at = None

    db.commit()

    return {
        "message": "Status updated",
        "vote_status": voter.vote_status.value,
        "voted_for": voter.voted_for
    }


@router.post("/bulk-status")
async def bulk_update_status(
    bulk_data: BulkStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Bulk update vote status for multiple voters."""
    voters = db.query(Voter).filter(Voter.id.in_(bulk_data.voter_ids)).all()

    for voter in voters:
        old_status = voter.vote_status
        voter.vote_status = bulk_data.vote_status
        if bulk_data.voted_for:
            voter.voted_for = bulk_data.voted_for

        # Track vote timestamp (same logic as single status update)
        if bulk_data.vote_status != VoteStatus.not_voted and old_status == VoteStatus.not_voted:
            voter.voted_at = datetime.utcnow()
        elif bulk_data.vote_status == VoteStatus.not_voted:
            voter.voted_at = None

    db.commit()

    return {"message": f"Updated {len(voters)} voters"}


from pydantic import BaseModel as PydanticBaseModel


class PledgeUpdate(PydanticBaseModel):
    is_pledged: str


class BulkPledgeUpdate(PydanticBaseModel):
    voter_ids: List[int]
    is_pledged: str


@router.patch("/{voter_id}/pledge")
async def update_pledge_status(
    voter_id: int,
    data: PledgeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Update a voter's pledge status (admin only)."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    old_pledge = voter.is_pledged.value if voter.is_pledged else "none"
    try:
        voter.is_pledged = PledgeStatus(data.is_pledged)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pledge status")

    db.commit()

    log_activity(db, "pledge_update", user=user, details=f"Updated pledge for {voter.name}: {old_pledge} -> {data.is_pledged}", entity_type="Voter", entity_id=voter.id, ip_address=request.client.host if request.client else None)

    return {"message": "Pledge status updated", "is_pledged": voter.is_pledged.value}


@router.post("/bulk-pledge")
async def bulk_update_pledge(
    data: BulkPledgeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Bulk update pledge status for multiple voters (admin only)."""
    try:
        pledge_status = PledgeStatus(data.is_pledged)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pledge status")

    voters = db.query(Voter).filter(Voter.id.in_(data.voter_ids)).all()
    for voter in voters:
        voter.is_pledged = pledge_status

    db.commit()

    log_activity(db, "bulk_pledge_update", user=user, details=f"Bulk pledge update to '{data.is_pledged}' for {len(voters)} voters", entity_type="Voter", ip_address=request.client.host if request.client else None)

    return {"message": f"Updated pledge status for {len(voters)} voters"}


@router.delete("/{voter_id}")
async def delete_voter(
    voter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete a voter (admin only)."""
    voter = db.query(Voter).filter(Voter.id == voter_id).first()
    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    voter_name = voter.name
    voter_id_val = voter.id

    # Delete photo if exists
    if voter.photo_path:
        delete_photo(voter.photo_path)

    db.delete(voter)
    db.commit()

    log_activity(db, Actions.VOTER_DELETE, user=user, details=f"Deleted voter: {voter_name}", entity_type="Voter", entity_id=voter_id_val, ip_address=request.client.host if request.client else None)

    return {"message": "Voter deleted"}
