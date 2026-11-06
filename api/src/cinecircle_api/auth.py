"""Sign-in: verify Supabase access tokens and expose the signed-in user to routes.

Local Supabase signs with ES256 (public key at /auth/v1/.well-known/jwks.json); legacy
projects sign with a shared HS256 secret. Both are accepted, nothing else is.
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request

from cinecircle_api.settings import Settings

_JWKS_ALGORITHMS = {"ES256", "RS256"}
_LEEWAY_SECONDS = 30


@dataclass(frozen=True)
class Claims:
    user_id: UUID
    email: str | None
    raw: dict[str, Any]  # the verified payload, forwarded to Postgres as request.jwt.claims


class InvalidToken(Exception):
    """The token is missing, malformed, expired, forged or meant for something else."""


class AuthUnavailable(Exception):
    """We cannot tell whether the token is good (no verifier configured, JWKS unreachable)."""


class TokenVerifier:
    def __init__(self, issuer: str, hs256_secret: str | None, jwks: jwt.PyJWKClient | None) -> None:
        self._issuer = issuer
        self._secret = hs256_secret
        self._jwks = jwks

    def verify(self, token: str) -> Claims:
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError:
            raise InvalidToken from None
        if alg == "HS256":
            if not self._secret:
                raise InvalidToken
            key: Any = self._secret
        elif alg in _JWKS_ALGORITHMS:
            if self._jwks is None:
                raise AuthUnavailable
            try:
                key = self._jwks.get_signing_key_from_jwt(token).key
            except jwt.PyJWKClientError:
                raise AuthUnavailable from None
            except jwt.PyJWTError:
                raise InvalidToken from None
        else:
            raise InvalidToken
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                issuer=self._issuer,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
            if payload.get("role") != "authenticated":
                raise InvalidToken
            user_id = UUID(payload["sub"])
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
            raise InvalidToken from None
        email = payload.get("email")
        return Claims(user_id, email if isinstance(email, str) else None, payload)


def make_verifier(settings: Settings) -> TokenVerifier | None:
    if settings.supabase_url is None:
        return None
    base = settings.supabase_url
    jwks = jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", timeout=5)
    return TokenVerifier(f"{base}/auth/v1", settings.supabase_jwt_secret, jwks)


def _not_authenticated() -> HTTPException:
    return HTTPException(401, "not_authenticated", headers={"WWW-Authenticate": "Bearer"})


def current_claims(request: Request, authorization: str | None = Header(None)) -> Claims:
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _not_authenticated()
    verifier: TokenVerifier | None = request.app.state.verifier
    if verifier is None:
        raise HTTPException(503, "auth_unavailable")
    try:
        return verifier.verify(token)
    except InvalidToken:
        raise _not_authenticated() from None
    except AuthUnavailable:
        raise HTTPException(503, "auth_unavailable") from None


CurrentUser = Annotated[Claims, Depends(current_claims)]
