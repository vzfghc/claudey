"""Live connectivity probe for admin-defined custom providers.

The Admin UI lets a user add an OpenAI- or Anthropic-compatible provider by
entering a base URL and API key. Before registering a wrong or unreachable
endpoint, the "Check" button probes it live. This module is the pure async
network half of that flow: it never persists anything and never raises for
expected failures (bad URL, bad type, network, auth) — it returns a small
dict the API route turns into a ``Cache-Control: no-store`` JSON response.
"""

import ssl
from typing import Any

import httpx

from claudey.core.anthropic.urls import (
    ANTHROPIC_VERSION_HEADER,
    anthropic_messages_url,
    openai_v1_base_url,
)

from .custom_providers import is_valid_compatible_type, validate_base_url

CHECK_TIMEOUT = httpx.Timeout(10.0, connect=8.0)

_MODELS_FAILED_STATUSES = frozenset({401, 403})


async def check_compatible_connection(
    base_url: str,
    api_key: str,
    compatible: str,
    model_id: str | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Probe a provider endpoint without registering it.

    Returns always ``{"valid": bool, "method": "models"|"chat", "error": str|None}``.
    Fails closed: a bad type or URL returns an invalid result rather than raising.
    ``transport`` lets tests inject ``httpx.MockTransport``.
    """
    if not is_valid_compatible_type(compatible):
        return _invalid(None, "Invalid provider type.")
    try:
        base = validate_base_url(base_url)
    except ValueError as error:
        return _invalid(None, str(error))

    models = await _probe_models(base, compatible, api_key, transport)
    if models["valid"]:
        return models
    if not model_id or models["error"] == "API key unauthorized.":
        return models
    return await _probe_chat(base, compatible, api_key, model_id, transport)


def _invalid(method: str | None, error: str) -> dict[str, Any]:
    """Build an invalid-result dict."""
    return {"valid": False, "method": method, "error": error}


def _models_url(base_url: str, compatible: str) -> str:
    """Compose the ``/models`` probe URL for a compatible endpoint."""
    if compatible == "anthropic":
        value = anthropic_messages_url(base_url)
    else:
        value = openai_v1_base_url(base_url)
    if value.endswith("/messages"):
        value = value[: -len("/messages")]
    return value.rstrip("/") + "/models"


def _chat_url(base_url: str, compatible: str) -> str:
    """Compose the chat fallback URL for a compatible endpoint.

    Anthropic gateways expose ``/v1/messages`` (not ``/chat/completions``), so
    the fallback posts there rather than to the OpenAI-shaped endpoint.
    """
    if compatible == "anthropic":
        return anthropic_messages_url(base_url)
    return openai_v1_base_url(base_url) + "/chat/completions"


def _auth_headers(compatible: str, api_key: str) -> dict[str, str]:
    """Return the probe auth headers; keys are only added when present."""
    headers: dict[str, str] = {}
    if not api_key:
        return headers
    if compatible == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = ANTHROPIC_VERSION_HEADER
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def _probe_models(
    base_url: str,
    compatible: str,
    api_key: str,
    transport: httpx.AsyncBaseTransport | None,
) -> dict[str, Any]:
    """GET ``/models``; return a result dict or ``None`` when a chat retry is worth it."""
    url = _models_url(base_url, compatible)
    async with httpx.AsyncClient(
        transport=transport,
        timeout=CHECK_TIMEOUT,
        headers=_auth_headers(compatible, api_key),
    ) as client:
        try:
            response = await client.get(url)
        except httpx.HTTPError as error:
            return _invalid_model_response(error)
        if response.status_code in _MODELS_FAILED_STATUSES:
            return {
                "valid": False,
                "method": "models",
                "error": "API key unauthorized.",
            }
        if response.is_success:
            return {"valid": True, "method": "models", "error": None}
        return {"valid": False, "method": "models", "error": None}


async def _probe_chat(
    base_url: str,
    compatible: str,
    api_key: str,
    model_id: str,
    transport: httpx.AsyncBaseTransport | None,
) -> dict[str, Any]:
    """POST a minimal chat request when ``/models`` is unavailable."""
    url = _chat_url(base_url, compatible)
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    async with httpx.AsyncClient(
        transport=transport,
        timeout=CHECK_TIMEOUT,
        headers=_auth_headers(compatible, api_key),
    ) as client:
        try:
            response = await client.post(url, json=payload)
        except httpx.HTTPError as error:
            return {
                "valid": False,
                "method": "chat",
                "error": _network_error_message(error),
            }
        if response.is_success:
            return {"valid": True, "method": "chat", "error": None}
        return {
            "valid": False,
            "method": "chat",
            "error": f"Endpoint responded with status {response.status_code}.",
        }


def _invalid_model_response(error: Exception) -> dict[str, Any]:
    """Convert a /models transport failure into an invalid 'models' result."""
    return {"valid": False, "method": "models", "error": _network_error_message(error)}


def _network_error_message(error: Exception) -> str:
    """Map a transport exception to a user-friendly message."""
    if isinstance(error, (httpx.ConnectTimeout, httpx.ReadTimeout, TimeoutError)):
        return "Connection timed out."
    text = str(error).lower()
    if isinstance(error, ssl.SSLError) or "certificate verify" in text or "ssl" in text:
        return "SSL certificate verification failed."
    if isinstance(error, httpx.ConnectError):
        if "refused" in text or "econnrefused" in text:
            return "Could not connect to the server (connection refused)."
        if "econnreset" in text or "aborted" in text:
            return "Connection was reset by the server."
        if "name or service" in text or "enotfound" in text or "getaddrinfo" in text:
            return "Could not reach the host (check the URL / DNS)."
        if "network is unreachable" in text or "enetunreach" in text:
            return "Could not reach the host (network unreachable)."
        return "Could not connect to the server."
    if isinstance(error, httpx.HTTPError):
        return "Request failed."
    return f"Unexpected error ({type(error).__name__})."
