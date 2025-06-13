import os
import shutil
import uuid
import json
from typing import Optional, List
from fastapi import FastAPI, Request, Form, UploadFile, File, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel, EmailStr
from argon2 import PasswordHasher
import secrets
import logging
from datetime import datetime
import csv
from io import StringIO
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.templating import _TemplateResponse
from functools import wraps

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Initialize Argon2 password hasher
ph = PasswordHasher()

# --- Путь к файлам
CARDS_FILE = os.path.join(settings.data_dir, "cards.json")
USERS_FILE = os.path.join(settings.data_dir, "users.json")
UPLOAD_DIR = settings.upload_dir
EXPORT_DIR = os.path.join(settings.data_dir, "exports")

# Create required directories
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# --- Cards utils
def load_cards():
    try:
        if not os.path.exists(CARDS_FILE):
            return []
        with open(CARDS_FILE, "r", encoding="utf-8") as f:
            cards = json.load(f)
            # Ensure all cards have required fields
            for card in cards:
                if "processed_text" not in card:
                    card["processed_text"] = card.get("text", "")
                if "original_text" not in card:
                    card["original_text"] = card.get("text", "")
                if "fields" not in card:
                    card["fields"] = {}
                if "status" not in card:
                    card["status"] = "new"
                if "validation_errors" not in card:
                    card["validation_errors"] = []
                if "created_at" not in card:
                    card["created_at"] = datetime.now().isoformat()
                if "updated_at" not in card:
                    card["updated_at"] = datetime.now().isoformat()
            return cards
    except json.JSONDecodeError:
        return []

def save_cards(cards):
    with open(CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

def get_card(card_id):
    cards = load_cards()
    return next((card for card in cards if card["id"] == card_id), None)

# --- Users utils
def load_users():
    try:
        if not os.path.exists(USERS_FILE):
            return []
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(email):
    users = load_users()
    return next((u for u in users if u["email"] == email), None)

def get_user_by_id(user_id):
    users = load_users()
    return next((u for u in users if u["id"] == user_id), None)

def verify_password(hashed_password: str, password: str) -> bool:
    try:
        ph.verify(hashed_password, password)
        return True
    except Exception:
        return False

def hash_password(password: str) -> str:
    return ph.hash(password)

# --- CSRF protect config
class CsrfSettings(BaseModel):
    secret_key: str = settings.csrf_secret_key

csrf = CsrfProtect()

@csrf.load_config
def get_csrf_config():
    return CsrfSettings()

# --- FastAPI setup
app = FastAPI(title="Library Card Digitization System")

# Define get_unread_notifications
def get_unread_notifications(request):
    if not request.session.get("user"):
        return 0
    try:
        with open(f"data/notifications/{request.session.get('user')}.json", "r") as f:
            notifications = json.load(f)
            return len([n for n in notifications if not n.get("read", False)])
    except FileNotFoundError:
        return 0

# Define NotificationCountMiddleware
class NotificationCountMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if isinstance(response, _TemplateResponse):
            unread = get_unread_notifications(request)
            response.context["unread_notifications"] = unread
        return response

# NOW add the middleware
app.add_middleware(NotificationCountMiddleware)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

templates = Jinja2Templates(directory="frontend/templates")

# --- Admin check
def admin_required(func):
    @wraps(func)
    def wrapper(request: Request, *args, **kwargs):
        user = get_user(request.session.get("user"))
        if not user or not user.get("is_admin"):
            return RedirectResponse("/login", status_code=302)
        return func(request, *args, **kwargs)
    return wrapper

@app.get("/", response_class=HTMLResponse)
def main_page(request: Request):
    user_email = request.session.get("user")
    return templates.TemplateResponse(
        "index.html",  
        {"request": request, "user_email": user_email}
    )

@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse(
        "reader/temp_signup.html",
        {"request": request, "error": None}
    )

@app.post("/signup", response_class=HTMLResponse)
async def signup_post(request: Request, email: str = Form(...), password: str = Form(...)):
    users = load_users()
    if get_user(email):
        return templates.TemplateResponse(
            "reader/temp_signup.html",
            {"request": request, "error": "Пользователь уже существует"}
        )
    is_admin = len(users) == 0
    user = User(
        email=email,
        password=hash_password(password),
        is_admin=is_admin,
        created_at=datetime.now().isoformat()
    ).dict()
    users.append(user)
    save_users(users)
    request.session["user"] = email
    return RedirectResponse("/", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        "reader/temp_login.html", 
        {"request": request, "error": None, "filename": None}
    )

@app.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        user = get_user(email)
        if user and verify_password(user["password"], password):
            request.session["user"] = email
            # Check if user is admin
            if user.get("is_admin"):
                request.session["admin"] = True
            
            return RedirectResponse("/", status_code=302)
        
        # Login failed
        return templates.TemplateResponse(
            "reader/temp_login.html", 
            {"request": request, "error": "Неверный логин или пароль"}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "reader/temp_login.html", 
            {"request": request, "error": f"Ошибка при входе: {str(e)}"}
        )

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

# ---------------------- ADMIN: USERS ----------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    return templates.TemplateResponse(
        "admin/login/index.html",
        {"request": request, "error": None}
    )

@app.post("/admin/login", response_class=HTMLResponse)
def admin_login_post(request: Request, password: str = Form(...)):
    if password == "admin123":
        request.session["admin"] = True
        return RedirectResponse("/admin/cards", status_code=302)
    return templates.TemplateResponse(
        "admin/login/index.html",
        {"request": request, "error": "Неверный пароль"}
    )

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    users = load_users()
    return templates.TemplateResponse(
        "admin/users/index.html",
        {"request": request, "users": users}
    )

@app.post("/admin/users/{user_id}/approve")
def admin_approve_user(request: Request, user_id: str):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    users = load_users()
    for u in users:
        if u["id"] == user_id:
            u["is_approved"] = True
    save_users(users)
    return RedirectResponse("/admin/users", status_code=302)

# ---------------------- ADMIN: CARDS ----------------------

@app.get("/admin/cards", response_class=HTMLResponse)
def admin_cards(request: Request, filter: str = "", q: str = ""):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    cards = load_cards()
    if filter:
        cards = [c for c in cards if c.get("status") == filter]
    if q:
        cards = [c for c in cards if q.lower() in c.get("processed_text", "").lower()]
    
    return templates.TemplateResponse(
        "admin/cards/index.html",
        {"request": request, "cards": cards, "filter": filter, "q": q}
    )

@app.get("/admin/cards/{card_id}/edit", response_class=HTMLResponse)
def admin_card_edit(request: Request, card_id: str):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    return templates.TemplateResponse(
        "admin/cards/edit.html",
        {"request": request, "card": card}
    )

@app.post("/admin/cards/{card_id}/edit")
def admin_card_edit_post(
    request: Request,
    card_id: str,
    processed_text: str = Form(...),
    fields: str = Form(...)
):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    cards = load_cards()
    for card in cards:
        if card["id"] == card_id:
            card["processed_text"] = processed_text
            card["fields"] = json.loads(fields)
            card["status"] = "verified"
            card["verified_by"] = request.session.get("admin")
            card["updated_at"] = datetime.now().isoformat()
    
    save_cards(cards)
    return RedirectResponse("/admin/cards", status_code=302)

@app.post("/admin/cards/{card_id}/delete")
def admin_card_delete(request: Request, card_id: str):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    cards = load_cards()
    cards = [c for c in cards if c["id"] != card_id]
    save_cards(cards)
    return RedirectResponse("/admin/cards", status_code=302)

@app.get("/admin/cards/export")
def admin_export_cards(request: Request, fmt: str = "json"):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    cards = load_cards()
    if fmt == "json":
        export_path = os.path.join(EXPORT_DIR, f"cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
        return FileResponse(export_path, media_type="application/json")
    elif fmt == "irbis":
        # TODO: Implement IRBIS format export
        raise HTTPException(status_code=501, detail="IRBIS export not implemented yet")
    
    raise HTTPException(status_code=400, detail="Unsupported export format")

@app.get("/admin/debug/{card_id}", response_class=HTMLResponse)
def admin_debug_card(request: Request, card_id: str):
    admin_required(request)
    card = get_card(card_id)
    if not card:
        return Response("Card not found", status_code=404)
    return templates.TemplateResponse("admin/debug/index.html", {"request": request, "card": card})

# ---------------------- READER ----------------------

@app.get("/upload", response_class=HTMLResponse)
def reader_upload_form(request: Request):
    return templates.TemplateResponse(
        "reader/upload.html",
        {"request": request, "error": None}
    )

@app.post("/upload", response_class=HTMLResponse)
async def reader_upload(request: Request, file: UploadFile = File(...)):
    try:
        # Create unique filename
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save uploaded file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Process card
        processed_text = process_card(file_path)
        
        # Create card data
        card = {
            "id": str(uuid.uuid4()),
            "image_path": file_path,
            "processed_text": processed_text,
            "original_text": processed_text,  # Initially same as processed
            "fields": {},  # Will be populated by AI
            "status": "new",
            "validation_errors": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": request.session.get("user", "anonymous")
        }
        
        # Save card
        cards = load_cards()
        cards.append(card)
        save_cards(cards)
        
        return RedirectResponse("/search", status_code=302)
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return templates.TemplateResponse(
            "reader/upload.html",
            {"request": request, "error": f"Ошибка при обработке файла: {str(e)}"}
        )

@app.get("/search", response_class=HTMLResponse)
def reader_search(
    request: Request,
    q: str = "",
    status: str = "",
    date_from: str = "",
    date_to: str = "",
    sort: str = "newest",
    page: int = 1
):
    cards = load_cards()
    
    # Apply filters
    if q:
        cards = [c for c in cards if q.lower() in c.get("processed_text", "").lower()]
    if status:
        cards = [c for c in cards if c.get("status") == status]
    if date_from:
        cards = [c for c in cards if c.get("created_at", "") >= date_from]
    if date_to:
        cards = [c for c in cards if c.get("created_at", "") <= date_to]
    
    # Sort cards
    if sort == "newest":
        cards.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    else:
        cards.sort(key=lambda x: x.get("created_at", ""))
    
    # Pagination
    page_size = 12
    total_cards = len(cards)
    total_pages = (total_cards + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_cards = cards[start_idx:end_idx]
    
    return templates.TemplateResponse(
        "reader/search.html",
        {
            "request": request,
            "cards": paginated_cards,
            "page": page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "q": q,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
            "sort": sort
        }
    )

@app.get("/cards/{card_id}", response_class=HTMLResponse)
def reader_card_view(request: Request, card_id: str):
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return templates.TemplateResponse(
        "reader/card.html",
        {"request": request, "card": card}
    )

@app.get("/history", response_class=HTMLResponse)
def reader_history(request: Request, history: Optional[str] = Cookie(None)):
    cards = load_cards()
    history_list = history.split(",") if history else []
    user_cards = [c for c in cards if c["id"] in history_list]
    return templates.TemplateResponse("reader/history/index.html", {"request": request, "cards": user_cards})

@app.get("/download/{card_id}")
def reader_download_card(card_id: str):
    card = get_card(card_id)
    if not card:
        return Response("Card not found", status_code=404)
    out_path = f"data/{card_id}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(card.get("text", ""))
    return FileResponse(out_path, media_type="text/plain", filename=f"card_{card_id}.txt")

# Admin routes
@app.get("/admin/cards", response_class=HTMLResponse)
async def admin_cards(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
    cards = load_cards()
    return templates.TemplateResponse(
        "admin/cards.html",
        {
            "request": request,
            "cards": cards,
            "user_email": request.session.get("user")
        }
    )

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
    users = load_users()
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "users": users,
            "user_email": request.session.get("user")
        }
    )

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
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
async def update_integration_settings(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
    form_data = await request.form()
    
    # Update API keys
    for service in ['ocr', 'library', 'notifications']:
        api_key = form_data.get(f"{service}_api_key")
        if api_key:
            integration_manager.set_api_key(service, api_key)
    
    return RedirectResponse("/admin/settings", status_code=302)

@app.post("/admin/cards/{card_id}/export")
async def export_card(request: Request, card_id: str):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
    cards = load_cards()
    card = next((c for c in cards if c["id"] == card_id), None)
    
    if not card:
        return RedirectResponse("/admin/cards", status_code=302)
    
    try:
        # Export to library system
        success = library_system.export_card(card)
        
        if success:
            # Send notification
            notification_service.send_notification(
                request.session.get("user"),
                "Card Exported",
                f"Card {card_id} has been successfully exported to the library system."
            )
            
            return RedirectResponse("/admin/cards", status_code=302)
        else:
            return templates.TemplateResponse(
                "admin/cards.html",
                {
                    "request": request,
                    "cards": cards,
                    "user_email": request.session.get("user"),
                    "error": "Failed to export card to library system"
                }
            )
    except Exception as e:
        logger.error(f"Error exporting card: {e}")
        return templates.TemplateResponse(
            "admin/cards.html",
            {
                "request": request,
                "cards": cards,
                "user_email": request.session.get("user"),
                "error": f"Error exporting card: {str(e)}"
            }
        )

@app.post("/admin/cards/export-batch")
async def export_cards_batch(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login", status_code=302)
    
    form_data = await request.form()
    card_ids = form_data.getlist("card_ids")
    
    cards = load_cards()
    selected_cards = [c for c in cards if c["id"] in card_ids]
    
    success_count = 0
    failed_count = 0
    
    for card in selected_cards:
        try:
            if library_system.export_card(card):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Error exporting card {card['id']}: {e}")
            failed_count += 1
    
    # Send notification about batch export
    notification_service.send_notification(
        request.session.get("user"),
        "Batch Export Complete",
        f"Successfully exported {success_count} cards. Failed to export {failed_count} cards."
    )
    
    return RedirectResponse("/admin/cards", status_code=302)

# Helper functions
def is_admin(request: Request) -> bool:
    user_email = request.session.get("user")
    if not user_email:
        return False
    
    users = load_users()
    user = next((u for u in users if u["email"] == user_email), None)
    return user and user.get("is_admin", False)

@app.get("/profile", response_class=HTMLResponse)
def reader_profile(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    
    # Get user's cards
    cards = load_cards()
    user_cards = [c for c in cards if c.get("created_by") == request.session.get("user")]
    
    # Calculate stats
    stats = {
        "total_cards": len(user_cards),
        "validated_cards": len([c for c in user_cards if c.get("status") == "validated"]),
        "pending_cards": len([c for c in user_cards if c.get("status") == "new"])
    }
    
    # Get recent cards
    recent_cards = sorted(user_cards, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    
    return templates.TemplateResponse(
        "reader/profile.html",
        {
            "request": request,
            "stats": stats,
            "recent_cards": recent_cards
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    # Get system stats
    cards = load_cards()
    users = load_users()
    
    stats = {
        "total_cards": len(cards),
        "total_users": len(users),
        "new_cards": len([c for c in cards if c.get("status") == "new"]),
        "validated_cards": len([c for c in cards if c.get("status") == "validated"]),
        "pending_users": len([u for u in users if not u.get("is_approved")])
    }
    
    # Get recent cards and users
    recent_cards = sorted(cards, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    recent_users = sorted(users, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_cards": recent_cards,
            "recent_users": recent_users
        }
    )

@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs(request: Request, page: int = 1):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    # Load logs from file
    logs = []
    try:
        with open("logs/app.log", "r") as f:
            logs = f.readlines()
    except FileNotFoundError:
        pass
    
    # Paginate logs
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
def admin_export(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=302)
    
    return templates.TemplateResponse(
        "admin/export.html",
        {"request": request}
    )

@app.post("/admin/export/cards")
async def admin_export_cards(
    request: Request,
    format: str = Form(...),
    date_from: str = Form(None),
    date_to: str = Form(None),
    status: str = Form(None)
):
    if not request.session.get("admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cards = load_cards()
    
    # Apply filters
    if date_from:
        cards = [c for c in cards if c.get("created_at", "") >= date_from]
    if date_to:
        cards = [c for c in cards if c.get("created_at", "") <= date_to]
    if status:
        cards = [c for c in cards if c.get("status") == status]
    
    # Export based on format
    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Text", "Status", "Created At", "Created By"])
        for card in cards:
            writer.writerow([
                card["id"],
                card["processed_text"],
                card["status"],
                card["created_at"],
                card["created_by"]
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=cards.csv"}
        )
    elif format == "json":
        return Response(
            content=json.dumps(cards, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=cards.json"}
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

@app.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    
    # Get user's notifications
    notifications = []
    try:
        with open(f"data/notifications/{request.session.get('user')}.json", "r") as f:
            notifications = json.load(f)
    except FileNotFoundError:
        pass
    
    # Mark notifications as read
    for notification in notifications:
        notification["read"] = True
    
    # Save updated notifications
    os.makedirs("data/notifications", exist_ok=True)
    with open(f"data/notifications/{request.session.get('user')}.json", "w") as f:
        json.dump(notifications, f, ensure_ascii=False, indent=2)
    
    return templates.TemplateResponse(
        "reader/notifications.html",
        {
            "request": request,
            "notifications": notifications
        }
    )

@app.get("/settings", response_class=HTMLResponse)
def user_settings(request: Request):
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
    if not request.session.get("user"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update user settings
    users = load_users()
    for user in users:
        if user["email"] == request.session.get("user"):
            user["settings"] = {
                "email": email,
                "notifications_enabled": notifications_enabled,
                "theme": theme
            }
            break
    
    save_users(users)
    return RedirectResponse("/settings", status_code=302)

class User(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False
    created_at: str
    settings: dict = {}

class Card(BaseModel):
    id: str
    image_path: str
    processed_text: str
    original_text: str
    fields: dict
    status: str
    validation_errors: list
    created_at: str
    updated_at: str
    created_by: str
