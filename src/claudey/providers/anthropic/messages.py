"""Anthropic Messages API passthrough for user-defined compatible endpoints.

The Admin "Anthropic-compatible" custom provider type speaks the real Anthropic
wire protocol (``/v1/messages`` with ``x-api-key`` + ``anthropic-version``) to an
arbitrary base URL the user supplies (e.g. MiniMax's ``/anthropic/v1`` gateway).
The request is serialized with the shared Anthropic message fields and streamed
upstream; the Anthropic-shaped SSE response is relayed to the gateway unchanged,
so no format translation is needed.
"""

import asyncio
import sys
from collections.abc import AsyncIterator

import httpx

from claudey.application.model_metadata import ProviderModelInfo
from claudey.core.anthropic import MessagesRequest
from claudey.core.anthropic.request_serialization import dump_messages_request
from claudey.core.anthropic.urls import ANTHROPIC_VERSION_HEADER, anthropic_messages_url
from claudey.core.reasoning import DEFAULT_REASONING_POLICY, ReasoningPolicy
from claudey.providers.admission import ProviderAdmissionController
from claudey.providers.base import BaseProvider, ProviderConfig
from claudey.providers.failure_policy import (
    classify_provider_failure,
    underlying_provider_error,
)
from claudey.providers.http import close_provider_stream
from claudey.providers.model_listing import extract_openai_model_infos

ANTHROPIC_COMPATIBLE_TAG = "ANTHROPIC_COMPATIBLE"


class AnthropicMessagesProvider(BaseProvider):
    """Talk Anthropic Messages wire to a user-defined compatible endpoint."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        admission: ProviderAdmissionController,
    ) -> None:
        super().__init__(config)
        self._admission = admission
        self._messages_url = anthropic_messages_url(config.base_url)
        self._provider_name = ANTHROPIC_COMPATIBLE_TAG
        headers: dict[str, str] = {
            "anthropic-version": ANTHROPIC_VERSION_HEADER,
            "accept": "text/event-stream",
        }
        if config.api_key:
            headers["x-api-key"] = config.api_key
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(
                config.http_read_timeout,
                connect=config.http_connect_timeout,
                read=config.http_read_timeout,
                write=config.http_write_timeout,
            ),
            proxy=config.proxy or None,
        )

    async def cleanup(self) -> None:
        """Release the upstream HTTP client."""
        await self._client.aclose()

    async def list_model_infos(self) -> frozenset[ProviderModelInfo]:
        """Return model metadata from the Anthropic-style ``/v1/models`` endpoint."""
        payload = await self._admission.run_with_retry(
            self._fetch_models_payload,
            provider_failure_override=None,
        )
        return extract_openai_model_infos(
            payload.json(), provider_name=self._provider_name
        )

    async def _fetch_models_payload(self) -> httpx.Response:
        response = await self._client.get(self._models_url())
        response.raise_for_status()
        return response

    def _models_url(self) -> str:
        value = self._messages_url
        if value.endswith("/messages"):
            return value[: -len("/messages")] + "/models"
        return value.rstrip("/") + "/models"

    def preflight_stream(
        self,
        request: MessagesRequest,
        *,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> None:
        """Validate Anthropic request serialization before opening a stream."""
        self._build_body(request)

    def _build_body(self, request: MessagesRequest) -> dict[str, object]:
        body = dump_messages_request(request)
        body["stream"] = True
        body["model"] = request.model
        extra_body = body.pop("extra_body", None)
        if isinstance(extra_body, dict):
            body.update(extra_body)
        return body

    def stream_response(
        self,
        request: MessagesRequest,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        response_model: str | None = None,
        reasoning: ReasoningPolicy = DEFAULT_REASONING_POLICY,
    ) -> AsyncIterator[str]:
        """Stream the Anthropic SSE response from the compatible endpoint."""
        return self._stream(request, request_id=request_id)

    async def _stream(
        self,
        request: MessagesRequest,
        *,
        request_id: str | None,
    ) -> AsyncIterator[str]:
        body = self._build_body(request)
        req_tag = f" request_id={request_id}" if request_id else ""
        retry_session = self._admission.new_retry_session(request_id=request_id)
        while retry_session.can_attempt:
            attempt = await self._admission.open_attempt(retry_session)
            stream: httpx.Response | None = None
            started = False
            try:
                request_obj = self._client.build_request(
                    "POST",
                    self._messages_url,
                    json=body,
                )
                stream = await self._client.send(request_obj, stream=True)
                if stream.status_code >= 400:
                    await stream.aread()
                    raise httpx.HTTPStatusError(
                        f"Anthropic-compatible provider returned {stream.status_code}",
                        request=request_obj,
                        response=stream,
                    )
                await attempt.succeeded()
                started = True
                async for text in stream.aiter_text():
                    yield text
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                should_retry = False
                if attempt is not None and not attempt.accepted:
                    should_retry = await attempt.retry(error)
                if not started and should_retry and retry_session.can_attempt:
                    continue
                reported_error = underlying_provider_error(error)
                self._log_stream_transport_error(
                    ANTHROPIC_COMPATIBLE_TAG,
                    req_tag,
                    reported_error,
                    request_id=request_id,
                )
                failure = classify_provider_failure(
                    reported_error,
                    provider_name=self._provider_name,
                    read_timeout_s=self._config.http_read_timeout,
                    request_id=request_id,
                )
                raise failure from error
            finally:
                if stream is not None:
                    await close_provider_stream(
                        stream,
                        active_error=sys.exception(),
                        provider_name=self._provider_name,
                        request_id=request_id,
                    )
                if attempt is not None:
                    await attempt.aclose()
        raise RuntimeError("provider retry session exhausted without a final error")
