import os
import shutil
import uuid
import json
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware

# === Интеграция с pipeline ===
from core.pipeline import process_card

CARDS_FILE = "data/cards.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(CARDS_FILE):
    with open(CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

def load_cards():
    with open(CARDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cards(cards):
    with open(CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

def get_card(card_id):
    cards = load_cards()
    for card in cards:
        if card["id"] == card_id:
            return card
    return None

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="YOUR_SECRET_KEY")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

UPLOAD_DIR = "frontend/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def admin_required(request: Request):
    if request.session.get("admin") != True:
        return RedirectResponse("/admin/login", status_code=302)

# ---------------------- ADMIN ----------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    return templates.TemplateResponse("admin/login/index.html", {"request": request, "error": None})

@app.post("/admin/login", response_class=HTMLResponse)
def admin_login_post(request: Request, password: str = Form(...)):
    if password == "admin123":
        request.session["admin"] = True
        return RedirectResponse("/admin/cards", status_code=302)
    return templates.TemplateResponse("admin/login/index.html", {"request": request, "error": "Неверный пароль"})

@app.get("/admin/cards", response_class=HTMLResponse)
def admin_cards(request: Request, filter: str = "", q: str = ""):
    admin_required(request)
    cards = load_cards()
    if filter:
        cards = [c for c in cards if c.get("status") == filter]
    if q:
        cards = [c for c in cards if q.lower() in c.get("text", "").lower()]
    return templates.TemplateResponse("admin/cards/export/index.html", {"request": request, "cards": cards, "filter": filter, "q": q})

@app.get("/admin/cards/{card_id}/edit", response_class=HTMLResponse)
def admin_card_edit(request: Request, card_id: str):
    admin_required(request)
    card = get_card(card_id)
    if not card:
        return Response("Card not found", status_code=404)
    return templates.TemplateResponse("admin/cards/export/edit.html", {"request": request, "card": card})

@app.post("/admin/cards/{card_id}/edit")
def admin_card_edit_post(request: Request, card_id: str, text: str = Form(...)):
    admin_required(request)
    cards = load_cards()
    for c in cards:
        if c["id"] == card_id:
            c["text"] = text
            c["status"] = "checked"
    save_cards(cards)
    return RedirectResponse("/admin/cards", status_code=302)

@app.post("/admin/cards/{card_id}/delete")
def admin_card_delete(request: Request, card_id: str):
    admin_required(request)
    cards = load_cards()
    cards = [c for c in cards if c["id"] != card_id]
    save_cards(cards)
    return RedirectResponse("/admin/cards", status_code=302)

@app.get("/admin/cards/export")
def admin_export_cards(request: Request, fmt: str = "json"):
    admin_required(request)
    cards = load_cards()
    if fmt == "json":
        return FileResponse(CARDS_FILE, media_type="application/json", filename="cards.json")
    return Response("Экспорт других форматов в разработке", status_code=501)

@app.get("/admin/debug/{card_id}", response_class=HTMLResponse)
def admin_debug_card(request: Request, card_id: str):
    admin_required(request)
    card = get_card(card_id)
    if not card:
        return Response("Card not found", status_code=404)
    return templates.TemplateResponse("admin/debug/index.html", {"request": request, "card": card})

# ---------------------- READER ----------------------

@app.get("/", response_class=HTMLResponse)
def reader_index(request: Request):
    return templates.TemplateResponse("reader/index.html", {"request": request, "result": None, "filename": None})

@app.post("/upload", response_class=HTMLResponse)
def reader_upload(request: Request, file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    fname = f"{file_id}_{file.filename}"
    file_location = os.path.join(UPLOAD_DIR, fname)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # === Интеграция с pipeline ===
    try:
        result_text = process_card(file_location)
    except Exception as e:
        result_text = f"Ошибка обработки: {e}"
    card = {
        "id": file_id,
        "image_path": f"/static/uploads/{fname}",
        "text": result_text,
        "status": "new"
    }
    cards = load_cards()
    cards.append(card)
    save_cards(cards)
    history = request.cookies.get("history", "")
    history_list = history.split(",") if history else []
    history_list.append(file_id)
    resp = templates.TemplateResponse("reader/index.html", {"request": request, "result": card["text"], "filename": fname, "card_id": file_id})
    resp.set_cookie("history", ",".join(history_list[-10:]))
    return resp

@app.get("/search", response_class=HTMLResponse)
def reader_search(request: Request, q: str = ""):
    cards = load_cards()
    if q:
        cards = [c for c in cards if q.lower() in c.get("text", "").lower()]
    return templates.TemplateResponse("reader/search/index.html", {"request": request, "cards": cards, "q": q})

@app.get("/cards/{card_id}", response_class=HTMLResponse)
def reader_card_view(request: Request, card_id: str):
    card = get_card(card_id)
    if not card:
        return Response("Card not found", status_code=404)
    return templates.TemplateResponse("reader/cards/index.html", {"request": request, "card": card})

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