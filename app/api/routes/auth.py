"""Authentication endpoints — generate JWT tokens."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.middleware.auth import create_jwt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Auth"])


class TokenRequest(BaseModel):
    """Simple API key exchange for JWT."""
    api_key: str = Field(..., description="Valid API key to exchange for JWT")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = 60


@router.post("/auth/token", response_model=TokenResponse)
async def get_token(payload: TokenRequest):
    """Exchange a valid API key for a JWT access token."""
    if not settings.API_KEY:
        raise HTTPException(status_code=400, detail="API key auth not configured.")

    if payload.api_key != settings.API_KEY:
        logger.warning("Invalid API key in token exchange attempt")
        raise HTTPException(status_code=403, detail="Invalid API key.")

    token = create_jwt_token({"sub": "api_user", "scope": "full_access"})
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.JWT_EXPIRY_MINUTES,
    )
