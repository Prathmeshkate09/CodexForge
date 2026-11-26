from __future__ import annotations

import hashlib
import hmac

from app.core.config import Settings
from app.core.errors import AuthorizationError, ForbiddenError


def verify_github_webhook_signature(
    settings: Settings,
    payload_bytes: bytes,
    signature_header: str | None,
) -> None:
    """Verifies GitHub's X-Hub-Signature-256 HMAC digest in constant time."""
    if settings.github_webhook_secret is None:
        raise AuthorizationError("GitHub webhook verification is not configured.")

    if not signature_header or not signature_header.startswith("sha256="):
        raise AuthorizationError("Missing or malformed X-Hub-Signature-256 header.")

    expected_signature = signature_header[7:].strip()
    secret = settings.github_webhook_secret.get_secret_value().encode("utf-8")
    computed_digest = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_digest.casefold(), expected_signature.casefold()):
        raise ForbiddenError("Invalid GitHub webhook signature.")
