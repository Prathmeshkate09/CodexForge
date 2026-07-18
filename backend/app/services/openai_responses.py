from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from openai import AsyncOpenAI
from openai.types.responses import ResponseInputParam, ToolParam
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.core.security import safety_identifier


class ResponsesProviderRequest(BaseModel):
    """A server-only request boundary for the OpenAI Responses API."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject: str = Field(min_length=1, max_length=255)
    input_items: list[dict[str, Any]]
    tools: list[dict[str, Any]] = Field(default_factory=list)
    previous_response_id: str | None = None


class ResponsesProviderResult(BaseModel):
    response_id: str
    # Raw output stays in the active tool loop; the worker redacts before persistence.
    output_items: list[dict[str, Any]]
    tool_call_ids: list[str]


class ResponsesProvider(Protocol):
    async def create(self, request: ResponsesProviderRequest) -> ResponsesProviderResult: ...


class OpenAIResponsesProvider:
    """Server-only Responses API adapter that never exposes API keys through HTTP DTOs."""

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise RuntimeError(
                "CODEXFORGE_OPENAI_API_KEY is required before starting an AI workflow worker."
            )
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    async def create(self, request: ResponsesProviderRequest) -> ResponsesProviderResult:
        try:
            response = await self._client.responses.create(
                model=self._settings.openai_model,
                input=cast(ResponseInputParam, request.input_items),
                tools=cast(list[ToolParam], request.tools),
                previous_response_id=request.previous_response_id,
                safety_identifier=safety_identifier(request.subject, self._settings),
            )
        except Exception as exc:  # Provider details are never exposed to API callers.
            raise ServiceUnavailableError("The AI provider is temporarily unavailable.") from exc

        output_items = [_model_to_dict(item) for item in response.output]
        return ResponsesProviderResult(
            response_id=response.id,
            output_items=output_items,
            tool_call_ids=_tool_call_ids(output_items),
        )


def _model_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        dumped = item.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if isinstance(item, Mapping):
        return dict(item)
    raise TypeError("The Responses API returned an unsupported output item.")


def _tool_call_ids(items: Sequence[Mapping[str, Any]]) -> list[str]:
    identifiers: list[str] = []
    for item in items:
        call_id = item.get("call_id")
        if isinstance(call_id, str):
            identifiers.append(call_id)
    return identifiers


def redact_provider_output_items(
    items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Create bounded audit metadata while retaining tool-loop identifiers."""

    redacted: list[dict[str, Any]] = []
    for item in items:
        retained: dict[str, Any] = {}
        for key in ("id", "type", "status", "name", "call_id"):
            value = item.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                retained[key] = value
        redacted.append(retained)
    return redacted
