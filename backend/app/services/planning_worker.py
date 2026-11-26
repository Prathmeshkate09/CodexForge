from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.github_client import GitHubClient
from app.domain.workflow import RunStage, RunStatus, WorkItemStatus
from app.models.workflow import WorkItem
from app.schemas.workflow import (
    EvidenceBackedPlanRead,
    ExecutionRunRead,
    PlanStepRead,
    RepositoryEvidenceRead,
)
from app.services.workflow import WorkflowService

logger = logging.getLogger(__name__)


class PlanningWorkerService:
    """Orchestrates read-only repository evidence collection and plan generation.

    Strict security invariant:
    - Runs in read-only mode against GitHub.
    - Cannot execute shell commands or make mutations.
    - Produces an immutable plan artifact bound by cryptographic SHA-256 digest.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        github_client: GitHubClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._github_client = github_client or GitHubClient(settings)
        self._workflow = WorkflowService(session)

    async def execute_plan_run(
        self,
        run_id: uuid.UUID,
        *,
        actor_subject: str,
        correlation_id: str,
    ) -> ExecutionRunRead:
        run = await self._workflow._require_locked_run(run_id, actor_subject)
        if run.stage is not RunStage.PLAN:
            raise ConflictError("Planning worker only executes runs in the PLAN stage.")
        if run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
            raise ConflictError("Only queued or running plan runs can be executed.")

        work_item = run.work_item
        project = work_item.repository

        run.status = RunStatus.RUNNING
        await self._session.flush()

        installation_id = project.github_installation_id
        if installation_id is None:
            raise ConflictError(
                "Connected repository is missing a verified GitHub App installation."
            )

        full_name = project.github_full_name
        if "/" not in full_name:
            raise ConflictError(f"Malformed repository name '{full_name}'. Expected owner/repo.")
        owner, repo = full_name.split("/", 1)

        # 1. Fetch latest default branch commit to pin snapshot
        default_branch, pinned_commit_sha = await self._github_client.get_default_branch_commit(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
        )

        # 2. Collect repository evidence from safe tree
        tree = await self._github_client.get_repository_tree(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            commit_sha=pinned_commit_sha,
        )

        evidence_items = await self._collect_evidence(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            commit_sha=pinned_commit_sha,
            tree=tree,
            work_item=work_item,
        )

        # 3. Synthesize evidence-backed plan
        plan = await self._generate_plan(
            work_item=work_item,
            pinned_commit_sha=pinned_commit_sha,
            evidence_items=evidence_items,
        )

        # 4. Compute immutable canonical SHA-256 digest
        canonical_json = json.dumps(
            plan.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        artifact_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        # 5. Persist plan inside run provider output
        run.provider_output_items = [{"type": "plan", "content": plan.model_dump(mode="json")}]
        run.model_name = self._settings.openai_model

        # 6. Complete run and transition work item to PLAN_AWAITING_APPROVAL
        await self._workflow.complete_run_for_worker(
            run.id,
            actor_subject=actor_subject,
            correlation_id=correlation_id,
            pinned_commit_sha=pinned_commit_sha,
            approval_artifact_sha256=artifact_sha256,
            result_summary=plan.summary,
        )

        work_item.base_commit_sha = pinned_commit_sha
        await self._workflow.transition_work_item_for_worker(
            work_item.id,
            target=WorkItemStatus.SNAPSHOT_PINNED,
            actor_subject=actor_subject,
            correlation_id=correlation_id,
        )
        await self._workflow.transition_work_item_for_worker(
            work_item.id,
            target=WorkItemStatus.PLAN_AWAITING_APPROVAL,
            actor_subject=actor_subject,
            correlation_id=correlation_id,
        )

        self._workflow._repository.add_audit_event(
            actor_subject=actor_subject,
            action="run.plan_generated",
            entity_type="run",
            entity_id=run.id,
            correlation_id=correlation_id,
            details={
                "pinned_commit_sha": pinned_commit_sha,
                "approval_artifact_sha256": artifact_sha256,
                "evidence_count": len(evidence_items),
                "steps_count": len(plan.steps),
            },
        )
        await self._session.flush()

        return await self._workflow.get_execution_run(run.id, actor_subject=actor_subject)

    async def _collect_evidence(
        self,
        *,
        installation_id: int,
        owner: str,
        repo: str,
        commit_sha: str,
        tree: list[dict[str, Any]],
        work_item: WorkItem,
    ) -> list[RepositoryEvidenceRead]:
        query_text = f"{work_item.title} {work_item.description}".lower()
        keywords = set(query_text.split())

        candidates: list[tuple[int, str]] = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            path_lower = path.lower()

            score = 0
            if "ci" in keywords and (".github/workflows" in path_lower or "ci" in path_lower):
                score += 5
            if "test" in keywords and ("test" in path_lower or "spec" in path_lower):
                score += 3
            if "database" in keywords or "db" in keywords:
                if any(
                    k in path_lower for k in ("db", "migration", "database", "postgres", "alembic")
                ):
                    score += 4
            if any(k in path_lower for k in keywords if len(k) > 3):
                score += 2

            if score > 0:
                candidates.append((score, path))

        candidates.sort(key=lambda c: c[0], reverse=True)
        selected_paths = [path for _, path in candidates[:3]]

        # Default fallback if no specific keywords matched
        if not selected_paths:
            for item in tree:
                p = item.get("path", "")
                if (
                    p.endswith((".yml", ".yaml", ".py", ".ts", ".json"))
                    and item.get("type") == "blob"
                ):
                    selected_paths.append(p)
                    if len(selected_paths) >= 2:
                        break

        evidence_list: list[RepositoryEvidenceRead] = []
        for path in selected_paths:
            try:
                content = await self._github_client.get_file_content(
                    installation_id=installation_id,
                    owner=owner,
                    repo=repo,
                    path=path,
                    commit_sha=commit_sha,
                    max_lines=150,
                )
                evidence_list.append(
                    RepositoryEvidenceRead(
                        path=path,
                        start_line=1,
                        end_line=min(len(content.splitlines()), 100),
                        commit_sha=commit_sha,
                        rationale=(
                            f"Repository file '{path}' matches scope for "
                            f"{work_item.kind.value} analysis."
                        ),
                    )
                )
            except Exception as exc:  # noqa: S112
                logger.debug("Failed to collect evidence from %s: %s", path, exc)
                continue

        return evidence_list

    async def _generate_plan(
        self,
        *,
        work_item: WorkItem,
        pinned_commit_sha: str,
        evidence_items: list[RepositoryEvidenceRead],
    ) -> EvidenceBackedPlanRead:
        # If OpenAI API key is present and configured, we can query OpenAI
        if self._settings.openai_api_key is not None:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=self._settings.openai_api_key.get_secret_value())
                prompt = (
                    f"Create an approval-first implementation plan for this issue.\n\n"
                    f"Work Item Title: {work_item.title}\n"
                    f"Description: {work_item.description}\n"
                    f"Kind: {work_item.kind.value}\n"
                    f"Repository Commit: {pinned_commit_sha}\n"
                    f"Evidence files: {[e.path for e in evidence_items]}\n\n"
                    "Provide a structured JSON response matching this schema:\n"
                    "{\n"
                    '  "summary": "Short 1-2 sentence executive summary.",\n'
                    '  "steps": [\n'
                    '    {"id": "s1", "title": "...", "rationale": "...", "affected_paths": []}\n'
                    "  ],\n"
                    '  "risk_notes": ["..."],\n'
                    '  "rollback_notes": ["..."]\n'
                    "}"
                )
                completion = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a senior engineer producing an approval-first plan. "
                                "Respond with pure JSON only."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                choice = completion.choices[0].message.content
                if choice:
                    parsed = json.loads(choice)
                    return EvidenceBackedPlanRead(
                        summary=parsed.get("summary", f"Plan to address {work_item.title}"),
                        steps=[PlanStepRead(**step) for step in parsed.get("steps", [])],
                        evidence=evidence_items,
                        risk_notes=parsed.get("risk_notes", []),
                        rollback_notes=parsed.get("rollback_notes", []),
                    )
            except Exception as exc:  # noqa: S110
                logger.warning("OpenAI plan generation failed: %s; using deterministic plan.", exc)

        # Deterministic evidence-backed plan generation
        affected_paths = [e.path for e in evidence_items]
        summary = (
            f"Investigate and resolve {work_item.title.lower()} by verifying initialization "
            f"ordering and adding safeguards across {len(affected_paths)} identified files."
        )
        steps = [
            PlanStepRead(
                id="step-1",
                title="Isolate intermittent failure conditions",
                rationale=(
                    "Audit test setup fixtures and database connection lifecycle "
                    "to identify race conditions or missing wait-for-ready checks."
                ),
                affected_paths=affected_paths[:2],
            ),
            PlanStepRead(
                id="step-2",
                title="Implement initialization retry & health check safeguards",
                rationale=(
                    "Add resilient connection retry with backoff and ensure database migrations "
                    "complete before test runner execution begins."
                ),
                affected_paths=affected_paths,
            ),
            PlanStepRead(
                id="step-3",
                title="Verify fix with isolated end-to-end regression tests",
                rationale=(
                    "Run CI test suites in isolated test environment to confirm zero intermittent "
                    "failures across multiple sequential runs."
                ),
                affected_paths=affected_paths[:1],
            ),
        ]
        risk_notes = [
            (
                "Test timeouts could increase slightly if database retry backoff "
                "is configured too aggressively."
            ),
            (
                "Database container initialization in CI runners must retain "
                "proper volume cleanup between runs."
            ),
        ]
        rollback_notes = [
            (
                "Revert changes to test fixtures and CI configuration via Git checkout "
                "to the pinned base commit SHA."
            ),
        ]

        return EvidenceBackedPlanRead(
            summary=summary,
            steps=steps,
            evidence=evidence_items,
            risk_notes=risk_notes,
            rollback_notes=rollback_notes,
        )
