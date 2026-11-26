from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import Settings
from app.core.github_client import GitHubClient, is_path_redacted
from app.domain.workflow import (
    ProjectConnectionStatus,
    RunStage,
    RunStatus,
    WorkItemKind,
    WorkItemStatus,
)
from app.main import app
from app.models.workflow import Repository, WorkItem, WorkRun
from app.services.planning_worker import PlanningWorkerService

DUMMY_COMMIT_SHA = "a" * 40


def test_is_path_redacted() -> None:
    # Secrets
    assert is_path_redacted(".env") is True
    assert is_path_redacted(".env.local") is True
    assert is_path_redacted("config/secret.key") is True
    assert is_path_redacted("keys/app.pem") is True
    assert is_path_redacted("service-account-prod.json") is True
    assert is_path_redacted(".ssh/id_rsa") is True

    # Directories
    assert is_path_redacted(".git/config") is True
    assert is_path_redacted("node_modules/react/index.js") is True
    assert is_path_redacted(".venv/lib/site-packages/pkg.py") is True
    assert is_path_redacted("dist/bundle.js") is True

    # Binaries
    assert is_path_redacted("bin/server.exe") is True
    assert is_path_redacted("static/logo.png") is True
    assert is_path_redacted("lib/native.so") is True

    # Safe files
    assert is_path_redacted("README.md") is False
    assert is_path_redacted("backend/app/main.py") is False
    assert is_path_redacted(".github/workflows/ci.yml") is False
    assert is_path_redacted("package.json") is False


@pytest.mark.asyncio
async def test_planning_worker_success(session: AsyncSession) -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        allow_in_memory_rate_limiter=True,
        openai_api_key=None,
    )

    # 1. Setup repository and work item
    repo = Repository(
        id=uuid.uuid4(),
        owner_subject="test-user",
        github_full_name="org/repo",
        default_branch="main",
        github_installation_id=12345,
        connection_status=ProjectConnectionStatus.ACTIVE,
    )
    work_item = WorkItem(
        id=uuid.uuid4(),
        repository_id=repo.id,
        title="Fix database deadlock in CI",
        description="The CI tests fail intermittently due to a deadlock during migration setup.",
        kind=WorkItemKind.BUG,
        status=WorkItemStatus.DRAFT,
    )
    run = WorkRun(
        id=uuid.uuid4(),
        work_item_id=work_item.id,
        stage=RunStage.PLAN,
        status=RunStatus.QUEUED,
        is_current=True,
    )
    session.add_all([repo, work_item, run])
    await session.commit()

    # 2. Mock GitHub client
    mock_gh = AsyncMock(spec=GitHubClient)
    mock_gh.get_default_branch_commit.return_value = ("main", DUMMY_COMMIT_SHA)
    mock_gh.get_repository_tree.return_value = [
        {"path": ".github/workflows/ci.yml", "type": "blob", "sha": "1" * 40},
        {"path": "backend/alembic/env.py", "type": "blob", "sha": "2" * 40},
        {"path": "tests/test_db.py", "type": "blob", "sha": "3" * 40},
    ]
    mock_gh.get_file_content.return_value = "def test_db(): pass"

    worker = PlanningWorkerService(session, settings, github_client=mock_gh)
    result = await worker.execute_plan_run(
        run.id,
        actor_subject="test-user",
        correlation_id="corr-123",
    )

    # 3. Assertions
    assert result.status == WorkItemStatus.PLAN_AWAITING_APPROVAL
    assert result.repository_commit_sha == DUMMY_COMMIT_SHA
    assert result.plan is not None
    assert result.plan_approval.status == "pending"
    assert len(result.plan.steps) >= 1
    assert len(result.plan.evidence) >= 1
    assert result.plan.evidence[0].commit_sha == DUMMY_COMMIT_SHA


@pytest.mark.asyncio
async def test_generate_plan_api_route(session: AsyncSession) -> None:
    from app.api.deps import get_rate_limited_principal
    from app.core.security import Principal

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_rate_limited_principal] = lambda: Principal(subject="test-user")
    try:
        # Create active project & work item
        repo = Repository(
            id=uuid.uuid4(),
            owner_subject="test-user",
            github_full_name="org/repo",
            default_branch="main",
            github_installation_id=54321,
            connection_status=ProjectConnectionStatus.ACTIVE,
        )
        work_item = WorkItem(
            id=uuid.uuid4(),
            repository_id=repo.id,
            title="Add retry mechanism",
            description="Add automatic backoff retry logic for transient network failures.",
            kind=WorkItemKind.FEATURE,
            status=WorkItemStatus.DRAFT,
        )
        run = WorkRun(
            id=uuid.uuid4(),
            work_item_id=work_item.id,
            stage=RunStage.PLAN,
            status=RunStatus.QUEUED,
            is_current=True,
        )
        session.add_all([repo, work_item, run])
        await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}
            with patch("app.services.planning_worker.GitHubClient") as mock_cls:
                mock_inst = AsyncMock()
                mock_inst.get_default_branch_commit.return_value = ("main", DUMMY_COMMIT_SHA)
                mock_inst.get_repository_tree.return_value = [
                    {"path": "app/retry.py", "type": "blob", "sha": "4" * 40}
                ]
                mock_inst.get_file_content.return_value = "def retry(): pass"
                mock_cls.return_value = mock_inst

                resp = await client.post(
                    f"/api/v1/runs/{run.id}/generate-plan",
                    headers=headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "plan_awaiting_approval"
                assert data["plan_approval"]["status"] == "pending"
                assert data["plan"]["summary"] is not None
                assert len(data["plan"]["steps"]) > 0
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_rate_limited_principal, None)


@pytest.mark.asyncio
async def test_sync_github_pull_request_for_run_is_non_destructive_and_idempotent(
    session: AsyncSession,
) -> None:
    from app.domain.workflow import ApprovalAction, ApprovalDecision
    from app.models.workflow import Approval
    from app.services.workflow import WorkflowService

    artifact_sha = "b" * 64
    repo = Repository(
        id=uuid.uuid4(),
        owner_subject="test-user",
        github_full_name="org/repo",
        default_branch="main",
        github_installation_id=12345,
        connection_status=ProjectConnectionStatus.ACTIVE,
    )
    work_item = WorkItem(
        id=uuid.uuid4(),
        repository_id=repo.id,
        title="Fix CI database init",
        description="Verify non-destructive draft PR creation after Gate 2 approval.",
        kind=WorkItemKind.BUG,
        status=WorkItemStatus.PR_AWAITING_APPROVAL,
        base_commit_sha=DUMMY_COMMIT_SHA,
    )
    run = WorkRun(
        id=uuid.uuid4(),
        work_item_id=work_item.id,
        stage=RunStage.PLAN,
        status=RunStatus.SUCCEEDED,
        is_current=True,
        base_commit_sha=DUMMY_COMMIT_SHA,
        approval_artifact_sha256=artifact_sha,
    )
    approval = Approval(
        id=uuid.uuid4(),
        run_id=run.id,
        action=ApprovalAction.PULL_REQUEST,
        decision=ApprovalDecision.APPROVED,
        actor_subject="test-user",
        pinned_commit_sha=DUMMY_COMMIT_SHA,
        artifact_sha256=artifact_sha,
    )
    session.add_all([repo, work_item, run, approval])
    await session.commit()

    mock_gh = AsyncMock(spec=GitHubClient)
    mock_gh.create_branch.return_value = f"codexforge/fix-ci-database-init-{run.id.hex[:6]}"
    mock_gh.create_or_update_file.return_value = {
        "content": {"path": f".codexforge/runs/{run.id}.md"}
    }
    mock_gh.create_pull_request.return_value = {
        "number": 42,
        "url": "https://github.com/org/repo/pull/42",
        "branch_name": f"codexforge/fix-ci-database-init-{run.id.hex[:6]}",
    }

    service = WorkflowService(session)
    first = await service.sync_github_pull_request_for_run(
        run.id,
        actor_subject="test-user",
        correlation_id="corr-pr-1",
        github_client=mock_gh,
    )
    assert first.pull_request == {
        "number": 42,
        "url": "https://github.com/org/repo/pull/42",
        "branch_name": f"codexforge/fix-ci-database-init-{run.id.hex[:6]}",
    }
    mock_gh.create_or_update_file.assert_awaited_once()
    assert (
        mock_gh.create_or_update_file.await_args.kwargs["path"] == f".codexforge/runs/{run.id}.md"
    )
    mock_gh.create_pull_request.assert_awaited_once()
    assert mock_gh.create_pull_request.await_args.kwargs["draft"] is True

    # Calling sync again must be idempotent and not issue duplicate GitHub writes.
    second = await service.sync_github_pull_request_for_run(
        run.id,
        actor_subject="test-user",
        correlation_id="corr-pr-2",
        github_client=mock_gh,
    )
    assert second.pull_request == first.pull_request
    mock_gh.create_branch.assert_awaited_once()
    mock_gh.create_or_update_file.assert_awaited_once()
    mock_gh.create_pull_request.assert_awaited_once()
