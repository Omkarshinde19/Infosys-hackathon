"""Login and role-based access: viewer < operator < admin.

Passwords are stored as salted PBKDF2-SHA256 hashes (config/users.yaml). A successful login
returns a signed JWT (HS256) carrying the username and role, valid for 12 hours.
"""

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
import yaml
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ROOT = Path(__file__).resolve().parents[1]
USERS_PATH = ROOT / "config" / "users.yaml"
load_dotenv(ROOT / ".env")  # JWT_SECRET (made by ./netheal start) survives restarts
ROLES = ["viewer", "operator", "admin"]
TOKEN_HOURS = 12
PLACEHOLDERS = {"change-me"}


def signing_secret(value: str | None) -> str:
    """The configured secret, or a random one when it is missing, a placeholder or short: a
    known secret would let anyone forge an admin session. (Random means every engine restart
    signs everyone out, so ./netheal start writes a real one to .env.)"""
    if not value or value in PLACEHOLDERS or len(value) < 32:
        return secrets.token_hex(32)
    return value


SECRET = signing_secret(os.getenv("JWT_SECRET"))

USERS = yaml.safe_load(USERS_PATH.read_text())["users"]
bearer = HTTPBearer(auto_error=False)


def login(username: str, password: str) -> dict | None:
    user = USERS.get(username)
    if user is None:
        return None
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(user["salt"]), 200_000)
    if not hmac.compare_digest(digest.hex(), user["hash"]):
        return None
    expires = datetime.now(UTC) + timedelta(hours=TOKEN_HOURS)
    token = jwt.encode({"sub": username, "role": user["role"], "exp": expires}, SECRET, "HS256")
    return {"token": token, "username": username, "role": user["role"]}


def require(role: str):
    """FastAPI dependency: the caller must be logged in with at least `role`."""

    def check(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
        if creds is None:
            raise HTTPException(401, "Log in first")
        try:
            claims = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"],
                                options={"require": ["exp", "sub", "role"]})  # fmt: skip
        except jwt.PyJWTError as e:
            raise HTTPException(401, "Invalid or expired session") from e
        if claims["role"] not in ROLES:
            raise HTTPException(401, "Invalid or expired session")
        if ROLES.index(claims["role"]) < ROLES.index(role):
            raise HTTPException(403, f"Needs the {role} role")
        return {"username": claims["sub"], "role": claims["role"]}

    return check
