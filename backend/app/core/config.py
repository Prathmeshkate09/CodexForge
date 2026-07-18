from __future__ import annotations

import re
from functools import lru_cache
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DNS_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
_MINIMUM_DEVELOPMENT_SECRET_LENGTH = 32


def _validate_jwks_host(hostname: str) -> None:
    """Accept public generic OAuth/OIDC hosts without pinning the provider to Firebase."""

    normalized_host = hostname.rstrip(".").lower()
    if not normalized_host:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must include a hostname.")

    try:
        address = ip_address(normalized_host)
    except ValueError:
        address = None

    if address is not None:
        if not address.is_global:
            raise ValueError(
                "CODEXFORGE_JWT_JWKS_URL must not target a private, local, or reserved IP address."
            )
        return

    try:
        ascii_host = normalized_host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL has an invalid hostname.") from exc
    if "." not in ascii_host or len(ascii_host) > 253:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must use a fully qualified public hostname.")
    if all(character.isdigit() or character == "." for character in ascii_host):
        raise ValueError("CODEXFORGE_JWT_JWKS_URL has an invalid IP address.")
    if ascii_host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must not target a local hostname.")
    labels = ascii_host.split(".")
    if any(
        not label or len(label) > 63 or _DNS_LABEL_PATTERN.fullmatch(label) is None
        for label in labels
    ):
        raise ValueError("CODEXFORGE_JWT_JWKS_URL has an invalid hostname.")


def _validate_jwks_url(value: str) -> str:
    if (
        not value
        or value != value.strip()
        or any(character.isspace() or ord(character) < 32 for character in value)
    ):
        raise ValueError(
            "CODEXFORGE_JWT_JWKS_URL must be an absolute HTTPS URL without whitespace."
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL has an invalid host or port.") from exc
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname is None:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must be an absolute HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must not contain userinfo.")
    if "?" in value or "#" in value:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL must not contain a query or fragment.")
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("CODEXFORGE_JWT_JWKS_URL has an invalid port.")
    _validate_jwks_host(parsed.hostname)
    return value


class Settings(BaseSettings):
    """Runtime settings. Production credentials are injected by Secret Manager."""

    model_config = SettingsConfigDict(
        env_prefix="CODEXFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "development", "test", "staging", "production"] = "local"
    api_name: str = "CodexForge API"
    api_version: str = "0.1.0"
    database_url: str = "postgresql+asyncpg://codexforge:codexforge@localhost:5432/codexforge"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "codexforge"
    jwt_audience: str = "codexforge-api"
    jwt_jwks_url: str | None = None
    jwt_public_key: SecretStr | None = None
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    allow_dev_identity: bool = False
    dev_identity_secret: SecretStr | None = None
    rate_limit_requests: int = Field(default=120, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    allow_in_memory_rate_limiter: bool = False
    cors_allowed_origins: list[str] = Field(default_factory=list)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-sol"
    safety_identifier_salt: SecretStr | None = None

    @field_validator("jwt_jwks_url")
    @classmethod
    def validate_jwt_jwks_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return _validate_jwks_url(value)

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Settings:
        if self.allows_development_features and not self.cors_allowed_origins:
            self.cors_allowed_origins = [
                "http://localhost:5173",
                "http://localhost:4173",
            ]
        if "*" in self.cors_allowed_origins:
            raise ValueError(
                "CODEXFORGE_CORS_ALLOWED_ORIGINS must not contain '*' "
                "when credentials are enabled"
            )
        if self.environment in {"staging", "production"}:
            if self.jwt_public_key is None and self.jwt_jwks_url is None:
                raise ValueError(
                    "CODEXFORGE_JWT_PUBLIC_KEY or CODEXFORGE_JWT_JWKS_URL "
                    "is required outside local/test"
                )
            if self.allow_dev_identity:
                raise ValueError("CODEXFORGE_ALLOW_DEV_IDENTITY is forbidden outside local/test")
            if self.allow_in_memory_rate_limiter:
                raise ValueError("in-memory rate limiting is forbidden outside local/test")
            if not self.cors_allowed_origins:
                raise ValueError("CODEXFORGE_CORS_ALLOWED_ORIGINS is required outside local/test")
        if self.allow_dev_identity:
            if not self.allows_development_features:
                raise ValueError("development identity is only allowed in local/test")
            if self.dev_identity_secret is None or self.jwt_secret is None:
                raise ValueError(
                    "development identity requires CODEXFORGE_DEV_IDENTITY_SECRET "
                    "and CODEXFORGE_JWT_SECRET"
                )
            development_secrets = {
                "CODEXFORGE_DEV_IDENTITY_SECRET": self.dev_identity_secret.get_secret_value(),
                "CODEXFORGE_JWT_SECRET": self.jwt_secret.get_secret_value(),
            }
            for setting_name, secret_value in development_secrets.items():
                normalized_secret = secret_value.strip()
                if (
                    len(normalized_secret) < _MINIMUM_DEVELOPMENT_SECRET_LENGTH
                    or "replace-with" in normalized_secret.casefold()
                ):
                    raise ValueError(
                        f"{setting_name} must be a non-placeholder secret of at least "
                        f"{_MINIMUM_DEVELOPMENT_SECRET_LENGTH} characters when "
                        "development identity is enabled"
                    )
        return self

    @property
    def is_local_or_test(self) -> bool:
        return self.environment in {"local", "development", "test"}

    @property
    def allows_development_features(self) -> bool:
        return self.environment in {"local", "development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
