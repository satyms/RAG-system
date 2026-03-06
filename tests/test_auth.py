"""Tests for Phase 3: Authentication (API key + JWT)."""

from __future__ import annotations

import pytest
from unittest.mock import patch


class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    @patch("app.config.settings.JWT_SECRET_KEY", "test-secret-key-123")
    @patch("app.config.settings.JWT_ALGORITHM", "HS256")
    @patch("app.config.settings.JWT_EXPIRY_MINUTES", 60)
    def test_create_and_decode_token(self):
        from app.middleware.auth import create_jwt_token, decode_jwt_token

        token = create_jwt_token({"sub": "test_user", "scope": "full"})
        assert isinstance(token, str)
        assert len(token) > 0

        payload = decode_jwt_token(token)
        assert payload["sub"] == "test_user"
        assert payload["scope"] == "full"
        assert "exp" in payload

    @patch("app.config.settings.JWT_SECRET_KEY", "test-secret-key-123")
    @patch("app.config.settings.JWT_ALGORITHM", "HS256")
    def test_invalid_token_raises(self):
        from fastapi import HTTPException
        from app.middleware.auth import decode_jwt_token

        with pytest.raises(HTTPException) as exc_info:
            decode_jwt_token("invalid.token.here")
        assert exc_info.value.status_code == 401


class TestAPIKeyVerification:
    """Tests for API key verification."""

    @pytest.mark.asyncio
    @patch("app.config.settings.API_KEY", "")
    async def test_no_api_key_configured_passes(self):
        from app.middleware.auth import verify_api_key
        result = await verify_api_key(api_key=None)
        assert result is None  # Open access

    @pytest.mark.asyncio
    @patch("app.config.settings.API_KEY", "my-secret-key")
    async def test_valid_api_key_passes(self):
        from app.middleware.auth import verify_api_key
        result = await verify_api_key(api_key="my-secret-key")
        assert result == "my-secret-key"

    @pytest.mark.asyncio
    @patch("app.config.settings.API_KEY", "my-secret-key")
    async def test_invalid_api_key_rejected(self):
        from fastapi import HTTPException
        from app.middleware.auth import verify_api_key

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="wrong-key")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("app.config.settings.API_KEY", "my-secret-key")
    async def test_missing_api_key_rejected(self):
        from fastapi import HTTPException
        from app.middleware.auth import verify_api_key

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key=None)
        assert exc_info.value.status_code == 401
