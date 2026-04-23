from functools import wraps
from fastapi import Request
from fastapi.responses import RedirectResponse

from services import get_user

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