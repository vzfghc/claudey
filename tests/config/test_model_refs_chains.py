"""Tier-setting chain grammar: inline, @combo:, and global-fallback expansion."""

from pathlib import Path

import pytest

from claudey.config.combos import (
    COMBOS_PATH_ENV,
    ComboNode,
    ComboRecord,
    combo_store,
)
from claudey.config.model_refs import (
    configured_chat_model_refs,
    is_combo_ref,
    parse_chain_refs,
)
from claudey.config.settings import Settings


def test_single_ref_back_compat():
    assert parse_chain_refs("nvidia_nim/nvidia/x") == ("nvidia_nim/nvidia/x",)


def test_inline_chain_splits_and_strips():
    assert parse_chain_refs(" open_router/a , novita/b , llm7/c ") == (
        "open_router/a",
        "novita/b",
        "llm7/c",
    )


def test_inline_chain_empty_element_rejected():
    with pytest.raises(ValueError):
        parse_chain_refs("open_router/a,,novita/b")


def test_combo_token_not_allowed_inside_chain():
    with pytest.raises(ValueError):
        parse_chain_refs("open_router/a,@combo:flagship")
    with pytest.raises(ValueError):
        parse_chain_refs("@combo:flagship,novita/b")


def test_is_combo_ref():
    assert is_combo_ref("@combo:flagship") is True
    assert is_combo_ref("@combo/misspelled") is False  # must use ":" not "/"
    assert is_combo_ref("open_router/a") is False


def test_combo_ref_resolves_by_priority():
    resolver = lambda _combo_id: (  # noqa: E731
        ComboNode("a/model", priority=0),
        ComboNode("b/model", priority=1),
    )
    assert parse_chain_refs("@combo:flagship", combo_resolver=resolver) == (
        "a/model",
        "b/model",
    )


def test_combo_ref_unknown_or_disabled_rejected():
    with pytest.raises(ValueError, match="Unknown or disabled combo"):
        parse_chain_refs("@combo:ghost")


def test_combo_ref_empty_id_rejected():
    with pytest.raises(ValueError, match="combo"):
        parse_chain_refs("@combo:")


@pytest.fixture
def seeded_combo(monkeypatch, tmp_path: Path) -> Path:
    store_path = tmp_path / "combos.json"
    monkeypatch.setenv(COMBOS_PATH_ENV, str(store_path))
    combo_store().upsert(
        ComboRecord(
            combo_id="flagship",
            display_name="Flagship",
            nodes=(
                ComboNode("novita/deepseek/deepseek-r1-0528", priority=1),
                ComboNode("llm7/meta-llama/llama-3.1-70b", priority=0),
            ),
        )
    )
    return store_path


def test_combo_ref_store_backed(seeded_combo):
    assert parse_chain_refs("@combo:flagship") == (
        "llm7/meta-llama/llama-3.1-70b",
        "novita/deepseek/deepseek-r1-0528",
    )


# --- configured_chat_model_refs expansion ---


def _base_settings() -> Settings:
    return Settings()


def _refs(settings: Settings):
    return [ref.model_ref for ref in configured_chat_model_refs(settings)]


def test_configured_refs_expand_inline_chain():
    settings = _base_settings()
    settings.model = "nvidia_nim/x"
    settings.model_opus = "open_router/a,novita/b"
    assert _refs(settings) == ["nvidia_nim/x", "open_router/a", "novita/b"]


def test_configured_refs_expand_combo(seeded_combo):
    settings = _base_settings()
    settings.model = "nvidia_nim/x"
    settings.model_haiku = "@combo:flagship"
    assert _refs(settings) == [
        "nvidia_nim/x",
        "llm7/meta-llama/llama-3.1-70b",
        "novita/deepseek/deepseek-r1-0528",
    ]


def test_configured_refs_appends_global_fallback_last(seeded_combo):
    settings = _base_settings()
    settings.model = "nvidia_nim/x"
    settings.model_haiku = "@combo:flagship"
    settings.global_fallback_model = "open_router/openrouter/free"
    assert _refs(settings) == [
        "nvidia_nim/x",
        "llm7/meta-llama/llama-3.1-70b",
        "novita/deepseek/deepseek-r1-0528",
        "open_router/openrouter/free",
    ]


def test_configured_refs_skips_missing_global_fallback():
    settings = _base_settings()
    settings.model = "nvidia_nim/x"
    assert _refs(settings) == ["nvidia_nim/x"]


def test_configured_refs_dedupes_across_tiers_and_chain(seeded_combo):
    settings = _base_settings()
    settings.model = "nvidia_nim/x"
    settings.model_opus = "open_router/a,novita/b"
    settings.model_haiku = "@combo:flagship"
    settings.global_fallback_model = "open_router/a"
    assert _refs(settings) == [
        "nvidia_nim/x",
        "open_router/a",
        "novita/b",
        "llm7/meta-llama/llama-3.1-70b",
        "novita/deepseek/deepseek-r1-0528",
    ]


# --- Settings validation (day-0) via env ---


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("MODEL_OPUS", "open_router/a,pants"),
        ("MODEL_OPUS", "@combo:ghost"),
        ("MODEL_OPUS", "open_router/a,open_router/a"),
        ("GLOBAL_FALLBACK_MODEL", "pants"),
        ("MODEL_OPUS", "open_router/a,"),
    ],
)
def test_settings_rejects_invalid_tier_values(monkeypatch, env_name, env_value):
    monkeypatch.setenv(env_name, env_value)
    with pytest.raises(ValueError):
        Settings()


def test_settings_rejects_unknown_combo_at_config_time(monkeypatch):
    monkeypatch.setenv("MODEL_OPUS", "@combo:ghost")
    with pytest.raises(ValueError, match="Unknown or disabled combo"):
        Settings()


def test_settings_rejects_adjacent_duplicate_chain_node(monkeypatch):
    monkeypatch.setenv("MODEL_OPUS", "open_router/a,open_router/a")
    with pytest.raises(ValueError, match="Adjacent duplicate"):
        Settings()


def test_settings_accepts_combo_ref(monkeypatch, seeded_combo):
    monkeypatch.setenv("MODEL_OPUS", "@combo:flagship")
    assert Settings().model_opus == "@combo:flagship"


def test_settings_accepts_global_fallback(monkeypatch):
    monkeypatch.setenv("GLOBAL_FALLBACK_MODEL", "open_router/openrouter/free")
    assert Settings().global_fallback_model == "open_router/openrouter/free"


def test_settings_accepts_inline_chain(monkeypatch):
    monkeypatch.setenv("MODEL_OPUS", "open_router/a,novita/b")
    assert Settings().model_opus == "open_router/a,novita/b"


def test_settings_allows_non_adjacent_repeated_node(monkeypatch):
    monkeypatch.setenv("MODEL_OPUS", "open_router/a,novita/b,open_router/a")
    assert Settings().model_opus == "open_router/a,novita/b,open_router/a"
