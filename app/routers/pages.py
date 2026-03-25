from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models import User
from app.models.user import UserRole
from app.services.auth import require_role

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")


# User management page (admin only)
@router.get("/users/list", response_class=HTMLResponse)
async def users_list_page(
    request: Request,
    user: User = Depends(require_role(UserRole.admin))
):
    """Render users management page."""
    return templates.TemplateResponse(
        "manage/users.html",
        {"request": request, "user": user}
    )
