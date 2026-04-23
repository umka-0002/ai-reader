from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services import get_user, create_user, verify_password
from config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory="frontend/templates")

router = APIRouter()

@router.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    """Signup form route."""
    return templates.TemplateResponse(
        "reader/temp_signup.html",
        {"request": request, "error": None}
    )

@router.post("/signup", response_class=HTMLResponse)
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

@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Login form route."""
    return templates.TemplateResponse(
        "reader/temp_login.html",
        {"request": request, "error": None}
    )

@router.post("/login", response_class=HTMLResponse)
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
        from main import logger
        logger.error(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "reader/temp_login.html",
            {
                "request": request,
                "error": "Произошла ошибка при входе. Попробуйте позже.",
                "email": email
            }
        )

@router.get("/logout")
async def logout(request: Request):
    """Handle user logout."""
    request.session.clear()
    return RedirectResponse("/", status_code=302)