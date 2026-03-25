from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db, SessionLocal
from app.services.auth import create_default_admin, get_current_user
from app.services.logging import log_activity, Actions
from app.routers import auth, voters, focals, candidates, boxes, import_data, dashboard, pages, admin, reports, voting

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Voter Management PWA for Election Day",
    version="1.0.0"
)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "font-src 'self' cdn.jsdelivr.net"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware — allow_origins=["*"] is open for development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Safe: prevents cross-origin cookie sending with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers - pages first for correct route priority
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(pages.router)  # Must be before API routers for /voters/list etc.
app.include_router(voters.router)
app.include_router(focals.router)
app.include_router(candidates.router)
app.include_router(boxes.router)
app.include_router(import_data.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(voting.router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon."""
    return FileResponse("static/icons/favicon.ico")


@app.on_event("startup")
async def startup_event():
    """Initialize database and create default admin user."""
    init_db()
    db = SessionLocal()
    try:
        create_default_admin(db)
        log_activity(db, Actions.APP_STARTUP, details="Application started successfully")
    except Exception as e:
        log_activity(db, Actions.APP_ERROR, details=f"Startup error: {str(e)}")
        raise
    finally:
        db.close()


@app.middleware("http")
async def error_logging_middleware(request: Request, call_next):
    """Log application errors to the activity log."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        db = SessionLocal()
        try:
            log_activity(
                db, Actions.APP_ERROR,
                details=f"{request.method} {request.url.path}: {type(e).__name__}: {str(e)}",
                ip_address=request.client.host if request.client else None
            )
        except Exception:
            pass
        finally:
            db.close()
        raise


@app.middleware("http")
async def auth_redirect_middleware(request: Request, call_next):
    """Redirect unauthenticated users to login page for HTML requests."""
    # Skip for static files, auth routes, and API routes
    path = request.url.path
    if (
        path.startswith("/static") or
        path.startswith("/uploads") or
        path.startswith("/auth") or
        path.startswith("/api") or
        path == "/favicon.ico" or
        "json" in request.headers.get("accept", "")
    ):
        return await call_next(request)

    # Check authentication for HTML pages
    from app.database import get_db
    db = SessionLocal()
    try:
        user = await get_current_user(request, None, db)
        if not user and path != "/auth/login":
            return RedirectResponse(url="/auth/login", status_code=302)
    finally:
        db.close()

    return await call_next(request)
