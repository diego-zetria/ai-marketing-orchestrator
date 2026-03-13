"""Tests for JWT authentication service."""

import time
from uuid import uuid4

import jwt
import pytest

from src.approval.services.auth import (
    JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS,
    create_jwt,
    verify_jwt,
)

SECRET = "test-secret-key-for-jwt"
ASSET_ID = uuid4()
CLIENT_ID = uuid4()
CLIENT_SLUG = "acme-corp"


def _make_token(**overrides):
    """Helper to create a JWT with default test values."""
    kwargs = {
        "secret": SECRET,
        "asset_id": ASSET_ID,
        "client_id": CLIENT_ID,
        "client_slug": CLIENT_SLUG,
    }
    kwargs.update(overrides)
    return create_jwt(**kwargs)


class TestCreateJwt:
    def test_create_jwt_returns_string(self):
        token = _make_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_jwt_contains_expected_claims(self):
        token = _make_token()
        decoded = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM])
        assert decoded["sub"] == f"client:{CLIENT_SLUG}"
        assert decoded["asset_id"] == str(ASSET_ID)
        assert decoded["client_id"] == str(CLIENT_ID)
        assert decoded["scope"] == "review"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_create_jwt_expiration(self):
        token = _make_token()
        decoded = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM])
        diff = decoded["exp"] - decoded["iat"]
        expected_seconds = JWT_EXPIRATION_HOURS * 3600
        assert diff == expected_seconds


class TestVerifyJwt:
    def test_verify_jwt_valid_token(self):
        token = _make_token()
        decoded = verify_jwt(secret=SECRET, token=token)
        assert decoded["sub"] == f"client:{CLIENT_SLUG}"
        assert decoded["asset_id"] == str(ASSET_ID)
        assert decoded["client_id"] == str(CLIENT_ID)
        assert decoded["scope"] == "review"

    def test_verify_jwt_expired_raises(self):
        # Create a token that is already expired
        payload = {
            "sub": f"client:{CLIENT_SLUG}",
            "asset_id": str(ASSET_ID),
            "client_id": str(CLIENT_ID),
            "scope": "review",
            "iat": time.time() - 7200,
            "exp": time.time() - 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_jwt(secret=SECRET, token=token)

    def test_verify_jwt_invalid_signature_raises(self):
        token = _make_token()
        with pytest.raises(jwt.InvalidSignatureError):
            verify_jwt(secret="wrong-secret", token=token)

    def test_verify_jwt_tampered_payload_raises(self):
        token = _make_token()
        # Tamper with the payload portion (second segment)
        parts = token.split(".")
        # Modify the payload by replacing a character
        tampered_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        with pytest.raises(jwt.InvalidTokenError):
            verify_jwt(secret=SECRET, token=tampered_token)


class TestConstants:
    def test_jwt_algorithm_constant(self):
        assert JWT_ALGORITHM == "HS256"

    def test_jwt_expiration_constant(self):
        assert JWT_EXPIRATION_HOURS == 1
