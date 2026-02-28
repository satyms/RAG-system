"""Miscellaneous helper utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_hash(path: Path, algo: str = "sha256") -> str:
    """Return the hex digest of a file."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_filename(name: str) -> str:
    """Strip potentially dangerous characters from a filename."""
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip()
