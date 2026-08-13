"""Concrete OpenAI-compatible provider and per-request stream execution."""

import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from typing import Any

import httpx
from loguru import logger
from openai import AsyncOpenAI

from claudey.core.anthropic.models import MessagesRequest
from claudey.core.anthropic.streaming import (
    AnthropicStreamLedger,
)
from claudey.core.failures import ExecutionFailure
from claudey.core.model_metadata import ProviderModelInfo
from claudey.core.reasoning import DEFAULT_REASONING_POLICY, ReasoningPolicy
from claudey.providers.admission import (
    ProviderAdmissionController,
    ProviderAttempt,
    ProviderRetrySession,
)
from claudey.providers.base import BaseProvider, ProviderConfig
from claudey.providers.http import (
    close_provider_stream,
)
from claudey.providers.model_listing import extract_openai_model_infos

from .output_cap import clamp_output_tokens, parse_output_token_cap
from .profiles import OpenAIChatProfile
from .request_policy import build_openai_chat_request_body
from .streaming import OpenAIChatStreamRunner
from .usage import (
    clone_without_stream_usage,
    is_stream_usage_rejection,
)

OpenAIAsyncCredentialProvider = Callable[[], Awaitable[str]]


class OpenAIChatProvider(BaseProvider):
    """OpenAI-compatible ``/chat/completions`` provider configured by a profile."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        profile: OpenAIChatProfile,
        admission: ProviderAdmissionController,
        default_headers: Mapping[str, str] | None = None,
        api_key_provider: OpenAIAsyncCredentialProvider | None = None,
    ):
        super().__init__(config)
        self._profile = profile
        self._provider_name = profile.provider_name
        self._api_key = config.api_key
        self._base_url = profile.base_url(config.base_url).rstrip("/")
        # Learned per-model output-token caps from upstream 400 rejections, so
        # later requests clamp proactively instead of paying the 400 each time.
        self._model_output_caps: dict[str, int] = {}
        self._admission = admission
        http_client = None
        if config.proxy:
            http_client = httpx.AsyncClient(
                proxy=config.proxy,
                timeout=httpx.Timeout(
                    config.http_read_timeout,
                    connect=config.http_connect_timeout,
                    read=config.http_read_timeout,
                    write=config.http_write_timeout,
                ),
            )
        self._client = AsyncOpenAI(
            api_key=api_key_provider or self._api_key,
            base_url=self._base_url,
            max_retries=0,
            default_headers=default_headers,
            timeout=httpx.Timeout(
                config.http_read_timeout,
                connect=config.http_connect_timeout,
                read=config.http_read_timeout,
                write=config.http_write_timeout,
            ),
            http_client=http_client,
        )

    async def cleanup(self) -> None:
        """Release HTTP client resources."""
        client = getattr(self, "_client", None)
        if client is not None:
            await client.close()

    async def list_model_infos(self) -> frozenset[ProviderModelInfo]:
        """Return model metadata from the OpenAI-compatible models endpoint."""
        payload = await self._list_models_payload()
        if not self._profile.model_ids_are_routable:
            return frozenset()
        return extract_openai_model_infos(payload, provider_name=self._provider_name)

    async def _list_models_payload(self) -> Any:
        """Fetch one OpenAI-compatible model-list payload with shared retries."""
        payload = await self._admission.run_with_retry(
            self._client.models.list,
            provider_failure_override=self._provider_failure_override,
        )
        return payload

    def _build_request_body(
        self,
        request: MessagesRequest,
        *,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> dict[str, Any]:
        """Build a provider request from the immutable profile."""
        return build_openai_chat_request_body(
            request,
            reasoning=reasoning,
            policy=self._profile.request_policy,
            postprocessors=self._profile.request_postprocessors,
        )

    def preflight_stream(
        self,
        request: MessagesRequest,
        *,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> None:
        """Validate OpenAI-chat request conversion before streaming."""
        self._build_request_body(request, reasoning=reasoning)

    def _handle_extra_reasoning(
        self, delta: Any, ledger: AnthropicStreamLedger, *, output_reasoning: bool
    ) -> Iterator[str]:
        """Hook for provider-specific reasoning."""
        return iter(())

    def _get_retry_request_body(self, error: Exception, body: dict) -> dict | None:
        """Return a modified request body for one retry, or None."""
        return None

    def _provider_failure_override(self, error: Exception) -> ExecutionFailure | None:
        """Return provider-specific failure semantics, or defer to shared policy."""
        return None

    def _prepare_create_body(self, body: dict[str, Any]) -> dict[str, Any]:
        """Return the body passed to the upstream OpenAI-compatible client."""
        return body

    def _record_tool_call_extra_content(
        self, tool_call_id: str, extra_content: dict[str, Any]
    ) -> None:
        """Hook for providers that must replay OpenAI tool-call metadata later."""

    def _tool_argument_aliases(self, body: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Return provider-specific per-tool argument aliases for this request."""
        return {}

    def _anthropic_usage_fields(self, usage_info: Any) -> dict[str, int]:
        """Return provider-specific Anthropic usage fields for final SSE usage."""
        return {}

    async def _create_stream(
        self,
        body: dict,
        retry_session: ProviderRetrySession,
    ) -> tuple[Any, dict, ProviderAttempt]:
        """Create a streaming chat completion with bounded request fallbacks."""
        body = self._apply_learned_output_cap(body)
        used_retry_kinds: set[str] = set()

        while retry_session.can_attempt:
            attempt = await self._admission.open_attempt(retry_session)
            stream: Any | None = None
            retain_attempt = False
            try:
                create_body = self._prepare_create_body(body)
                stream = await self._client.chat.completions.create(
                    **create_body,
                    stream=True,
                )
                stream = self._normalize_stream(stream, body)
                retain_attempt = True
                return stream, body, attempt
            except asyncio.CancelledError:
                raise
            except Exception as error:
                retry_body = self._next_create_retry_body(error, body, used_retry_kinds)
                if retry_body is not None and retry_session.can_attempt:
                    await attempt.retry_immediately()
                    body = retry_body
                    continue
                should_retry = await attempt.retry(
                    error,
                    provider_failure_override=self._provider_failure_override,
                )
                if not should_retry:
                    raise
            finally:
                if not retain_attempt:
                    if stream is not None:
                        await close_provider_stream(
                            stream,
                            active_error=sys.exception(),
                            provider_name=self._provider_name,
                            request_id=retry_session.request_id,
                        )
                    await attempt.aclose()

        raise RuntimeError("provider retry session exhausted without a final error")

    def _normalize_stream(self, stream: Any, _body: Mapping[str, Any]) -> Any:
        """Return the provider-specific stream view consumed by the base runner."""
        return stream

    def _next_create_retry_body(
        self,
        error: Exception,
        body: dict,
        used_retry_kinds: set[str],
    ) -> dict | None:
        retry_body = self._retry_body_for_output_cap(error, body)
        if retry_body is not None:
            return retry_body

        if "stream_usage" not in used_retry_kinds and is_stream_usage_rejection(error):
            retry_body = clone_without_stream_usage(body)
            if retry_body is not None:
                used_retry_kinds.add("stream_usage")
                logger.warning(
                    "{}_STREAM: retrying without stream_options.include_usage "
                    "after upstream rejection",
                    self._provider_name,
                )
                return retry_body

        if "provider_specific" not in used_retry_kinds:
            retry_body = self._get_retry_request_body(error, body)
            if retry_body is not None:
                used_retry_kinds.add("provider_specific")
                return retry_body

        return None

    def _apply_learned_output_cap(self, body: dict) -> dict:
        """Clamp output tokens to a previously learned cap for this model."""
        model = body.get("model")
        if not isinstance(model, str):
            return body
        cap = self._model_output_caps.get(model)
        if cap is None:
            return body
        clamped = clamp_output_tokens(body, cap)
        return clamped if clamped is not None else body

    def _retry_body_for_output_cap(self, error: Exception, body: dict) -> dict | None:
        """Learn an upstream output-token cap from a 400 and clamp for one retry."""
        cap = parse_output_token_cap(error)
        if cap is None:
            return None
        model = body.get("model")
        if isinstance(model, str):
            previous = self._model_output_caps.get(model)
            cap = cap if previous is None else min(previous, cap)
            self._model_output_caps[model] = cap
        clamped = clamp_output_tokens(body, cap)
        if clamped is None:
            return None
        logger.warning(
            "{}_STREAM: clamping output tokens to {} after upstream cap rejection",
            self._provider_name,
            cap,
        )
        return clamped

    def stream_response(
        self,
        request: MessagesRequest,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        response_model: str | None = None,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> AsyncIterator[str]:
        """Stream response in Anthropic SSE format."""
        runner = OpenAIChatStreamRunner(
            self,
            request=request,
            input_tokens=input_tokens,
            request_id=request_id,
            response_model=response_model,
            reasoning=reasoning,
        )
        return runner.run()
