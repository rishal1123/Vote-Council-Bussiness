from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Box, Voter, User
from app.models.user import UserRole
from app.schemas.box import BoxCreate, BoxUpdate, BoxResponse
from app.services.auth import get_current_user_required, require_role
from app.services.logging import log_activity, Actions

router = APIRouter(prefix="/boxes", tags=["Boxes"])
templates = Jinja2Templates(directory="app/templates")


# HTML Page route
@router.get("/list", response_class=HTMLResponse)
async def boxes_list_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render boxes management page."""
    return templates.TemplateResponse(
        "manage/boxes.html",
        {"request": request, "user": user}
    )


# API routes
@router.get("", response_model=List[BoxResponse])
async def list_boxes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """List all boxes."""
    boxes = db.query(Box).all()
    result = []
    for box in boxes:
        voter_count = db.query(Voter).filter(Voter.box_id == box.id).count()
        result.append(BoxResponse(
            id=box.id,
            name=box.name,
            location=box.location,
            voter_count=voter_count
        ))
    return result


@router.get("/{box_id}", response_model=BoxResponse)
async def get_box(
    box_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get a specific box."""
    box = db.query(Box).filter(Box.id == box_id).first()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    voter_count = db.query(Voter).filter(Voter.box_id == box.id).count()
    return BoxResponse(
        id=box.id,
        name=box.name,
        location=box.location,
        voter_count=voter_count
    )


@router.post("", response_model=BoxResponse)
async def create_box(
    box_data: BoxCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Create a new box."""
    # Check if box name exists
    existing = db.query(Box).filter(Box.name == box_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Box with this name already exists")

    box = Box(**box_data.model_dump())
    db.add(box)
    db.commit()
    db.refresh(box)

    log_activity(db, Actions.BOX_CREATE, user=user, details=f"Created box: {box.name}", entity_type="Box", entity_id=box.id, ip_address=request.client.host if request.client else None)

    return BoxResponse(id=box.id, name=box.name, location=box.location, voter_count=0)


@router.put("/{box_id}", response_model=BoxResponse)
async def update_box(
    box_id: int,
    box_data: BoxUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Update a box."""
    box = db.query(Box).filter(Box.id == box_id).first()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    # Check for duplicate name
    if box_data.name:
        existing = db.query(Box).filter(Box.name == box_data.name, Box.id != box_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Box with this name already exists")

    update_data = box_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(box, key, value)

    db.commit()
    db.refresh(box)

    log_activity(db, Actions.BOX_UPDATE, user=user, details=f"Updated box: {box.name}", entity_type="Box", entity_id=box.id, ip_address=request.client.host if request.client else None)

    voter_count = db.query(Voter).filter(Voter.box_id == box.id).count()
    return BoxResponse(id=box.id, name=box.name, location=box.location, voter_count=voter_count)


@router.delete("/{box_id}")
async def delete_box(
    box_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete a box (admin only)."""
    box = db.query(Box).filter(Box.id == box_id).first()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    # Check if box has voters
    voter_count = db.query(Voter).filter(Voter.box_id == box.id).count()
    if voter_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete box with {voter_count} voters. Reassign voters first."
        )

    box_name = box.name
    box_id_val = box.id
    db.delete(box)
    db.commit()

    log_activity(db, Actions.BOX_DELETE, user=user, details=f"Deleted box: {box_name}", entity_type="Box", entity_id=box_id_val, ip_address=request.client.host if request.client else None)

    return {"message": "Box deleted"}
