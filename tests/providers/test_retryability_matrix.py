"""Pinned retryability matrix for the unified classifier (refactor Sprint 3).

Every exception family appearing in either pre-merge decision table
(``is_retryable_provider_error`` / the pre-merge stream-recovery classifier) is asserted
in BOTH execution contexts: the provider-retry context (admission-level
retries and post-retry classification) and the stream-recovery context.
The table was written first and passed against the pre-merge code; it pins
today's decisions, including the deliberate context divergences:
- the stream context omits the write-family transport variants
  (``httpx.WriteError``, ``httpx.WriteTimeout``, ``httpx.PoolTimeout``,
  ``httpx.ConnectTimeout``) and only recognizes ``httpx.ReadTimeout``;
- the stream context short-circuits only authentication and bad-request
  errors, so a permission error carrying a retryable body stays retryable
  there while the provider context rejects it before body inspection.
"""

from collections.abc import Callable
from dataclasses import dataclass

import httpx
import openai
import pytest

from claudey.core.failures import ExecutionFailure, FailureKind
from claudey.providers.failure_policy import (
    ProviderRecoveryExhausted,
    RetryableProviderProtocolError,
    RetryableToolProtocolError,
    is_retryable_error,
    is_retryable_provider_error,
)
from claudey.providers.stream_recovery import TruncatedProviderStreamError


def _openai_status_error(
    error_type: type[openai.APIStatusError],
    *,
    status_code: int,
    body: object | None = None,
) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://provider.test/messages")
    return error_type(
        "upstream error",
        response=httpx.Response(status_code, request=request),
        body=body if body is not None else {"error": {"message": "upstream error"}},
    )


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://provider.test/messages")
    return httpx.HTTPStatusError(
        "upstream error",
        request=request,
        response=httpx.Response(status_code, request=request),
    )


def _transport_error(error_type: type[httpx.TransportError]) -> httpx.TransportError:
    return error_type(
        "transport failure",
        request=httpx.Request("POST", "https://provider.test/messages"),
    )


def _openai_request() -> httpx.Request:
    return httpx.Request("POST", "https://provider.test/messages")


@dataclass(frozen=True, slots=True)
class _RetryabilityCase:
    name: str
    error: Callable[[], BaseException]
    provider_retryable: bool
    stream_retryable: bool


_CASES: tuple[_RetryabilityCase, ...] = (
    _RetryabilityCase(
        "provider_recovery_exhausted",
        lambda: ProviderRecoveryExhausted(RuntimeError("upstream failed")),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "execution_failure_retryable",
        lambda: ExecutionFailure(
            kind=FailureKind.RATE_LIMIT,
            status_code=429,
            message="rate limited",
            retryable=True,
        ),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "execution_failure_non_retryable",
        lambda: ExecutionFailure(
            kind=FailureKind.INVALID_REQUEST,
            status_code=400,
            message="invalid request",
            retryable=False,
        ),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "openai_authentication_error",
        lambda: _openai_status_error(openai.AuthenticationError, status_code=401),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "openai_permission_denied",
        lambda: _openai_status_error(openai.PermissionDeniedError, status_code=403),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "openai_permission_denied_with_retryable_body",
        lambda: _openai_status_error(
            openai.PermissionDeniedError,
            status_code=403,
            body={"status": 429, "message": "quota exhausted"},
        ),
        provider_retryable=False,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_bad_request",
        lambda: _openai_status_error(openai.BadRequestError, status_code=400),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "openai_rate_limit",
        lambda: _openai_status_error(openai.RateLimitError, status_code=429),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_internal_server_error",
        lambda: _openai_status_error(openai.InternalServerError, status_code=500),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_api_timeout",
        lambda: openai.APITimeoutError(request=_openai_request()),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_api_connection_error",
        lambda: openai.APIConnectionError(request=_openai_request()),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_statusless_api_error_with_retryable_body",
        lambda: openai.APIError(
            "embedded failure",
            request=_openai_request(),
            body={"error": {"message": "internal failure", "code": 500}},
        ),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "openai_statusless_api_error_bare",
        lambda: openai.APIError("plain failure", request=_openai_request(), body=None),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_timeout_exception",
        lambda: _transport_error(httpx.TimeoutException),
        provider_retryable=True,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_read_timeout",
        lambda: _transport_error(httpx.ReadTimeout),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_connect_timeout",
        lambda: _transport_error(httpx.ConnectTimeout),
        provider_retryable=True,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_write_timeout",
        lambda: _transport_error(httpx.WriteTimeout),
        provider_retryable=True,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_pool_timeout",
        lambda: _transport_error(httpx.PoolTimeout),
        provider_retryable=True,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_connect_error",
        lambda: _transport_error(httpx.ConnectError),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_read_error",
        lambda: _transport_error(httpx.ReadError),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_write_error",
        # Not listed in the stream table explicitly, but retryable there too:
        # WriteError is a NetworkError subclass, and the stream table keeps
        # httpx.NetworkError.
        lambda: _transport_error(httpx.WriteError),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_remote_protocol_error",
        lambda: _transport_error(httpx.RemoteProtocolError),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_network_error",
        lambda: _transport_error(httpx.NetworkError),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_status_429",
        lambda: _http_status_error(429),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "httpx_status_400",
        lambda: _http_status_error(400),
        provider_retryable=False,
        stream_retryable=False,
    ),
    _RetryabilityCase(
        "httpx_status_500",
        lambda: _http_status_error(500),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "retryable_provider_protocol_error",
        lambda: RetryableProviderProtocolError("malformed upstream result"),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "retryable_tool_protocol_error",
        lambda: RetryableToolProtocolError("incomplete tool response"),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "truncated_provider_stream_error",
        lambda: TruncatedProviderStreamError("missing terminal marker"),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "builtin_timeout_error",
        lambda: TimeoutError("timed out"),
        provider_retryable=True,
        stream_retryable=True,
    ),
    _RetryabilityCase(
        "unrelated_runtime_error",
        lambda: RuntimeError("boom"),
        provider_retryable=False,
        stream_retryable=False,
    ),
)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
def test_retryability_matches_pinned_matrix(case: _RetryabilityCase) -> None:
    error = case.error()

    assert is_retryable_provider_error(error) is case.provider_retryable
    assert is_retryable_error(error, recovery=True) is case.stream_retryable
