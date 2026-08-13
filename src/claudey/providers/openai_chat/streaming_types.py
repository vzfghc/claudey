"""Structural collaborator boundaries for OpenAI-chat streaming."""

from collections.abc import Iterator
from typing import Any, Protocol

from claudey.core.anthropic.models import MessagesRequest
from claudey.core.anthropic.streaming import AnthropicStreamLedger
from claudey.core.reasoning import ReasoningPolicy
from claudey.providers.admission import (
    ProviderAdmissionController,
    ProviderAttempt,
    ProviderRetrySession,
)
from claudey.providers.base import ProviderConfig
from claudey.providers.failure_policy import ProviderFailureOverride


class OpenAIChatStreamProfile(Protocol):
    """Profile members read by the streaming runner."""

    @property
    def structured_reasoning_details(self) -> bool: ...

    def reasoning_delta(self, delta: Any) -> str | None: ...


class OpenAIChatProviderProtocol(Protocol):
    """Complete provider collaborator surface used by the streaming runner."""

    @property
    def _admission(self) -> ProviderAdmissionController: ...

    @property
    def _config(self) -> ProviderConfig: ...

    @property
    def _profile(self) -> OpenAIChatStreamProfile: ...

    @property
    def _provider_name(self) -> str: ...

    @property
    def _provider_failure_override(self) -> ProviderFailureOverride: ...

    def _record_tool_call_extra_content(
        self, tool_call_id: str, extra_content: dict[str, Any]
    ) -> None: ...

    def _build_request_body(
        self, request: MessagesRequest, *, reasoning: ReasoningPolicy
    ) -> dict[str, Any]: ...

    async def _create_stream(
        self, body: dict[str, Any], retry_session: ProviderRetrySession
    ) -> tuple[Any, dict[str, Any], ProviderAttempt]: ...

    def _tool_argument_aliases(
        self, body: dict[str, Any]
    ) -> dict[str, dict[str, str]]: ...

    def _handle_extra_reasoning(
        self, delta: Any, ledger: AnthropicStreamLedger, *, output_reasoning: bool
    ) -> Iterator[str]: ...

    def _log_stream_transport_error(
        self,
        tag: str,
        req_tag: str,
        error: Exception,
        *,
        request_id: str | None,
    ) -> None: ...

    def _anthropic_usage_fields(self, usage_info: Any) -> dict[str, int]: ...
