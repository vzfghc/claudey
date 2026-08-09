"""Provider-prefixed model reference and tier-chain helpers.

Tier settings accept three grammars (OmniRoute's chain shape):

- single ref        ``MODEL_OPUS="provider/model"``
- inline chain      ``MODEL_OPUS="refA,refB,refC"``
- combo reference   ``MODEL_OPUS="@combo:flagship"`` (expanded via the combo store)

A ``global_fallback_model`` is appended last to every resolved chain (when set)
and is always the terminal hop of a failover chain.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from claudey.config.combos import ComboNode
from claudey.config.combos import resolve_combo as _default_combo_resolver

COMBO_REF_PREFIX = "@combo:"


@dataclass(frozen=True, slots=True)
class ConfiguredChatModelRef:
    """A unique configured (expanded) chat model reference."""

    model_ref: str
    provider_id: str
    model_id: str


class ChatModelConfig(Protocol):
    model: str
    model_fable: str | None
    model_opus: str | None
    model_sonnet: str | None
    model_haiku: str | None
    global_fallback_model: str | None


def parse_provider_type(model_ref: str) -> str:
    """Extract provider type from any 'provider/model' string."""

    return model_ref.split("/", 1)[0]


def parse_model_name(model_ref: str) -> str:
    """Extract model name from any 'provider/model' string."""

    return model_ref.split("/", 1)[1]


def is_combo_ref(value: str) -> bool:
    """Return whether a tier-setting value is a ``@combo:<id>`` reference."""
    return value.startswith(COMBO_REF_PREFIX)


def parse_chain_refs(
    value: str,
    *,
    combo_resolver: Callable[
        ..., tuple[ComboNode, ...] | None
    ] = _default_combo_resolver,
) -> tuple[str, ...]:
    """Expand one tier-setting value into an ordered tuple of provider/model refs.

    A single ref yields a one-tuple (backwards compatible). A comma-separated
    value is an inline chain; empty elements and nested ``@...`` tokens are
    rejected. A ``@combo:<id>`` value delegates to ``combo_resolver`` and trusts
    the returned nodes (so custom provider nodes in combos stay routable); an
    unknown or disabled combo raises here rather than failing at request time.
    """
    value = value.strip()
    if not value:
        raise ValueError("Model tier must not be empty.")

    if is_combo_ref(value):
        combo_id = value[len(COMBO_REF_PREFIX) :].strip()
        if not combo_id:
            raise ValueError(f"Combo reference requires an id (got {value!r}).")
        resolved = combo_resolver(combo_id)
        if not resolved:
            raise ValueError(
                f"Unknown or disabled combo {combo_id!r} referenced by {value!r}."
            )
        return tuple(node.provider_model_ref for node in resolved)

    if "," in value:
        parts = tuple(part.strip() for part in value.split(","))
        for index, part in enumerate(parts):
            if not part:
                raise ValueError(
                    f"Chain must not contain empty elements (got {value!r})."
                )
            if part.startswith("@"):
                raise ValueError(
                    f"Combo tokens may only appear alone, never inside a chain "
                    f"(got {value!r})."
                )
            if index > 0 and part == parts[index - 1]:
                raise ValueError(
                    f"Adjacent duplicate chain node {part!r} in {value!r}."
                )
        return parts

    return (value,)


def configured_chat_model_refs(
    settings: ChatModelConfig,
) -> tuple[ConfiguredChatModelRef, ...]:
    """Return unique configured chat provider/model refs, chains expanded.

    Each tier is expanded through :func:`parse_chain_refs`, preserving order and
    de-duplicating (first occurrence wins). ``global_fallback_model`` — when set
    and not already present — is appended as the terminal hop.
    """

    refs: list[str] = []
    seen: set[str] = set()

    def _extend(chain: tuple[str, ...]) -> None:
        for ref in chain:
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)

    for tier in (
        settings.model,
        settings.model_fable,
        settings.model_opus,
        settings.model_sonnet,
        settings.model_haiku,
    ):
        if tier is not None:
            _extend(parse_chain_refs(tier))

    fallback = getattr(settings, "global_fallback_model", None)
    if fallback:
        _extend(parse_chain_refs(fallback))

    return tuple(
        ConfiguredChatModelRef(
            model_ref=ref,
            provider_id=parse_provider_type(ref),
            model_id=parse_model_name(ref),
        )
        for ref in refs
    )
