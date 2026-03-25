from sqlalchemy.orm import Session
from typing import Optional
from app.models.log import ActivityLog
from app.models.user import User


def log_activity(
    db: Session,
    action: str,
    user: Optional[User] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Log an activity to the database."""
    log = ActivityLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
    return log


# Common action types
class Actions:
    # Auth
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"

    # Voter
    VOTER_CREATE = "voter_create"
    VOTER_UPDATE = "voter_update"
    VOTER_DELETE = "voter_delete"
    VOTER_STATUS_UPDATE = "voter_status_update"
    VOTER_PHOTO_UPLOAD = "voter_photo_upload"

    # Import
    IMPORT_START = "import_start"
    IMPORT_COMPLETE = "import_complete"
    IMPORT_FAILED = "import_failed"

    # System
    APP_STARTUP = "app_startup"
    APP_ERROR = "app_error"

    # Admin
    SYSTEM_RESET = "system_reset"
    USER_CREATE = "user_create"
    USER_DELETE = "user_delete"

    # Box/Focal/Candidate
    BOX_CREATE = "box_create"
    BOX_UPDATE = "box_update"
    BOX_DELETE = "box_delete"
    FOCAL_CREATE = "focal_create"
    FOCAL_UPDATE = "focal_update"
    FOCAL_DELETE = "focal_delete"
    CANDIDATE_CREATE = "candidate_create"
    CANDIDATE_UPDATE = "candidate_update"
    CANDIDATE_DELETE = "candidate_delete"
