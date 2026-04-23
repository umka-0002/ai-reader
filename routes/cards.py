import uuid
import json
import base64
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services import get_user, create_card, get_cards, get_card
from config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter()

@router.get("/upload", response_class=HTMLResponse)
async def reader_upload_form(request: Request):
    """Upload form route."""
    return templates.TemplateResponse(
        "reader/upload.html",
        {"request": request, "error": None}
    )

@router.post("/upload", response_class=HTMLResponse)
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

@router.get("/search", response_class=HTMLResponse)
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

@router.get("/cards/{card_id}", response_class=HTMLResponse)
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