from typing import Optional, List
from sqlalchemy.future import select

from models.db import User, SessionLocal
from core.auth_utils import hash_password

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

async def update_user(email: str, **kwargs) -> Optional[User]:
    """Update user by email."""
    async with SessionLocal() as session:
        user = await get_user(email)
        if not user:
            return None
        for key, value in kwargs.items():
            setattr(user, key, value)
        await session.commit()
        return user
