"""Pydantic schemas for authentication and user accounts."""

from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_minutes: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: Optional[str] = None
    status: str
    created_at: datetime
