"""
Request/response contracts for the auth endpoints. Kept separate from
app/db/models.py deliberately: models.py describes the Postgres TABLE
(includes hashed_password), these describe the HTTP API (never includes
hashed_password in a response) - conflating the two is a classic way to
accidentally leak a password hash in an API response.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
