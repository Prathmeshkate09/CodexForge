from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workflow import Approval, AuditEvent, Repository, WorkItem, WorkRun


class WorkflowRepository:
    """Ownership-scoped database access for the approval-first workflow."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project(self, project_id: uuid.UUID, actor_subject: str) -> Repository | None:
        result = await self._session.execute(
            select(Repository).where(
                Repository.id == project_id, Repository.owner_subject == actor_subject
            )
        )
        return result.scalar_one_or_none()

    async def list_projects(self, actor_subject: str) -> Sequence[Repository]:
        result = await self._session.execute(
            select(Repository)
            .where(Repository.owner_subject == actor_subject)
            .order_by(Repository.created_at.desc())
        )
        return result.scalars().all()

    async def get_project_by_name(
        self, actor_subject: str, github_full_name: str
    ) -> Repository | None:
        result = await self._session.execute(
            select(Repository).where(
                Repository.owner_subject == actor_subject,
                Repository.github_full_name == github_full_name,
            )
        )
        return result.scalar_one_or_none()

    async def get_work_item(
        self,
        work_item_id: uuid.UUID,
        actor_subject: str,
        *,
        for_update: bool = False,
    ) -> WorkItem | None:
        query = (
            select(WorkItem)
            .join(WorkItem.repository)
            .where(WorkItem.id == work_item_id, Repository.owner_subject == actor_subject)
        )
        if for_update:
            query = query.execution_options(populate_existing=True).with_for_update(of=WorkItem)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_work_items(
        self, actor_subject: str, project_id: uuid.UUID | None = None
    ) -> Sequence[WorkItem]:
        query: Select[tuple[WorkItem]] = (
            select(WorkItem)
            .join(WorkItem.repository)
            .where(Repository.owner_subject == actor_subject)
            .order_by(WorkItem.created_at.desc())
        )
        if project_id is not None:
            query = query.where(WorkItem.repository_id == project_id)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_run(
        self,
        run_id: uuid.UUID,
        actor_subject: str,
        *,
        for_update: bool = False,
    ) -> WorkRun | None:
        query = (
            select(WorkRun)
            .join(WorkRun.work_item)
            .join(WorkItem.repository)
            .options(selectinload(WorkRun.work_item).selectinload(WorkItem.repository))
            .where(WorkRun.id == run_id, Repository.owner_subject == actor_subject)
        )
        if for_update:
            query = query.execution_options(populate_existing=True).with_for_update(of=WorkRun)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_approval(self, run_id: uuid.UUID, action: str) -> Approval | None:
        result = await self._session.execute(
            select(Approval).where(Approval.run_id == run_id, Approval.action == action)
        )
        return result.scalar_one_or_none()

    async def list_approvals(self, run_id: uuid.UUID) -> Sequence[Approval]:
        result = await self._session.execute(select(Approval).where(Approval.run_id == run_id))
        return result.scalars().all()

    async def list_audit_events(self, entity_ids: list[uuid.UUID]) -> Sequence[AuditEvent]:
        result = await self._session.execute(
            select(AuditEvent)
            .where(AuditEvent.entity_id.in_(entity_ids))
            .order_by(AuditEvent.created_at.asc())
        )
        return result.scalars().all()

    def add_audit_event(
        self,
        *,
        actor_subject: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        correlation_id: str,
        details: dict[str, object],
    ) -> AuditEvent:
        event = AuditEvent(
            actor_subject=actor_subject,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            details=details,
        )
        self._session.add(event)
        return event

    async def flush(self) -> None:
        await self._session.flush()

    @property
    def session(self) -> AsyncSession:
        return self._session
