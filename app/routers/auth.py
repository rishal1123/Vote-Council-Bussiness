from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_user,
    get_current_user_required,
    require_role
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    """Render login page."""
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Handle login form submission."""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=400
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value}
    )

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return response


@router.get("/logout")
async def logout():
    """Handle logout."""
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# API endpoints for user management (admin only)
@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin))
):
    """List all users (admin only)."""
    return db.query(User).all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin))
):
    """Create a new user (admin only)."""
    # Check if username exists
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin))
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user_required)):
    """Get current user info."""
    return user
