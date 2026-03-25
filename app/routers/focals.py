from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Focal, Voter, User
from app.models.user import UserRole
from app.schemas.focal import FocalCreate, FocalUpdate, FocalResponse
from app.services.auth import get_current_user_required, require_role

router = APIRouter(prefix="/focals", tags=["Focals"])
templates = Jinja2Templates(directory="app/templates")


# HTML Page route
@router.get("/list", response_class=HTMLResponse)
async def focals_list_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Render focals management page."""
    return templates.TemplateResponse(
        "manage/focals.html",
        {"request": request, "user": user}
    )


# API routes
@router.get("", response_model=List[FocalResponse])
async def list_focals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """List all focals."""
    focals = db.query(Focal).order_by(Focal.name).all()
    result = []
    for focal in focals:
        voter_count = len(focal.voters)
        result.append(FocalResponse(
            id=focal.id,
            name=focal.name,
            phone=focal.phone,
            user_id=focal.user_id,
            voter_count=voter_count
        ))
    return result


@router.get("/{focal_id}", response_model=FocalResponse)
async def get_focal(
    focal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get a specific focal."""
    focal = db.query(Focal).filter(Focal.id == focal_id).first()
    if not focal:
        raise HTTPException(status_code=404, detail="Focal not found")

    return FocalResponse(
        id=focal.id,
        name=focal.name,
        phone=focal.phone,
        user_id=focal.user_id,
        voter_count=len(focal.voters)
    )


@router.post("", response_model=FocalResponse)
async def create_focal(
    focal_data: FocalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Create a new focal."""
    focal = Focal(**focal_data.model_dump())
    db.add(focal)
    db.commit()
    db.refresh(focal)

    return FocalResponse(
        id=focal.id,
        name=focal.name,
        phone=focal.phone,
        user_id=focal.user_id,
        voter_count=0
    )


@router.put("/{focal_id}", response_model=FocalResponse)
async def update_focal(
    focal_id: int,
    focal_data: FocalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.operator))
):
    """Update a focal."""
    focal = db.query(Focal).filter(Focal.id == focal_id).first()
    if not focal:
        raise HTTPException(status_code=404, detail="Focal not found")

    update_data = focal_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(focal, key, value)

    db.commit()
    db.refresh(focal)

    return FocalResponse(
        id=focal.id,
        name=focal.name,
        phone=focal.phone,
        user_id=focal.user_id,
        voter_count=len(focal.voters)
    )


@router.delete("/{focal_id}")
async def delete_focal(
    focal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete a focal (admin only)."""
    focal = db.query(Focal).filter(Focal.id == focal_id).first()
    if not focal:
        raise HTTPException(status_code=404, detail="Focal not found")

    # Remove focal from all voters first
    focal.voters = []
    db.commit()

    db.delete(focal)
    db.commit()
    return {"message": "Focal deleted"}


@router.get("/{focal_id}/voters")
async def get_focal_voters(
    focal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """Get all voters assigned to a focal."""
    focal = db.query(Focal).filter(Focal.id == focal_id).first()
    if not focal:
        raise HTTPException(status_code=404, detail="Focal not found")

    voters = []
    for voter in focal.voters:
        voters.append({
            "id": voter.id,
            "name": voter.name,
            "voter_id": voter.voter_id,
            "is_pledged": voter.is_pledged,
            "vote_status": voter.vote_status.value,
            "box": {"id": voter.box.id, "name": voter.box.name} if voter.box else None
        })

    return voters
