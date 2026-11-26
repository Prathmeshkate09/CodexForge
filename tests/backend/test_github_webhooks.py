from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import Settings
from app.core.errors import AuthorizationError, ForbiddenError
from app.core.github_auth import verify_github_webhook_signature
from app.domain.workflow import ProjectConnectionStatus
from app.main import create_app
from app.models.workflow import Repository
from app.schemas.workflow import ProjectCreate, WorkItemCreate
from app.services.workflow import WorkflowService

WEBHOOK_SECRET = "super-secret-webhook-key-12345678"  # noqa: S105


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_github_webhook_signature_success() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        github_webhook_secret=SecretStr(WEBHOOK_SECRET),
        allow_in_memory_rate_limiter=True,
    )
    payload = b'{"action": "added"}'
    sig = _sign_payload(WEBHOOK_SECRET, payload)
    # Should not raise
    verify_github_webhook_signature(settings, payload, sig)


def test_verify_github_webhook_signature_rejects_invalid_or_missing() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        github_webhook_secret=SecretStr(WEBHOOK_SECRET),
        allow_in_memory_rate_limiter=True,
    )
    payload = b'{"action": "added"}'

    with pytest.raises(AuthorizationError, match="Missing or malformed"):
        verify_github_webhook_signature(settings, payload, None)

    with pytest.raises(ForbiddenError, match="Invalid GitHub webhook signature"):
        verify_github_webhook_signature(settings, payload, "sha256=bad-signature")

    unconfigured = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        allow_in_memory_rate_limiter=True,
    )
    with pytest.raises(AuthorizationError, match="not configured"):
        verify_github_webhook_signature(unconfigured, payload, "sha256=123")


@pytest.mark.asyncio
async def test_process_github_installation_repositories_activates_and_revokes(
    session: AsyncSession,
) -> None:
    service = WorkflowService(session)
    project = await service.create_project(
        ProjectCreate(repository_full_name="org/my-repo", default_branch="main"),
        actor_subject="owner-1",
        correlation_id="corr-1",
    )
    assert project.connection_status == ProjectConnectionStatus.PENDING

    # Webhook adds repository
    activated = await service.process_github_installation_repositories(
        action="added",
        github_installation_id=999,
        repositories_added=["org/my-repo"],
        repositories_removed=[],
        correlation_id="corr-2",
    )
    assert len(activated) == 1
    assert activated[0].connection_status == ProjectConnectionStatus.ACTIVE
    assert activated[0].github_installation_id == 999

    # Now work item creation is permitted
    item = await service.create_work_item(
        WorkItemCreate(
            project_id=project.id,
            kind="bug",
            title="Active repo bug",
            description="Testing bug creation after activation.",
        ),
        actor_subject="owner-1",
        correlation_id="corr-3",
    )
    assert item.work_item.title == "Active repo bug"

    # Webhook removes repository
    revoked = await service.process_github_installation_repositories(
        action="removed",
        github_installation_id=999,
        repositories_added=[],
        repositories_removed=["org/my-repo"],
        correlation_id="corr-4",
    )
    assert len(revoked) == 1
    assert revoked[0].connection_status == ProjectConnectionStatus.REVOKED


@pytest.mark.asyncio
async def test_github_webhook_http_endpoint_delivery(session: AsyncSession) -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret=SecretStr("x" * 40),
        github_webhook_secret=SecretStr(WEBHOOK_SECRET),
        allow_in_memory_rate_limiter=True,
    )
    app = create_app(settings)

    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    # Create pending project
    project = Repository(
        id=uuid.uuid4(),
        owner_subject="user-gh",
        github_full_name="octocat/hello-world",
        default_branch="main",
        connection_status=ProjectConnectionStatus.PENDING,
    )
    session.add(project)
    await session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Ping event
        ping_body = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")
        ping_sig = _sign_payload(WEBHOOK_SECRET, ping_body)
        ping_res = await client.post(
            "/api/v1/webhooks/github",
            content=ping_body,
            headers={
                "X-Hub-Signature-256": ping_sig,
                "X-GitHub-Event": "ping",
            },
        )
        assert ping_res.status_code == 200
        assert ping_res.json()["message"] == "pong"

        # Installation repositories added event
        payload_dict = {
            "action": "added",
            "installation": {"id": 12345},
            "repositories_added": [{"full_name": "octocat/hello-world"}],
            "repositories_removed": [],
        }
        body = json.dumps(payload_dict).encode("utf-8")
        sig = _sign_payload(WEBHOOK_SECRET, body)
        delivery_id = "delivery-" + ("x" * 20)

        res = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "installation_repositories",
                "X-GitHub-Delivery": delivery_id,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["affected_projects"] == 1

        # Check repository in db
        await session.refresh(project)
        assert project.connection_status == ProjectConnectionStatus.ACTIVE
        assert project.github_installation_id == 12345

        # Replay same delivery_id (deduplication)
        replay_res = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "installation_repositories",
                "X-GitHub-Delivery": delivery_id,
            },
        )
        assert replay_res.status_code == 200
        assert replay_res.json() == data


@pytest.mark.asyncio
async def test_dev_verification_endpoint(session: AsyncSession) -> None:
    dev_secret = "dev-secret-at-least-32-chars-long-1234"  # noqa: S105
    settings = Settings(
        environment="development",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret=SecretStr("x" * 40),
        allow_dev_identity=True,
        dev_identity_secret=SecretStr(dev_secret),
        allow_in_memory_rate_limiter=True,
    )
    app = create_app(settings)

    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    project = Repository(
        id=uuid.uuid4(),
        owner_subject="dev-user",
        github_full_name="dev/repo",
        default_branch="main",
        connection_status=ProjectConnectionStatus.PENDING,
    )
    session.add(project)
    await session.commit()

    from app.core.security import issue_development_token

    token = issue_development_token(
        settings, subject="dev-user", email=None, name=None, scopes=set()
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Without dev key header -> 401
        unauthorized_res = await client.post(
            f"/api/v1/projects/{project.id}/verify-dev",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert unauthorized_res.status_code == 401

        # With dev key header -> 200 and project becomes ACTIVE
        authorized_res = await client.post(
            f"/api/v1/projects/{project.id}/verify-dev",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Dev-Identity-Key": dev_secret,
            },
        )
        assert authorized_res.status_code == 200
        assert authorized_res.json()["connection_status"] == "active"
