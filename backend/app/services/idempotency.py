from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models.workflow import IdempotencyRecord

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")


@dataclass(frozen=True)
class IdempotencyReservation:
    record: IdempotencyRecord
    replayed_response: tuple[int, dict[str, Any]] | None = None


class IdempotencyService:
    """Stores a per-user request fingerprint and safe completed response for 24 hours."""

    _TTL = timedelta(hours=24)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def validate_key(key: str | None) -> str:
        if key is None or not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise ConflictError(
                "Idempotency-Key must be 16-128 characters and use only letters, digits, "
                "'.', '_', ':', or '-'."
            )
        return key

    @staticmethod
    def request_hash(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def reserve(
        self,
        *,
        actor_subject: str,
        scope: str,
        key: str,
        payload: Any,
    ) -> IdempotencyReservation:
        key = self.validate_key(key)
        fingerprint = self.request_hash(payload)
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.actor_subject == actor_subject,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.key == key,
            )
            .with_for_update()
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return await self._reuse_or_replay_existing(existing, fingerprint=fingerprint, now=now)

        record = IdempotencyRecord(
            actor_subject=actor_subject,
            scope=scope,
            key=key,
            request_hash=fingerprint,
            expires_at=now + self._TTL,
        )
        self._session.add(record)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # This reservation precedes workflow mutations, so rollback cannot discard durable work.
            await self._session.rollback()
            concurrent_result = await self._session.execute(
                select(IdempotencyRecord)
                .where(
                    IdempotencyRecord.actor_subject == actor_subject,
                    IdempotencyRecord.scope == scope,
                    IdempotencyRecord.key == key,
                )
                .with_for_update()
            )
            concurrent = concurrent_result.scalar_one_or_none()
            if concurrent is None:
                raise ConflictError(
                    "Idempotency-Key reservation could not be completed safely."
                ) from exc
            return await self._reuse_or_replay_existing(
                concurrent,
                fingerprint=fingerprint,
                now=datetime.now(UTC),
            )
        return IdempotencyReservation(record)

    async def complete(
        self,
        reservation: IdempotencyReservation,
        *,
        status_code: int,
        response_body: dict[str, Any],
    ) -> None:
        reservation.record.response_status = status_code
        reservation.record.response_body = response_body
        await self._session.flush()

    async def _reuse_or_replay_existing(
        self,
        record: IdempotencyRecord,
        *,
        fingerprint: str,
        now: datetime,
    ) -> IdempotencyReservation:
        if self._is_expired(record.expires_at, now):
            # Reusing the same row preserves the unique-key lock; an expired key is a new request.
            record.request_hash = fingerprint
            record.response_status = None
            record.response_body = None
            record.expires_at = now + self._TTL
            await self._session.flush()
            return IdempotencyReservation(record)
        if record.request_hash != fingerprint:
            raise ConflictError("Idempotency-Key was already used for a different request.")
        if record.response_status is not None and record.response_body is not None:
            return IdempotencyReservation(record, (record.response_status, record.response_body))
        raise ConflictError("A request with this Idempotency-Key is still being processed.")

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime) -> bool:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= now
