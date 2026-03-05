"""Authentication — API key & JWT token validation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

logger = logging.getLogger(__name__)

# ── API Key scheme ───────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ── JWT Bearer scheme ────────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


# ── JWT helpers ──────────────────────────────────────────────

def create_jwt_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    from jose import jwt

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRY_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    from jose import jwt, JWTError

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


# ── FastAPI dependencies ─────────────────────────────────────

async def verify_api_key(api_key: Optional[str] = Security(_api_key_header)) -> Optional[str]:
    """
    Validate the X-API-Key header.

    If API_KEY is not configured (empty), authentication is bypassed for ease of development.
    """
    if not settings.API_KEY:
        # No API key configured — open access
        return None

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Provide X-API-Key header.")

    if api_key != settings.API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key.")

    return api_key


async def verify_jwt(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> Optional[dict]:
    """
    Validate JWT Bearer token.

    If JWT_SECRET_KEY is the default placeholder, authentication is bypassed.
    """
    if settings.JWT_SECRET_KEY == "change-me-in-production":
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Bearer token.")

    return decode_jwt_token(credentials.credentials)


async def require_auth(
    request: Request,
    api_key: Optional[str] = Security(_api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> Optional[dict]:
    """
    Flexible auth dependency — accepts EITHER API key OR JWT.

    If neither security mechanism is configured, access is open.
    """
    # If no security configured, pass through
    if not settings.API_KEY and settings.JWT_SECRET_KEY == "change-me-in-production":
        return None

    # Try API key first
    if settings.API_KEY and api_key:
        if api_key == settings.API_KEY:
            return {"auth": "api_key"}
        raise HTTPException(status_code=403, detail="Invalid API key.")

    # Try JWT
    if settings.JWT_SECRET_KEY != "change-me-in-production" and credentials:
        payload = decode_jwt_token(credentials.credentials)
        return {"auth": "jwt", **payload}

    raise HTTPException(status_code=401, detail="Authentication required. Provide X-API-Key or Bearer token.")
