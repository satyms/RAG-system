"""Unit tests for helper utilities."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.utils.helpers import file_hash, sanitize_filename


class TestFileHash:
    def test_consistent_hash(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            f.flush()
            path = Path(f.name)

        h1 = file_hash(path)
        h2 = file_hash(path)
        assert h1 == h2
        path.unlink()

    def test_different_content_different_hash(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f1:
            f1.write(b"aaa")
            f1.flush()
            p1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f2:
            f2.write(b"bbb")
            f2.flush()
            p2 = Path(f2.name)

        assert file_hash(p1) != file_hash(p2)
        p1.unlink()
        p2.unlink()

    def test_sha256_length(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"data")
            f.flush()
            path = Path(f.name)

        h = file_hash(path)
        assert len(h) == 64  # SHA-256 hex digest length
        path.unlink()


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_strips_dangerous_chars(self):
        assert "/" not in sanitize_filename("../../etc/passwd")
        assert "\\" not in sanitize_filename("..\\..\\windows\\system32")

    def test_keeps_safe_chars(self):
        result = sanitize_filename("my-file_v2.0.txt")
        assert result == "my-file_v2.0.txt"

    def test_empty_input(self):
        assert sanitize_filename("") == ""
