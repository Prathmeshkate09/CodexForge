from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request
from pydantic import SecretStr, ValidationError

from app.api.deps import get_rate_limited_principal
from app.core.config import Settings
from app.core.errors import AuthorizationError
from app.core.security import (
    JwtVerifier,
    Principal,
    issue_development_token,
    verify_development_identity_secret,
)
from app.services.rate_limit import RateLimitResult


def _production_settings_with_jwks(jwks_url: str) -> Settings:
    return Settings(
        environment="production",
        database_url="postgresql+asyncpg://example:example@localhost/example",
        jwt_jwks_url=jwks_url,
        cors_allowed_origins=["https://app.example.test"],
    )


def test_production_settings_reject_in_memory_rate_limit_and_dev_identity() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_public_key=SecretStr("test-public-key"),
            cors_allowed_origins=["https://app.example.com"],
            allow_in_memory_rate_limiter=True,
        )


@pytest.mark.asyncio
async def test_authenticated_rate_limit_uses_verified_subject_not_proxy_ip() -> None:
    class RecordingLimiter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, int]] = []

        async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
            self.calls.append((key, limit, window_seconds))
            return RateLimitResult(True, 1, limit - 1)

    settings = Settings(
        environment="test",
        jwt_secret=SecretStr("x" * 40),
        allow_in_memory_rate_limiter=True,
    )
    limiter = RecordingLimiter()
    request = cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=settings, rate_limiter=limiter)),
            client=SimpleNamespace(host="shared-proxy.example.test"),
        ),
    )
    principal = Principal(subject="firebase-user-1")

    actual = await get_rate_limited_principal(request, principal)

    assert actual == principal
    assert limiter.calls == [
        (
            "user:firebase-user-1",
            settings.rate_limit_requests,
            settings.rate_limit_window_seconds,
        )
    ]


def test_blank_jwks_url_is_normalized_to_unset() -> None:
    settings = Settings(
        environment="production",
        jwt_public_key=SecretStr("test-public-key"),
        jwt_jwks_url="",
        cors_allowed_origins=["https://app.example.com"],
    )

    assert settings.jwt_jwks_url is None


@pytest.mark.parametrize(
    ("jwt_secret", "dev_identity_secret"),
    [
        ("replace-with-at-least-32-random-local-characters", "d" * 40),
        ("j" * 40, "too-short"),
    ],
)
def test_development_identity_rejects_placeholder_or_short_secrets(
    jwt_secret: str,
    dev_identity_secret: str,
) -> None:
    with pytest.raises(ValidationError, match="non-placeholder secret"):
        Settings(
            environment="test",
            jwt_secret=SecretStr(jwt_secret),
            dev_identity_secret=SecretStr(dev_identity_secret),
            allow_dev_identity=True,
            allow_in_memory_rate_limiter=True,
        )


@pytest.mark.parametrize(
    "jwks_url",
    [
        "http://issuer.example.test/.well-known/jwks.json",
        "https://",
        "https://user:password@issuer.example.test/.well-known/jwks.json",
        "https://issuer.example.test/.well-known/jwks.json?tenant=codexforge",
        "https://issuer.example.test/.well-known/jwks.json#current",
        "https://localhost/.well-known/jwks.json",
        "https://127.0.0.1/.well-known/jwks.json",
        "https://0177.0.0.1/.well-known/jwks.json",
        "https://[::1]/.well-known/jwks.json",
    ],
)
def test_production_settings_rejects_unsafe_jwks_urls(jwks_url: str) -> None:
    with pytest.raises(ValidationError, match="CODEXFORGE_JWT_JWKS_URL"):
        _production_settings_with_jwks(jwks_url)


@pytest.mark.parametrize(
    "jwks_url",
    [
        "https://issuer.example.test/.well-known/jwks.json",
        "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
    ],
)
def test_production_settings_accepts_generic_public_https_jwks_url(
    jwks_url: str,
) -> None:
    settings = _production_settings_with_jwks(jwks_url)

    assert settings.jwt_jwks_url == jwks_url


@pytest.mark.asyncio
async def test_development_token_requires_guard_and_validates_subject() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret=SecretStr("x" * 40),
        dev_identity_secret=SecretStr("development-only-key-0123456789abcdef"),
        allow_dev_identity=True,
        allow_in_memory_rate_limiter=True,
    )
    verify_development_identity_secret(settings, "development-only-key-0123456789abcdef")
    token = issue_development_token(
        settings,
        subject="user-123",
        email="user@example.com",
        name="User",
        scopes={"codexforge:api"},
    )
    principal = await JwtVerifier(settings).verify(token)
    assert principal.subject == "user-123"
    assert principal.is_development_identity is True
    assert "codexforge:api" in principal.scopes

    with pytest.raises(AuthorizationError):
        verify_development_identity_secret(settings, "wrong-key")


@pytest.mark.asyncio
async def test_hs256_requires_explicit_development_identity_enablement() -> None:
    settings = Settings(
        environment="local",
        jwt_secret=SecretStr("x" * 40),
        allow_in_memory_rate_limiter=True,
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "local-user",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthorizationError, match="Symmetric bearer tokens require"):
        await JwtVerifier(settings).verify(token)


@pytest.mark.asyncio
async def test_rs256_jwks_validation_checks_key_id_issuer_and_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "test-key-1"
    settings = Settings(
        environment="production",
        database_url="postgresql+asyncpg://example:example@localhost/example",
        jwt_issuer="https://issuer.example.test",
        jwt_audience="codexforge-api",
        jwt_jwks_url="https://issuer.example.test/.well-known/jwks.json",
        cors_allowed_origins=["https://app.example.test"],
    )

    fetched_urls: list[str] = []

    async def fake_jwks(_: type[JwtVerifier], url: str) -> dict[str, object]:
        fetched_urls.append(url)
        return {"keys": [jwk]}

    monkeypatch.setattr(JwtVerifier, "_fetch_jwks", classmethod(fake_jwks))
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "firebase-user-1",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )

    principal = await JwtVerifier(settings).verify(token)
    assert principal.subject == "firebase-user-1"
    assert fetched_urls == [settings.jwt_jwks_url]
