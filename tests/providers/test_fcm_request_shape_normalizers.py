"""Regression audit of request-shape normalization vs. FCM ``schema-normalizer``
rules.

FCM normalizes OpenAI-compatible chat request shapes with a set of strips the
claudey request-policy layer enforces per provider via ``unsupported_body_keys``
and ``normalize_n_to_one``. This module locks in that audit so a future provider
profile cannot silently regress the guarantees:

- `parallel_tool_calls`, `n`, `top_k`/`top_logprobs`, `logprobs`, `echo`,
  `user`, `metadata`, `store` (and `logit_bias`, `audio`, ...) are stripped only
  where a profile declares the upstream rejects them;
- `n` is forced to 1 only for providers that need it (groq); others preserve it;
- canonical fields (incl. `temperature`) cannot be overridden by ``extra_body``.

No *new* normalizers are introduced: the audit found the strip surface already
adequate, and GLM/Z.ai temperature passes through unchanged rather than being
silently clamped (documented gap, left to the provider).
"""

from typing import Any

import pytest

from claudey.providers.openai_chat.extra_body import (
    validate_extra_body_does_not_override_canonical_fields,
)
from claudey.providers.openai_chat.profiles import OPENAI_CHAT_PROFILES
from claudey.providers.openai_chat.request_policy import (
    _apply_common_openai_chat_policy,
)

# The full FCM schema-normalizer strip vocabulary.
FCM_STRIP_KEYS = frozenset(
    {
        "parallel_tool_calls",
        "n",
        "top_k",
        "top_logprobs",
        "logprobs",
        "echo",
        "user",
        "metadata",
        "store",
        "logit_bias",
        "audio",
        "modalities",
        "prediction",
        "service_tier",
    }
)


def _profile_policies():
    """Yield (profile_id, policy) for every provider with a strip surface."""
    for provider_id, profile in OPENAI_CHAT_PROFILES.items():
        policy = profile.request_policy
        if policy.unsupported_body_keys or policy.normalize_n_to_one:
            yield provider_id, policy


def test_every_stripping_profile_declares_documented_keys() -> None:
    """The audit found the strip surface is declared per profile (no global set)."""
    provider_ids = [pid for pid, _ in _profile_policies()]
    assert "cohere" in provider_ids
    assert "groq" in provider_ids


@pytest.mark.parametrize(
    ("provider_id", "policy"),
    [(pid, policy) for pid, policy in _profile_policies()],
    ids=[pid for pid, _ in _profile_policies()],
)
def test_declared_unsupported_keys_are_stripped_fcm_vocabulary(
    provider_id, policy
) -> None:
    """Every FCM-listed key a profile rejects is dropped from the wire body."""
    body: dict[str, Any] = {
        **dict.fromkeys(FCM_STRIP_KEYS, True),
        "model": "test-model",
        "messages": [],
        "max_tokens": 32,
    }
    _apply_common_openai_chat_policy(body, policy)

    for key in policy.unsupported_body_keys:
        assert key not in body, f"{provider_id} must strip {key}"


@pytest.mark.parametrize(
    ("provider_id", "policy"),
    [(pid, policy) for pid, policy in _profile_policies()],
    ids=[pid for pid, _ in _profile_policies()],
)
def test_undeclared_keys_pass_through_unchanged(provider_id, policy) -> None:
    """Keys a profile does NOT reject are preserved (no blanket nuking)."""
    # 'stream_options' is a canonical passthrough field never in any strip set.
    body: dict[str, Any] = {
        "model": "test-model",
        "messages": [],
        "stream_options": {"include_usage": True},
    }
    for key in policy.unsupported_body_keys:
        body[key] = True

    _apply_common_openai_chat_policy(body, policy)

    assert body["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize(
    ("provider_id", "policy"),
    [(pid, policy) for pid, policy in _profile_policies()],
    ids=[pid for pid, _ in _profile_policies()],
)
def test_n_normalization_is_per_provider_only(provider_id, policy) -> None:
    """groq forces ``n=1``; cohere strips ``n``; others preserve a caller ``n``."""
    body: dict[str, Any] = {"model": "m", "messages": [], "n": 4}
    _apply_common_openai_chat_policy(body, policy)
    if policy.normalize_n_to_one:
        expected = 1
    elif "n" in policy.unsupported_body_keys:
        expected = None  # stripped for the upstream
    else:
        expected = 4
    assert body.get("n") == expected


def test_groq_declares_rate_limit_friendly_strip_surface() -> None:
    policy = OPENAI_CHAT_PROFILES["groq"].request_policy
    assert policy.normalize_n_to_one is True
    assert {"logprobs", "logit_bias", "top_logprobs"} <= policy.unsupported_body_keys


def test_cohere_declares_broad_strip_surface() -> None:
    policy = OPENAI_CHAT_PROFILES["cohere"].request_policy
    assert {
        "metadata",
        "n",
        "parallel_tool_calls",
        "store",
        "top_logprobs",
    } <= policy.unsupported_body_keys


def test_glm_temperature_is_forwarded_unsilenced() -> None:
    """Audit finding: no provider silently clamps temperature.

    A temperature outside an upstream's accepted range reaches the wire
    unchanged and surfaces as an upstream rejection, so the operator sees a real
    diagnostic instead of a silently altered temperature.
    """
    policy = OPENAI_CHAT_PROFILES["zai"].request_policy
    # Z.ai rejects caller extra_body outright; temperature rides the canonical
    # body field and must never be clamped by request-policy.
    body: dict[str, Any] = {
        "model": "glm-4.5",
        "messages": [],
        "temperature": 2.5,
    }
    _apply_common_openai_chat_policy(body, policy)
    assert body["temperature"] == 2.5


def test_extra_body_cannot_override_canonical_temperature() -> None:
    """FCM rule: user extras never clobber claudey-owned request fields."""
    with pytest.raises(ValueError, match="canonical request fields"):
        validate_extra_body_does_not_override_canonical_fields(
            {"temperature": 0.0, "metadata": {"trace": "x"}}
        )


def test_extra_body_cannot_override_reasoning_fields() -> None:
    from claudey.providers.openai_chat.extra_body import (
        validate_extra_body_does_not_override_reasoning_fields,
    )

    with pytest.raises(ValueError, match="reasoning fields"):
        validate_extra_body_does_not_override_reasoning_fields({"thinking": {}})
