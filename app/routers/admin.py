from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, Voter, Box, Focal, Candidate, ActivityLog
from app.models.user import UserRole
from app.models.voter import voter_focal
from app.services.auth import require_role
from app.services.logging import log_activity, Actions
from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render activity logs page."""
    return templates.TemplateResponse(
        "admin/logs.html",
        {"request": request, "user": user}
    )


@router.get("/logs/data")
async def get_logs(
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Get activity logs with filtering."""
    query = db.query(ActivityLog)

    # Filter by date range
    since = datetime.utcnow() - timedelta(days=days)
    query = query.filter(ActivityLog.timestamp >= since)

    # Filter by action
    if action:
        query = query.filter(ActivityLog.action == action)

    # Filter by username
    if username:
        query = query.filter(ActivityLog.username.ilike(f"%{username}%"))

    # Get total count
    total = query.count()

    # Get logs
    logs = query.order_by(desc(ActivityLog.timestamp)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "username": log.username or "System",
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": log.details,
                "ip_address": log.ip_address
            }
            for log in logs
        ]
    }


@router.get("/reset", response_class=HTMLResponse)
async def reset_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render system reset page."""
    return templates.TemplateResponse(
        "admin/reset.html",
        {"request": request, "user": user}
    )


@router.post("/reset/voters")
async def reset_voters(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete all voters (keeps boxes, focals, candidates)."""
    # Delete voter-focal associations
    db.execute(voter_focal.delete())

    # Delete all voters
    count = db.query(Voter).delete()
    db.commit()

    # Log the action
    log_activity(
        db, Actions.SYSTEM_RESET, user,
        details=f"Deleted {count} voters",
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Deleted {count} voters"}


@router.post("/reset/vote-status")
async def reset_vote_status(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Reset all vote statuses to not_voted."""
    from app.models.voter import VoteStatus

    count = db.query(Voter).update({
        Voter.vote_status: VoteStatus.not_voted,
        Voter.voted_for: None
    })
    db.commit()

    log_activity(
        db, Actions.SYSTEM_RESET, user,
        details=f"Reset vote status for {count} voters",
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Reset vote status for {count} voters"}


@router.post("/reset/all")
async def reset_all(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete ALL data except users and logs."""
    # Delete voter-focal associations
    db.execute(voter_focal.delete())

    # Delete all voters
    voter_count = db.query(Voter).delete()

    # Delete all focals
    focal_count = db.query(Focal).delete()

    # Delete all boxes
    box_count = db.query(Box).delete()

    # Delete all candidates
    candidate_count = db.query(Candidate).delete()

    db.commit()

    log_activity(
        db, Actions.SYSTEM_RESET, user,
        details=f"Full reset: {voter_count} voters, {focal_count} focals, {box_count} boxes, {candidate_count} candidates",
        ip_address=request.client.host if request.client else None
    )

    return {
        "message": "System reset complete",
        "deleted": {
            "voters": voter_count,
            "focals": focal_count,
            "boxes": box_count,
            "candidates": candidate_count
        }
    }


@router.delete("/logs")
async def clear_logs(
    days_to_keep: int = Query(30, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Clear old logs, keeping recent ones."""
    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
    count = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff).delete()
    db.commit()

    return {"message": f"Deleted {count} old log entries"}
