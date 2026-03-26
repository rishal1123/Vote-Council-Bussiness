import os
import shutil
import asyncio
from datetime import datetime
from app.config import settings
from app.services.settings import is_voting_open

BACKUP_DIR = "backups"
MAX_BACKUPS = 50  # Keep last 50 backups


def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def get_db_path():
    """Extract the SQLite file path from DATABASE_URL."""
    url = settings.DATABASE_URL
    # sqlite:///./votecouncil.db or sqlite:///data/votecouncil.db
    path = url.replace("sqlite:///", "")
    if path.startswith("./"):
        path = path[2:]
    return path


def create_backup(reason="manual"):
    """Create a timestamped copy of the database."""
    ensure_backup_dir()
    db_path = get_db_path()

    if not os.path.exists(db_path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"votecouncil_{timestamp}_{reason}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy2(db_path, backup_path)

    # Also copy WAL file if exists (for consistency)
    wal_path = db_path + "-wal"
    if os.path.exists(wal_path):
        shutil.copy2(wal_path, backup_path + "-wal")

    # Cleanup old backups
    cleanup_old_backups()

    return backup_name


def cleanup_old_backups():
    """Keep only the last MAX_BACKUPS backups."""
    ensure_backup_dir()
    backups = sorted(list_backups(), key=lambda b: b["created"], reverse=True)
    for backup in backups[MAX_BACKUPS:]:
        path = os.path.join(BACKUP_DIR, backup["filename"])
        if os.path.exists(path):
            os.remove(path)
        wal = path + "-wal"
        if os.path.exists(wal):
            os.remove(wal)


def list_backups():
    """List all backup files with metadata."""
    ensure_backup_dir()
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".db") and f.startswith("votecouncil_"):
            path = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(path)
            created = os.path.getmtime(path)

            # Parse reason from filename: votecouncil_20260326_120000_startup.db
            parts = f.replace(".db", "").split("_")
            reason = parts[-1] if len(parts) >= 4 else "unknown"

            backups.append({
                "filename": f,
                "size": size,
                "size_mb": round(size / 1024 / 1024, 2),
                "created": datetime.fromtimestamp(created).isoformat(),
                "created_display": datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason
            })

    return sorted(backups, key=lambda b: b["created"], reverse=True)


def delete_backup(filename):
    """Delete a specific backup."""
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        wal = path + "-wal"
        if os.path.exists(wal):
            os.remove(wal)
        return True
    return False


async def backup_scheduler():
    """Background task: backup every 15 minutes while voting is open."""
    while True:
        await asyncio.sleep(900)  # 15 minutes
        if is_voting_open():
            try:
                create_backup("auto")
            except Exception:
                pass
