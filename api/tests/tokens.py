"""Helpers for minting Supabase-style access tokens in tests (never the real local secret)."""

import time
from typing import Any

import jwt

from cinecircle_api.settings import Settings

TEST_SUPABASE_URL = "http://127.0.0.1:55321"
TEST_JWT_SECRET = "test-only-jwt-secret-0123456789-abcdefghij"


def make_token(sub: str, /, **overrides: Any) -> str:
    """An HS256 token the test verifier accepts; an override of None removes that claim."""
    claims: dict[str, Any] = {
        "sub": sub,
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "role": "authenticated",
        "email": "gal@example.com",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def auth_settings(database_url: str, **overrides: Any) -> Settings:
    return Settings(
        database_url=database_url,
        supabase_url=TEST_SUPABASE_URL,
        supabase_jwt_secret=TEST_JWT_SECRET,
        _env_file=None,
        **overrides,
    )
