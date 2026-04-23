"""
Library Card Digitization System - FastAPI Application
Main application file with all routes and database models.
"""

import os
import logging

from fastapi import FastAPI, Request, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from models.db import Base, engine
from config import get_settings

# --- Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Application Settings
settings = get_settings()

# --- Directory Setup
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.join(settings.data_dir, "exports"), exist_ok=True)

# --- Database Configuration
# Database setup and models are moved into models/db.py

# --- CSRF Protection
# CSRF settings moved to security.py

# --- FastAPI Application Setup
app = FastAPI(
    title="Library Card Digitization System",
    description="A modern system for digitizing library cards using AI and OCR",
    version="1.0.0"
)

# --- Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files and Templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# --- Include Route Modules
from routes.auth import router as auth_router
from routes.cards import router as cards_router
from routes.profile import router as profile_router
from routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(cards_router)
app.include_router(profile_router)
app.include_router(admin_router)

# --- Main Page Route
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Main page route."""
    user_email = request.session.get("user")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user_email": user_email}
    )

# --- Admin Authorization
# Admin authorization moved to services/auth_service.py

# --- Routes
# Routes moved to separate modules in routes/

# --- Card Management Routes
# Card routes moved to routes/cards.py

# --- Profile Routes
# Profile routes moved to routes/profile.py

# --- Admin Routes
# Admin routes moved to routes/admin.py

# --- Database Initialization
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    """Initialize application on startup."""
    await init_db()

# --- Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Application Settings
settings = get_settings()

# --- Directory Setup
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.join(settings.data_dir, "exports"), exist_ok=True)

# --- Database Configuration
# Database setup and models are moved into models/db.py

# --- CSRF Protection
# CSRF settings moved to security.py

# --- FastAPI Application Setup
app = FastAPI(
    title="Library Card Digitization System",
    description="A modern system for digitizing library cards using AI and OCR",
    version="1.0.0"
)

# --- Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files and Templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# --- Include Route Modules
from routes.auth import router as auth_router
from routes.cards import router as cards_router
from routes.profile import router as profile_router
from routes.admin import router as admin_router

app.include_router(auth_router)
app.include_router(cards_router)
app.include_router(profile_router)
app.include_router(admin_router)

# --- Main Page Route
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Main page route."""
    user_email = request.session.get("user")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user_email": user_email}
    )

# --- Admin Authorization
# Admin authorization moved to services/auth_service.py

# --- Routes
# Routes moved to separate modules in routes/

# --- Card Management Routes
# Card routes moved to routes/cards.py

# --- Profile Routes
# Profile routes moved to routes/profile.py

# --- Admin Routes
# Admin routes moved to routes/admin.py

# --- Database Initialization
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    """Initialize application on startup."""
    await init_db()
