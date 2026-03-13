"""JWT authentication for the approval portal."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 1


def create_jwt(*, secret: str, asset_id: UUID, client_id: UUID, client_slug: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"client:{client_slug}",
        "asset_id": str(asset_id),
        "client_id": str(client_id),
        "scope": "review",
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def verify_jwt(*, secret: str, token: str) -> dict:
    """Verify and decode JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
