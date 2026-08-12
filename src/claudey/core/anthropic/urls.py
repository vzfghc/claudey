"""Gateway wire-endpoint URL and header constants shared by both protocols.

Home of the Anthropic ``anthropic-version`` header value, the Messages
endpoint composer, and the OpenAI-compatible ``/v1`` base-URL normalizer.
Hosted in ``core`` because the config-layer connectivity probe
(:mod:`claudey.config.custom_provider_check`) consumes both families and must
not import behind the provider facades (``claudey.providers.openai_chat`` is
facade-gated). These are gateway wire-endpoint helpers for both protocols.
"""

ANTHROPIC_VERSION_HEADER = "2023-06-01"
"""The ``anthropic-version`` request header value spoken by this client."""


def anthropic_messages_url(base_url: str) -> str:
    """Compose the Messages endpoint from a user-supplied base URL.

    Anthropic's SDK appends ``/v1/messages`` to the host, so a base URL that
    already carries ``/v1`` is not doubled.
    """
    value = base_url.strip().rstrip("/")
    if value.endswith("/messages"):
        return value
    if value.endswith("/v1"):
        return value + "/messages"
    return value + "/v1/messages"


def openai_v1_base_url(base_url: str) -> str:
    """Return the canonical ``/v1`` API base for a server root or API base."""
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"
