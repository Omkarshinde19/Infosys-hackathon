"""Test helpers for logging in (demo accounts live in config/DEMO_ACCOUNTS.md)."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from services import auth

DEMO_ACCOUNTS = Path(__file__).resolve().parents[1] / "config" / "DEMO_ACCOUNTS.md"


def demo_password(username: str) -> str:
    match = re.search(rf"\| `{username}` \| `([^`]+)` \|", DEMO_ACCOUNTS.read_text())
    return match.group(1)


def bearer(role: str) -> dict:
    """Authorization header for a signed-in user with this role (tokens signed in-process)."""
    exp = datetime.now(UTC) + timedelta(hours=1)
    token = jwt.encode({"sub": role, "role": role, "exp": exp}, auth.SECRET, "HS256")
    return {"Authorization": f"Bearer {token}"}
