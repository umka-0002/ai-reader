from typing import Optional, List
from sqlalchemy.future import select

from models.db import Card, SessionLocal

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
        for key, value in kwargs.items():
            setattr(card, key, value)
        await session.commit()
        return card

async def delete_card(card_id: str) -> None:
    """Delete card by ID."""
    async with SessionLocal() as session:
        card = await get_card(card_id)
        if card:
            await session.delete(card)
            await session.commit()

async def get_all_cards() -> List[Card]:
    """Get all cards."""
    async with SessionLocal() as session:
        result = await session.execute(select(Card))
        return result.scalars().all()

async def get_cards_by_user(user_email: str) -> List[Card]:
    """Get cards created by a specific user."""
    async with SessionLocal() as session:
        result = await session.execute(select(Card).where(Card.created_by == user_email))
        return result.scalars().all()

async def get_cards_with_filters(date_from: Optional[str] = None, date_to: Optional[str] = None, status: Optional[str] = None) -> List[Card]:
    """Get cards with optional date and status filters."""
    async with SessionLocal() as session:
        query = select(Card)
        if date_from:
            query = query.where(Card.created_at >= date_from)
        if date_to:
            query = query.where(Card.created_at <= date_to)
        if status:
            query = query.where(Card.status == status)
        result = await session.execute(query)
        return result.scalars().all()
