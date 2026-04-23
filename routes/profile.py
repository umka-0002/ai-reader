import json
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select

from services import get_user, get_cards_by_user, update_user
from models.db import SessionLocal, Card
from config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter()

@router.get("/profile", response_class=HTMLResponse)
async def reader_profile(request: Request):
    """User profile route."""
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)

    user_email = request.session.get("user")
    user_cards = await get_cards_by_user(user_email)

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

@router.get("/settings", response_class=HTMLResponse)
async def user_settings(request: Request):
    """User settings route."""
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "reader/settings.html",
        {"request": request}
    )

@router.post("/settings")
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
    await update_user(
        user_email,
        settings=json.dumps({
            "email": email,
            "notifications_enabled": notifications_enabled,
            "theme": theme
        })
    )
    return RedirectResponse("/settings", status_code=302)