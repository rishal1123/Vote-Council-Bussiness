from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.user import UserRole
from app.services.auth import get_current_user_required, require_role
from app.services.excel_import import import_voters_from_excel

router = APIRouter(prefix="/import", tags=["Import"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def import_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render the import page (admin only)."""
    return templates.TemplateResponse(
        "import.html",
        {"request": request, "user": user}
    )


@router.post("/excel")
async def import_excel(
    file: UploadFile = File(...),
    import_photos: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """
    Import voters from Excel file (admin only).
    Auto-creates boxes and focals as needed.
    Optionally imports embedded photos.
    """
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)"
        )

    # Read file content
    content = await file.read()

    # Import voters
    stats = import_voters_from_excel(db, content, import_photos=import_photos)

    return stats
