from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserInDB(UserBase):
    id: UUID = Field(default_factory=uuid4)
    hashed_password: str
    is_approved: bool = False
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class User(UserBase):
    id: UUID
    is_approved: bool
    is_admin: bool
    created_at: datetime

class CardBase(BaseModel):
    text: str

class CardCreate(CardBase):
    pass

class CardInDB(CardBase):
    id: UUID = Field(default_factory=uuid4)
    image_path: str
    status: str = "new"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[UUID] = None

class Card(CardBase):
    id: UUID
    image_path: str
    status: str
    created_at: datetime
    user_id: Optional[UUID]

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None 