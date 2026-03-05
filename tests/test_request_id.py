"""Tests for Phase 3: Request-ID middleware."""

from __future__ import annotations

import pytest

from app.middleware.request_id import request_id_ctx


class TestRequestIDContext:
    """Test the request ID context variable."""

    def test_default_value_is_empty(self):
        assert request_id_ctx.get("") == ""

    def test_set_and_get(self):
        token = request_id_ctx.set("test-id-123")
        assert request_id_ctx.get("") == "test-id-123"
        request_id_ctx.reset(token)

    def test_reset_clears(self):
        token = request_id_ctx.set("test-id-456")
        request_id_ctx.reset(token)
        assert request_id_ctx.get("") == ""
