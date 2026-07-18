from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.services.idempotency import IdempotencyService


@pytest.mark.asyncio
async def test_completed_idempotency_key_replays_only_the_same_request(
    session: AsyncSession,
) -> None:
    service = IdempotencyService(session)
    key = "a" * 16
    first = await service.reserve(
        actor_subject="user-1",
        scope="work-items.create",
        key=key,
        payload={"title": "Fix CI"},
    )
    await service.complete(first, status_code=201, response_body={"id": "work-item-1"})
    await session.commit()

    replay = await service.reserve(
        actor_subject="user-1",
        scope="work-items.create",
        key=key,
        payload={"title": "Fix CI"},
    )
    assert replay.replayed_response == (201, {"id": "work-item-1"})

    with pytest.raises(ConflictError, match="different request"):
        await service.reserve(
            actor_subject="user-1",
            scope="work-items.create",
            key=key,
            payload={"title": "Different"},
        )


@pytest.mark.asyncio
async def test_expired_idempotency_key_is_reused_as_a_new_request(
    session: AsyncSession,
) -> None:
    service = IdempotencyService(session)
    key = "b" * 16
    original = await service.reserve(
        actor_subject="user-1",
        scope="projects.create",
        key=key,
        payload={"repository": "acme/old"},
    )
    await service.complete(original, status_code=201, response_body={"id": "old-project"})
    original.record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    fresh = await service.reserve(
        actor_subject="user-1",
        scope="projects.create",
        key=key,
        payload={"repository": "acme/new"},
    )
    assert fresh.replayed_response is None
    assert fresh.record.id == original.record.id
    assert fresh.record.response_body is None
    assert fresh.record.response_status is None
    assert fresh.record.request_hash == service.request_hash({"repository": "acme/new"})
