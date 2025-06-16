"""
Library Card Digitization System - FastAPI Application
Main application file with all routes and database models.
"""

import os
import uuid
import json
import csv
from typing import Optional, List
from datetime import datetime
from io import StringIO
import base64

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel
from argon2 import PasswordHasher
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.templating import _TemplateResponse
from functools import wraps

from sqlalchemy import Column, String, Boolean, DateTime, Text, update, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.pipeline import process_card, validate_card_data
from core.ocr import recognize_text as perform_ocr
from core.yolo_detector import detect_fields
from config import get_settings
from integrations import (
    integration_manager,
    ocr_service,
    library_system,
    notification_service
)

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
ph = PasswordHasher()

# --- Directory Setup
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.join(settings.data_dir, "exports"), exist_ok=True)

# --- Database Configuration
DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# --- Database Models
class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(Text, default="{}")

class Card(Base):
    """Card model for storing library card information."""
    __tablename__ = "cards"
    id = Column(String, primary_key=True, index=True)
    image_data = Column(LargeBinary)
    image_mime = Column(String)
    image_path = Column(String)
    processed_text = Column(Text)
    original_text = Column(Text)
    fields = Column(Text)
    status = Column(String)
    validation_errors = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String)

# --- Database Helper Functions
async def get_user(email: str) -> Optional[User]:
    """Get user by email."""
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalars().first()

async def create_user(email: str, password: str, is_admin: bool = False) -> User:
    """Create new user."""
    async with SessionLocal() as session:
        user = User(email=email, password=hash_password(password), is_admin=is_admin)
        session.add(user)
        await session.commit()
        return user

async def get_all_users() -> List[User]:
    """Get all users."""
    async with SessionLocal() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

async def get_card(card_id: str) -> Optional[Card]:
    """Get card by ID."""
    async with SessionLocal() as session:
        result = await session.execute(select(Card).where(Card.id == card_id))
        return result.scalars().first()

async def create_card(**kwargs) -> Card:
    """Create new card."""
    async with SessionLocal() as session:
        card = Card(**kwargs)
        session.add(card)
        await session.commit()
        return card

async def get_cards(q: Optional[str] = None, status: Optional[str] = None, skip: int = 0, limit: int = 12) -> List[Card]:
    """Get cards with optional filtering and pagination."""
    async with SessionLocal() as session:
        query = select(Card)
        if status:
            query = query.where(Card.status == status)
        if q:
            query = query.where(Card.processed_text.ilike(f'%{q}%'))
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def update_card(card_id: str, **kwargs) -> Optional[Card]:
    """Update card by ID."""
    async with SessionLocal() as session:
        card = await get_card(card_id)
        if not card:
            return None
        for k, v in kwargs.items():
            setattr(card, k, v)
        await session.commit()
        return card

async def delete_card(card_id: str) -> None:
    """Delete card by ID."""
    async with SessionLocal() as session:
        card = await get_card(card_id)
        if card:
            await session.delete(card)
            await session.commit()

# --- Password Utilities
def verify_password(hashed_password: str, password: str) -> bool:
    """Verify password against hash."""
    try:
        ph.verify(hashed_password, password)
        return True
    except Exception:
        return False

def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return ph.hash(password)

# --- CSRF Protection
class CsrfSettings(BaseModel):
    """CSRF protection settings."""
    secret_key: str = settings.csrf_secret_key

csrf = CsrfProtect()

@csrf.load_config
def get_csrf_config():
    return CsrfSettings()

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

# --- Admin Authorization
def admin_required(func):
    """Decorator for admin-only routes."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not await is_admin(request):
            return RedirectResponse("/login", status_code=302)
        return await func(request, *args, **kwargs)
    return wrapper

async def is_admin(request: Request) -> bool:
    """Check if current user is admin."""
    user_email = request.session.get("user")
    if not user_email:
        return False
    user = await get_user(user_email)
    return user and user.is_admin

# --- Routes
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Main page route."""
    user_email = request.session.get("user")
    return templates.TemplateResponse(
        "index.html",  
        {"request": request, "user_email": user_email}
    )

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    """Signup form route."""
    return templates.TemplateResponse(
        "reader/temp_signup.html",
        {"request": request, "error": None}
    )

@app.post("/signup", response_class=HTMLResponse)
async def signup_post(request: Request, email: str = Form(...), password: str = Form(...)):
    """Handle signup form submission."""
    user = await get_user(email)
    if user:
        return templates.TemplateResponse(
            "reader/temp_signup.html",
            {"request": request, "error": "Пользователь уже существует"}
        )
    is_admin = False  # First user could be admin
    await create_user(email=email, password=password, is_admin=is_admin)
    request.session["user"] = email
    return RedirectResponse("/", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Login form route."""
    return templates.TemplateResponse(
        "reader/temp_login.html", 
        {"request": request, "error": None}
    )

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle login form submission."""
    try:
        if not email or not password:
            return templates.TemplateResponse(
                "reader/temp_login.html",
                {
                    "request": request,
                    "error": "Email и пароль обязательны",
                    "email": email
                }
            )

        user = await get_user(email)
        if not user:
            return templates.TemplateResponse(
                "reader/temp_login.html",
                {
                    "request": request,
                    "error": "Пользователь не найден",
                    "email": email
                }
            )

        if not verify_password(user.password, password):
            return templates.TemplateResponse(
                "reader/temp_login.html",
                {
                    "request": request,
                    "error": "Неверный пароль",
                    "email": email
                }
            )

        request.session["user"] = email
        return RedirectResponse("/", status_code=302)

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "reader/temp_login.html",
            {
                "request": request,
                "error": "Произошла ошибка при входе. Попробуйте позже.",
                "email": email
            }
        )

@app.get("/logout")
async def logout(request: Request):
    """Handle user logout."""
    request.session.clear()
    return RedirectResponse("/", status_code=302)

# --- Card Management Routes
@app.get("/upload", response_class=HTMLResponse)
async def reader_upload_form(request: Request):
    """Upload form route."""
    return templates.TemplateResponse(
        "reader/upload.html",
        {"request": request, "error": None}
    )

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    """Handle file upload."""
    image_data = await file.read()
    image_mime = file.content_type
    processed_text = "Распознанный текст (заглушка)"
    card_id = str(uuid.uuid4())
    await create_card(
        id=card_id,
        image_data=image_data,
        image_mime=image_mime,
        image_path=None,
        processed_text=processed_text,
        original_text=processed_text,
        fields=json.dumps({}),
        status="new",
        validation_errors=json.dumps([]),
        created_by=request.session.get("user")
    )
    user_email = request.session.get("user")
    user = await get_user(user_email) if user_email else None
    if user and user.is_admin:
        return RedirectResponse(f"/admin/cards/{card_id}/edit", status_code=302)
    return templates.TemplateResponse(
        "reader/upload_success.html",
        {"request": request, "message": "Карточка успешно добавлена в список!"}
    )

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", status: str = "", page: int = 1):
    """Search cards route."""
    skip = (page - 1) * 12
    cards = await get_cards(q=q, status=status, skip=skip, limit=12)
    for card in cards:
        card.card_image_base64 = base64.b64encode(card.image_data).decode() if card.image_data else ""
    return templates.TemplateResponse(
        "reader/search.html",
        {
            "request": request,
            "cards": cards,
            "page": page,
            "q": q,
            "status": status
        }
    )

@app.get("/cards/{card_id}", response_class=HTMLResponse)
async def reader_card_view(request: Request, card_id: str):
    """View single card route."""
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card_image_base64 = base64.b64encode(card.image_data).decode() if card.image_data else ""
    return templates.TemplateResponse(
        "reader/card.html",
        {"request": request, "card": card, "card_image_base64": card_image_base64}
    )

# --- Profile Routes
@app.get("/profile", response_class=HTMLResponse)
async def reader_profile(request: Request):
    """User profile route."""
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    
    user_email = request.session.get("user")
    async with SessionLocal() as session:
        result = await session.execute(
            select(Card).where(Card.created_by == user_email)
        )
        user_cards = result.scalars().all()
    
    stats = {
        "total_cards": len(user_cards),
        "validated_cards": len([c for c in user_cards if c.status == "validated"]),
        "pending_cards": len([c for c in user_cards if c.status == "new"])
    }
    recent_cards = sorted(user_cards, key=lambda x: x.created_at or "", reverse=True)[:5]
    
    return templates.TemplateResponse(
        "reader/profile.html",
        {
            "request": request,
            "stats": stats,
            "recent_cards": recent_cards
        }
    )

# --- Settings Routes
@app.get("/settings", response_class=HTMLResponse)
async def user_settings(request: Request):
    """User settings route."""
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "reader/settings.html",
        {"request": request}
    )

@app.post("/settings")
async def update_settings(
    request: Request,
    email: str = Form(None),
    notifications_enabled: bool = Form(False),
    theme: str = Form("light")
):
    """Update user settings."""
    if not request.session.get("user"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    user_email = request.session.get("user")
    user = await get_user(user_email)
    if user:
        user.settings = json.dumps({
            "email": email,
            "notifications_enabled": notifications_enabled,
            "theme": theme
        })
        async with SessionLocal() as session:
            session.add(user)
            await session.commit()
    return RedirectResponse("/settings", status_code=302)

# --- Admin Routes
@app.get("/admin", response_class=HTMLResponse)
@admin_required
async def admin_dashboard(request: Request):
    """Admin dashboard route."""
    async with SessionLocal() as session:
        cards = (await session.execute(select(Card))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()
    
    stats = {
        "total_cards": len(cards),
        "total_users": len(users),
        "new_cards": len([c for c in cards if c.status == "new"]),
        "validated_cards": len([c for c in cards if c.status == "validated"]),
    }
    recent_cards = sorted(cards, key=lambda x: x.created_at or "", reverse=True)[:5]
    recent_users = sorted(users, key=lambda x: x.created_at or "", reverse=True)[:5]
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_cards": recent_cards,
            "recent_users": recent_users
        }
    )

@app.get("/admin/users", response_class=HTMLResponse)
@admin_required
async def admin_users(request: Request):
    """Admin users management route."""
    users = await get_all_users()
    return templates.TemplateResponse(
        "admin/users/index.html",
        {
            "request": request,
            "users": users,
            "user_email": request.session.get("user")
        }
    )

@app.get("/admin/cards", response_class=HTMLResponse)
@admin_required
async def admin_cards(request: Request, q: str = "", status: str = "", page: int = 1):
    """Admin cards management route."""
    skip = (page - 1) * 12
    cards = await get_cards(q=q, status=status, skip=skip, limit=12)
    for card in cards:
        card.card_image_base64 = base64.b64encode(card.image_data).decode() if card.image_data else ""
    return templates.TemplateResponse(
        "admin/cards.html",
        {
            "request": request,
            "cards": cards,
            "user_email": request.session.get("user"),
            "q": q,
            "status": status,
            "page": page
        }
    )

@app.get("/admin/cards/{card_id}/edit", response_class=HTMLResponse)
@admin_required
async def admin_card_edit(request: Request, card_id: str):
    """Admin card edit form route."""
    card = await get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    fields = {}
    try:
        fields = json.loads(card.fields) if card.fields else {}
    except Exception:
        fields = {}
    return templates.TemplateResponse(
        "admin/cards/edit.html",
        {"request": request, "card": card, "fields": fields}
    )

@app.post("/admin/cards/{card_id}/edit")
@admin_required
async def admin_card_edit_post(
    request: Request,
    card_id: str,
    processed_text: str = Form(...),
    fields: str = Form(...)
):
    """Handle admin card edit form submission."""
    await update_card(
        card_id,
        processed_text=processed_text,
        fields=fields,
        status="verified",
        updated_at=datetime.now()
    )
    return RedirectResponse("/admin/cards", status_code=302)

@app.post("/admin/cards/{card_id}/delete")
@admin_required
async def admin_card_delete(request: Request, card_id: str):
    """Handle admin card deletion."""
    await delete_card(card_id)
    return RedirectResponse("/admin/cards", status_code=302)

@app.get("/admin/settings", response_class=HTMLResponse)
@admin_required
async def admin_settings(request: Request):
    """Admin settings route."""
    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "user_email": request.session.get("user"),
            "integrations": {
                "ocr": integration_manager.get_api_key('ocr'),
                "library": integration_manager.get_api_key('library'),
                "notifications": integration_manager.get_api_key('notifications')
            }
        }
    )

@app.post("/admin/settings/integrations")
@admin_required
async def update_integration_settings(request: Request):
    """Handle admin integration settings update."""
    form_data = await request.form()
    for service in ['ocr', 'library', 'notifications']:
        api_key = form_data.get(f"{service}_api_key")
        if api_key:
            integration_manager.set_api_key(service, api_key)
    return RedirectResponse("/admin/settings", status_code=302)

@app.get("/admin/logs", response_class=HTMLResponse)
@admin_required
async def admin_logs(request: Request, page: int = 1):
    """Admin logs view route."""
    logs = []
    try:
        with open("logs/app.log", "r") as f:
            logs = f.readlines()
    except FileNotFoundError:
        pass
    
    page_size = 50
    total_logs = len(logs)
    total_pages = (total_logs + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_logs = logs[start_idx:end_idx]
    
    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "logs": paginated_logs,
            "page": page,
            "total_pages": total_pages,
            "has_next": page < total_pages
        }
    )

@app.get("/admin/export", response_class=HTMLResponse)
@admin_required
async def admin_export(request: Request):
    """Admin export form route."""
    return templates.TemplateResponse(
        "admin/export.html",
        {"request": request}
    )

@app.post("/admin/export/cards")
@admin_required
async def admin_export_cards(
    request: Request,
    format: str = Form(...),
    date_from: str = Form(None),
    date_to: str = Form(None),
    status: str = Form(None)
):
    """Handle admin card export."""
    async with SessionLocal() as session:
        query = select(Card)
        if date_from:
            query = query.where(Card.created_at >= date_from)
        if date_to:
            query = query.where(Card.created_at <= date_to)
        if status:
            query = query.where(Card.status == status)
        result = await session.execute(query)
        cards = result.scalars().all()

    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Text", "Status", "Created At", "Created By"])
        for card in cards:
            writer.writerow([
                card.id,
                card.processed_text,
                card.status,
                card.created_at.isoformat() if card.created_at else None,
                card.created_by
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=cards.csv"}
        )
    elif format == "json":
        return Response(
            content=json.dumps([
                {
                    "id": card.id,
                    "processed_text": card.processed_text,
                    "status": card.status,
                    "created_at": card.created_at.isoformat() if card.created_at else None,
                    "created_by": card.created_by
                } for card in cards
            ], ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=cards.json"}
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

# --- Database Initialization
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    """Initialize application on startup."""
    await init_db()
