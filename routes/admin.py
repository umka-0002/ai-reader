import json
import csv
import base64
from io import StringIO
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select

from services import admin_required, get_all_users, get_cards, get_card, update_card, delete_card, get_all_cards, get_cards_with_filters
from models.db import SessionLocal, Card, User
from integrations import integration_manager
from config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter()

@router.get("/admin", response_class=HTMLResponse)
@admin_required
async def admin_dashboard(request: Request):
    """Admin dashboard route."""
    cards = await get_all_cards()
    users = await get_all_users()

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

@router.get("/admin/users", response_class=HTMLResponse)
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

@router.get("/admin/cards", response_class=HTMLResponse)
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

@router.get("/admin/cards/{card_id}/edit", response_class=HTMLResponse)
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

@router.post("/admin/cards/{card_id}/edit")
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

@router.post("/admin/cards/{card_id}/delete")
@admin_required
async def admin_card_delete(request: Request, card_id: str):
    """Handle admin card deletion."""
    await delete_card(card_id)
    return RedirectResponse("/admin/cards", status_code=302)

@router.get("/admin/settings", response_class=HTMLResponse)
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

@router.post("/admin/settings/integrations")
@admin_required
async def update_integration_settings(request: Request):
    """Handle admin integration settings update."""
    form_data = await request.form()
    for service in ['ocr', 'library', 'notifications']:
        api_key = form_data.get(f"{service}_api_key")
        if api_key:
            integration_manager.set_api_key(service, api_key)
    return RedirectResponse("/admin/settings", status_code=302)

@router.get("/admin/logs", response_class=HTMLResponse)
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

@router.get("/admin/export", response_class=HTMLResponse)
@admin_required
async def admin_export(request: Request):
    """Admin export form route."""
    return templates.TemplateResponse(
        "admin/export.html",
        {"request": request}
    )

@router.post("/admin/export/cards")
@admin_required
async def admin_export_cards(
    request: Request,
    format: str = Form(...),
    date_from: str = Form(None),
    date_to: str = Form(None),
    status: str = Form(None)
):
    """Handle admin card export."""
    cards = await get_cards_with_filters(date_from=date_from, date_to=date_to, status=status)

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