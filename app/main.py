from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import asyncio
import time
from collections import defaultdict

from app.config import settings
from app.database import init_db, SessionLocal
from app.services.auth import create_default_admin, get_current_user
from app.services.logging import log_activity, Actions
from app.services.backup import create_backup, backup_scheduler
from app.routers import auth, voters, focals, candidates, boxes, import_data, dashboard, pages, admin, reports, voting

# Create FastAPI app — disable docs in production
app = FastAPI(
    title=settings.APP_NAME,
    description="Voter Management PWA for Election Day",
    version=settings.APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Allow service worker from /static/ to control / scope
        if request.url.path == "/static/sw.js":
            response.headers["Service-Worker-Allowed"] = "/"
        # Prevent caching HTML pages (ensures latest JS is always served)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net static.cloudflareinsights.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "font-src 'self' cdn.jsdelivr.net; "
            "connect-src 'self' cdn.jsdelivr.net *.jsdelivr.net cloudflareinsights.com *.cloudflareinsights.com"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting for login attempts
login_attempts = defaultdict(list)  # IP -> list of timestamps
RATE_LIMIT_WINDOW = 300  # 5 minutes
RATE_LIMIT_MAX = 10  # max attempts per window


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/auth/login" and request.method == "POST":
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            # Clean old entries
            login_attempts[ip] = [t for t in login_attempts[ip] if now - t < RATE_LIMIT_WINDOW]
            if len(login_attempts[ip]) >= RATE_LIMIT_MAX:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Please try again in a few minutes."}
                )
            login_attempts[ip].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# CORS — restrict to own domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://voterslife.com",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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


# Inject app_version into all Jinja2 template environments for cache-busting
from jinja2 import Environment
_original_get_template = Environment.get_template
def _patched_get_template(self, name, *args, **kwargs):
    self.globals['app_version'] = settings.APP_VERSION
    return _original_get_template(self, name, *args, **kwargs)
Environment.get_template = _patched_get_template


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
        create_backup("startup")
        log_activity(db, Actions.APP_STARTUP, details="Application started successfully")
        # Start background backup scheduler
        asyncio.create_task(backup_scheduler())
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
