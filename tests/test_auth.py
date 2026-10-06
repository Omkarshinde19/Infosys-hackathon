from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from services import auth
from services.gateway.main import app


@pytest.mark.parametrize("value", [None, "", "change-me", "short"])
def test_a_known_or_weak_secret_is_never_used_to_sign(value):
    # `./netheal setup` used to copy JWT_SECRET=change-me from .env.example: anyone knowing
    # that string could forge an admin session.
    secret = auth.signing_secret(value)
    assert secret != value and len(secret) == 64


def test_a_strong_configured_secret_is_kept():
    strong = "a" * 64
    assert auth.signing_secret(strong) == strong


@pytest.mark.parametrize("claims", [{"sub": "x"}, {"sub": "x", "role": "root"}])
def test_a_signed_token_with_a_missing_or_unknown_role_is_rejected(claims):
    exp = datetime.now(UTC) + timedelta(hours=1)
    token = jwt.encode({**claims, "exp": exp}, auth.SECRET, "HS256")
    with TestClient(app) as client:
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
