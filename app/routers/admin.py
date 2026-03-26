import os

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, FileResponse
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
from app.services.settings import get_column_settings, save_column_settings, DEFAULT_COLUMNS, is_voting_open, set_voting_open
from app.services.backup import list_backups, create_backup, delete_backup, BACKUP_DIR, get_db_path
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


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render display settings page."""
    return templates.TemplateResponse(
        "admin/settings.html",
        {"request": request, "user": user}
    )


@router.get("/settings/columns")
async def get_columns_settings(
    user: User = Depends(require_role(UserRole.admin))
):
    """Get current column visibility settings."""
    return get_column_settings()


@router.post("/settings")
async def save_settings(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Save column visibility settings."""
    data = await request.json()
    # Ensure 'name' is always visible
    if "name" in data:
        data["name"]["print"] = True
        data["name"]["pdf"] = True
        data["name"]["detail"] = True
    save_column_settings(data)
    return {"message": "Settings saved"}


@router.post("/settings/reset")
async def reset_settings(
    user: User = Depends(require_role(UserRole.admin))
):
    """Reset column visibility settings to defaults."""
    save_column_settings(DEFAULT_COLUMNS.copy())
    return {"message": "Settings reset to defaults"}


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


@router.get("/voting-status")
async def get_voting_status(
    user: User = Depends(require_role(UserRole.admin))
):
    """Get current voting open/closed status."""
    return {"voting_open": is_voting_open()}


@router.post("/voting-status")
async def toggle_voting_status(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Toggle voting open/closed."""
    data = await request.json()
    new_status = data.get("voting_open", False)
    set_voting_open(new_status)

    status_text = "opened" if new_status else "closed"
    log_activity(
        db, "voting_toggle", user,
        details=f"Voting {status_text}",
        ip_address=request.client.host if request.client else None
    )

    return {"voting_open": new_status, "message": f"Voting {status_text}"}


# --- Backups ---

@router.get("/backups", response_class=HTMLResponse)
async def backups_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render backups page."""
    return templates.TemplateResponse(
        "admin/backups.html",
        {"request": request, "user": user}
    )


@router.get("/backups/list")
async def get_backups(
    user: User = Depends(require_role(UserRole.admin))
):
    """List all database backups."""
    return list_backups()


@router.post("/backups/create")
async def create_manual_backup(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Create a manual database backup."""
    filename = create_backup("manual")
    if filename:
        log_activity(db, "backup_create", user, details=f"Created backup: {filename}",
                     ip_address=request.client.host if request.client else None)
        return {"message": "Backup created", "filename": filename}
    raise HTTPException(status_code=500, detail="Failed to create backup")


@router.get("/backups/download/{filename}")
async def download_backup(
    filename: str,
    user: User = Depends(require_role(UserRole.admin))
):
    """Download a backup file."""
    import os
    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, filename=safe_name,
                       media_type="application/octet-stream")


@router.delete("/backups/{filename}")
async def remove_backup(
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Delete a backup file."""
    import os
    safe_name = os.path.basename(filename)
    if delete_backup(safe_name):
        log_activity(db, "backup_delete", user, details=f"Deleted backup: {safe_name}",
                     ip_address=request.client.host if request.client else None)
        return {"message": "Backup deleted"}
    raise HTTPException(status_code=404, detail="Backup not found")


# --- System Stats ---

@router.get("/stats", response_class=HTMLResponse)
async def stats_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render system stats page."""
    return templates.TemplateResponse(
        "admin/stats.html",
        {"request": request, "user": user}
    )


@router.get("/stats/data")
async def get_system_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """Get system statistics."""
    import platform
    import shutil

    # Database stats - try multiple paths
    db_size = 0
    wal_size = 0
    try:
        db_path = get_db_path()
        for path in [db_path, os.path.join("/app", db_path), os.path.abspath(db_path)]:
            if os.path.exists(path):
                db_size = os.path.getsize(path)
                wal = path + "-wal"
                wal_size = os.path.getsize(wal) if os.path.exists(wal) else 0
                break
    except Exception:
        pass

    # Record counts
    try:
        voter_count = db.query(Voter).count()
        box_count = db.query(Box).count()
        focal_count = db.query(Focal).count()
        candidate_count = db.query(Candidate).count()
        user_count = db.query(User).count()
        log_count = db.query(ActivityLog).count()
    except Exception:
        voter_count = box_count = focal_count = candidate_count = user_count = log_count = 0

    # Uploads size
    uploads_size = 0
    uploads_count = 0
    for uploads_dir in ["uploads", "/app/uploads"]:
        if os.path.exists(uploads_dir):
            for f in os.listdir(uploads_dir):
                fp = os.path.join(uploads_dir, f)
                if os.path.isfile(fp):
                    uploads_size += os.path.getsize(fp)
                    uploads_count += 1
            break

    # Backups size
    backups_size = 0
    backups_count = 0
    for bdir in [BACKUP_DIR, "/app/" + BACKUP_DIR]:
        if os.path.exists(bdir):
            for f in os.listdir(bdir):
                fp = os.path.join(bdir, f)
                if os.path.isfile(fp):
                    backups_size += os.path.getsize(fp)
                    backups_count += 1
            break

    # Disk usage
    try:
        disk = shutil.disk_usage("/")
        disk_total = round(disk.total / 1024 / 1024 / 1024, 1)
        disk_used = round(disk.used / 1024 / 1024 / 1024, 1)
        disk_percent = round(disk.used / disk.total * 100, 1)
    except Exception:
        disk_total = disk_used = disk_percent = 0

    # CPU/memory - try psutil, then /proc, then fallback
    cpu_count = os.cpu_count() or 1
    cpu_percent = 0
    mem_total = mem_used = 0
    mem_percent = 0.0

    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem_total = round(mem.total / 1024 / 1024)
        mem_used = round(mem.used / 1024 / 1024)
        mem_percent = mem.percent
    except ImportError:
        # Fallback: read /proc/meminfo (Linux/Docker)
        try:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
                mem_total = round(meminfo.get("MemTotal", 0) / 1024)
                mem_free = round((meminfo.get("MemAvailable", 0) or meminfo.get("MemFree", 0)) / 1024)
                mem_used = mem_total - mem_free
                mem_percent = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0
        except Exception:
            pass
        # CPU usage from /proc/loadavg
        try:
            with open("/proc/loadavg") as f:
                load = float(f.read().split()[0])
                cpu_percent = round(min(load / cpu_count * 100, 100), 1)
        except Exception:
            pass

    return {
        "database": {
            "size_mb": round(db_size / 1024 / 1024, 2),
            "wal_size_mb": round(wal_size / 1024 / 1024, 2),
            "total_size_mb": round((db_size + wal_size) / 1024 / 1024, 2),
        },
        "records": {
            "voters": voter_count,
            "boxes": box_count,
            "focals": focal_count,
            "candidates": candidate_count,
            "users": user_count,
            "logs": log_count,
        },
        "storage": {
            "uploads_count": uploads_count,
            "uploads_mb": round(uploads_size / 1024 / 1024, 2),
            "backups_count": backups_count,
            "backups_mb": round(backups_size / 1024 / 1024, 2),
        },
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": cpu_count,
            "cpu_percent": cpu_percent,
            "memory_total_mb": mem_total,
            "memory_used_mb": mem_used,
            "memory_percent": mem_percent,
            "disk_total_gb": disk_total,
            "disk_used_gb": disk_used,
            "disk_percent": disk_percent,
        }
    }
