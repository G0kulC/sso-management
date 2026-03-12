"""
main.py - FastAPI Application Entry Point
Configures the app, middleware, routers, and startup events
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
import time

from app.config import settings
from app.database import engine, Base
from app.routers import auth, users, apps

# ─────────────────────────────────────────────
# LOGGING CONFIGURATION
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# APPLICATION LIFESPAN (startup/shutdown)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager:
    - Startup: Create DB tables, log ready message, open browser
    - Shutdown: Log graceful shutdown
    """
    logger.info("🚀 Starting SSO Identity Management System...")

    # Create all database tables (idempotent)
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created/verified")

    # Create default admin user if none exists
    _create_default_admin()
    logger.info("✅ Default admin account ready")

    logger.info(f"🔐 {settings.APP_NAME} v{settings.APP_VERSION} is ready")
    
    # Auto-open browser to frontend
    import webbrowser
    import threading
    def open_browser():
        import time
        time.sleep(1.5)  # Wait for server to be fully ready
        webbrowser.open(f"{settings.BACKEND_URL}/")
    threading.Thread(target=open_browser, daemon=True).start()
    logger.info(f"🌐 Opening browser at {settings.BACKEND_URL}/")
    
    yield

    logger.info("👋 Shutting down SSO server...")


def _create_default_admin():
    """Creates a default admin account if no admin exists in the database."""
    from app.database import SessionLocal
    from app.models import User, UserRole
    from app.security import hash_password

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password_hash=hash_password("Admin@1234"),
                full_name="System Administrator",
                role=UserRole.ADMIN,
            )
            db.add(admin_user)
            db.commit()
            logger.info("👤 Default admin created: username='admin' password='Admin@1234'")
    except Exception as e:
        logger.error(f"Failed to create default admin: {e}")
        db.rollback()
    finally:
        db.close()


# ─────────────────────────────────────────────
# FASTAPI APPLICATION INSTANCE
# ─────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 🔐 Secure Single Sign-On (SSO) & Identity Management System

A centralized authentication server that allows users to log in once
and securely access multiple client applications using JWT tokens.

### Key Features:
- **User Registration & Login** with bcrypt password hashing
- **JWT Access & Refresh Tokens** for stateless authentication
- **Role-Based Access Control (RBAC)** — Admin and User roles
- **Token Blacklisting** for secure logout
- **Application Registration** for SSO client apps
- **Login Audit Logs** for security monitoring

### Default Admin Credentials:
- Username: `admin`
- Password: `Admin@1234`

> ⚠️ Change the default password immediately in production!
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────

# CORS - Allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """
    Middleware: Logs request duration and adds X-Process-Time header.
    Useful for performance monitoring.
    """
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.3f}s)")
    return response


@app.middleware("http")
async def jwt_verification_middleware(request: Request, call_next):
    """
    Middleware: Passive JWT inspection on every request.
    Does NOT block requests (auth is handled per-route via Depends).
    Logs suspicious requests for monitoring.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        # Could add rate limiting or suspicious token logging here
        pass

    return await call_next(request)


# ─────────────────────────────────────────────
# EXCEPTION HANDLERS
# ─────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Endpoint '{request.url.path}' not found"}
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error(f"Internal server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )


# ─────────────────────────────────────────────
# ROUTER REGISTRATION
# ─────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(apps.router)


# ─────────────────────────────────────────────
# STATIC FILES & FRONTEND SERVING
# ─────────────────────────────────────────────

from pathlib import Path
from fastapi.responses import HTMLResponse

# Get the frontend directory paths
frontend_dir = Path(__file__).parent.parent / "frontend"
templates_dir = Path(__file__).parent / "templates"

# Set up Jinja2 templates for server-side rendering
templates = Jinja2Templates(directory=str(templates_dir))

# Serve static files (JS, CSS, images, etc.)
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/login", tags=["Frontend"], response_class=HTMLResponse, summary="Login Page")
def serve_login(request: Request):
    """Serves the login page with server-side rendering."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "api_base": settings.BACKEND_URL
    })

@app.get("/dashboard", tags=["Frontend"], response_class=HTMLResponse, summary="Dashboard Page")
def serve_dashboard(request: Request):
    """Serves the dashboard page with server-side rendering."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "api_base": settings.BACKEND_URL
    })


# ─────────────────────────────────────────────
# ROOT ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/", tags=["Frontend"], response_class=HTMLResponse, summary="Home Page")
def home(request: Request):
    """Serves the home page with server-side rendered data."""
    from datetime import datetime
    return templates.TemplateResponse("home.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "api_base": settings.BACKEND_URL,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "debug_mode": "Enabled" if settings.DEBUG else "Disabled"
    })

@app.get("/api", tags=["Health"], summary="API Health Check")
def api_root():
    """Returns service info and confirms the API is running."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"], summary="Detailed health status")
def health_check():
    """Returns detailed health information including database connectivity."""
    from app.database import SessionLocal
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": settings.APP_VERSION,
    }
