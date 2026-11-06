import time
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from cinecircle_api.auth import AuthUnavailable, InvalidToken, TokenVerifier, make_verifier
from cinecircle_api.settings import Settings
from tests.tokens import TEST_JWT_SECRET, TEST_SUPABASE_URL, auth_settings, make_token

UID = "6f1c2b6e-0000-4000-8000-000000000001"
DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"


class StubJwks:
    """Stands in for jwt.PyJWKClient: hands back one fixed public key, or raises."""

    def __init__(self, public_key=None, error: Exception | None = None) -> None:
        self.jwk = jwt.PyJWK(jwt.algorithms.ECAlgorithm.to_jwk(public_key, as_dict=True))
        self.error = error

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if self.error:
            raise self.error
        return self.jwk


def verifier(secret=TEST_JWT_SECRET, jwks=None):
    return TokenVerifier(f"{TEST_SUPABASE_URL}/auth/v1", secret, jwks)


def es256_token(private_key, **claims) -> str:
    payload = {
        "sub": UID,
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload | claims, private_key, algorithm="ES256", headers={"kid": "k1"})


def test_hs256_token_accepted():
    claims = verifier().verify(make_token(UID, email="gal@example.com"))
    assert (str(claims.user_id), claims.email) == (UID, "gal@example.com")
    assert claims.raw["role"] == "authenticated"


def test_es256_token_accepted_via_jwks():
    private = ec.generate_private_key(ec.SECP256R1())
    jwks = StubJwks(private.public_key())
    claims = verifier(secret=None, jwks=jwks).verify(es256_token(private))
    assert claims.user_id == UUID(UID)
    assert claims.email is None


def test_es256_token_signed_by_another_key_rejected():
    jwks = StubJwks(ec.generate_private_key(ec.SECP256R1()).public_key())
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(InvalidToken):
        verifier(secret=None, jwks=jwks).verify(es256_token(other))


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"exp": None},
        {"aud": "anon"},
        {"iss": "http://evil/auth/v1"},
        {"role": "anon"},
        {"role": "service_role"},
        {"sub": None},
        {"sub": "not-a-uuid"},
    ],
)
def test_rejects_bad_claims(overrides):
    with pytest.raises(InvalidToken):
        verifier().verify(make_token(UID, **overrides))


def test_rejects_bad_signature_and_alg_none():
    forged = make_token(UID)
    other = jwt.encode(jwt.decode(forged, options={"verify_signature": False}), "x" * 40, "HS256")
    with pytest.raises(InvalidToken):
        verifier().verify(other)
    unsigned = jwt.encode(jwt.decode(forged, options={"verify_signature": False}), None, "none")
    with pytest.raises(InvalidToken):
        verifier().verify(unsigned)


def test_rejects_garbage_and_unsupported_alg():
    for token in ("garbage", "a.b.c", ""):
        with pytest.raises(InvalidToken):
            verifier().verify(token)
    hs512 = jwt.encode({"sub": UID}, TEST_JWT_SECRET * 2, algorithm="HS512")
    with pytest.raises(InvalidToken):
        verifier().verify(hs512)


def test_rejects_hs256_when_no_secret():
    with pytest.raises(InvalidToken):
        verifier(secret=None).verify(make_token(UID))


def test_unreachable_jwks_is_auth_unavailable():
    private = ec.generate_private_key(ec.SECP256R1())
    jwks = StubJwks(private.public_key(), error=jwt.PyJWKClientError("down"))
    with pytest.raises(AuthUnavailable):
        verifier(secret=None, jwks=jwks).verify(es256_token(private))


def test_es256_without_jwks_client_is_auth_unavailable():
    private = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(AuthUnavailable):
        verifier(secret=None, jwks=None).verify(es256_token(private))


def test_make_verifier_none_without_supabase_url(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert make_verifier(Settings(database_url=DEAD, _env_file=None)) is None


def test_make_verifier_built_from_settings():
    assert make_verifier(auth_settings(DEAD)) is not None
