from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.errors import AuthorizationError


class Principal(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    email: str | None = None
    name: str | None = None
    scopes: frozenset[str] = Field(default_factory=frozenset)
    is_development_identity: bool = False


def _scopes_from_claims(payload: dict[str, Any]) -> frozenset[str]:
    scope = payload.get("scope", payload.get("scp", []))
    if isinstance(scope, str):
        return frozenset(part for part in scope.split(" ") if part)
    if isinstance(scope, list) and all(isinstance(item, str) for item in scope):
        return frozenset(scope)
    return frozenset()


class JwtVerifier:
    """Validates OAuth2 bearer JWTs without trusting client-supplied identity data."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    _jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthorizationError("The bearer token is malformed.") from exc

        algorithm = header.get("alg")
        if algorithm == "none" or not isinstance(algorithm, str):
            raise AuthorizationError("The bearer token uses an unsupported signing algorithm.")

        try:
            if algorithm == "RS256" and self._settings.jwt_jwks_url:
                payload = await self._decode_with_jwks(token, header)
            else:
                payload = self._decode(token, algorithm)
        except jwt.PyJWTError as exc:
            raise AuthorizationError("The bearer token is invalid or expired.") from exc

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthorizationError("The bearer token is missing a subject claim.")
        email = payload.get("email")
        name = payload.get("name")
        return Principal(
            subject=subject,
            email=email if isinstance(email, str) else None,
            name=name if isinstance(name, str) else None,
            scopes=_scopes_from_claims(payload),
            is_development_identity=payload.get("dev") is True,
        )

    def _decode(self, token: str, algorithm: str) -> dict[str, Any]:
        common: dict[str, Any] = {
            "algorithms": [algorithm],
            "audience": self._settings.jwt_audience,
            "issuer": self._settings.jwt_issuer,
            "leeway": self._settings.jwt_clock_skew_seconds,
            "options": {"require": ["exp", "iat", "sub", "aud", "iss"]},
        }
        if algorithm == "HS256":
            if (
                not self._settings.is_local_or_test
                or not self._settings.allow_dev_identity
                or self._settings.jwt_secret is None
            ):
                raise AuthorizationError(
                    "Symmetric bearer tokens require explicitly enabled local development identity."
                )
            return jwt.decode(token, self._settings.jwt_secret.get_secret_value(), **common)

        if algorithm == "RS256" and self._settings.jwt_public_key is not None:
            return jwt.decode(token, self._settings.jwt_public_key.get_secret_value(), **common)

        raise AuthorizationError("The bearer token uses an unsupported signing configuration.")

    async def _decode_with_jwks(self, token: str, header: dict[str, Any]) -> dict[str, Any]:
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthorizationError("The bearer token is missing a key identifier.")
        jwks_url = self._settings.jwt_jwks_url
        if jwks_url is None:
            raise AuthorizationError("JWKS validation is not configured.")
        jwks = await self._fetch_jwks(jwks_url)
        keys = jwks.get("keys")
        if not isinstance(keys, list):
            raise AuthorizationError("The configured JWKS response is invalid.")
        matching_key = next(
            (key for key in keys if isinstance(key, dict) and key.get("kid") == kid),
            None,
        )
        if matching_key is None:
            raise AuthorizationError("The bearer token signing key is unknown.")
        try:
            public_key = cast(
                RSAPublicKey,
                jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matching_key)),
            )
            return jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                leeway=self._settings.jwt_clock_skew_seconds,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthorizationError("The bearer token is invalid or expired.") from exc

    @classmethod
    async def _fetch_jwks(cls, jwks_url: str) -> dict[str, Any]:
        cached = cls._jwks_cache.get(jwks_url)
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            return cached[1]
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.get(jwks_url, headers={"Accept": "application/json"})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthorizationError("The identity provider signing keys are unavailable.") from exc
        if not isinstance(payload, dict):
            raise AuthorizationError("The configured JWKS response is invalid.")
        cls._jwks_cache[jwks_url] = (now + 300, payload)
        return payload


def issue_development_token(
    settings: Settings,
    *,
    subject: str,
    email: str | None,
    name: str | None,
    scopes: set[str],
) -> str:
    """Issue a short-lived token only after the guarded local development check."""

    if (
        not settings.allow_dev_identity
        or not settings.is_local_or_test
        or settings.jwt_secret is None
    ):
        raise AuthorizationError("Development identity is disabled.")
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "scope": " ".join(sorted(scopes)),
        "dev": True,
    }
    if email:
        claims["email"] = email
    if name:
        claims["name"] = name
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def verify_development_identity_secret(settings: Settings, supplied_secret: str | None) -> None:
    expected = settings.dev_identity_secret
    if not settings.allow_dev_identity or not settings.is_local_or_test or expected is None:
        raise AuthorizationError("Development identity is disabled.")
    if supplied_secret is None:
        raise AuthorizationError("A development identity key is required.")
    supplied_digest = hashlib.sha256(supplied_secret.encode()).digest()
    expected_digest = hashlib.sha256(expected.get_secret_value().encode()).digest()
    if not hmac.compare_digest(supplied_digest, expected_digest):
        raise AuthorizationError("The development identity key is invalid.")


def safety_identifier(subject: str, settings: Settings) -> str:
    """Derive a non-reversible per-user provider identifier; never send raw user IDs."""

    salt = settings.safety_identifier_salt or settings.jwt_secret
    if salt is None:
        raise RuntimeError(
            "A safety identifier salt must be configured before calling a model provider."
        )
    return hashlib.sha256(f"{salt.get_secret_value()}:{subject}".encode()).hexdigest()
