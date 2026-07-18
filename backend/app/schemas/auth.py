from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._:@-]+$")
    email: str | None = Field(default=None, max_length=320)
    name: str | None = Field(default=None, max_length=255)
    scopes: set[str] = Field(default_factory=lambda: {"codexforge:api"}, max_length=20)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 response metadata, not a credential.
    expires_in: int = 900
