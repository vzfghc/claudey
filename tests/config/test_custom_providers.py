"""Unit tests for the runtime custom-provider registry."""

import json
from pathlib import Path

import pytest

from claudey.config.custom_providers import (
    CUSTOM_PROVIDERS_PATH_ENV,
    CustomProviderRecord,
    CustomProviderStore,
    custom_provider_ids,
    custom_provider_store,
    custom_providers_path,
    find_custom_provider,
    is_valid_compatible_type,
    list_custom_providers,
    make_unique_provider_id,
    slug_for_display_name,
    validate_base_url,
)


@pytest.fixture
def redirect_store(monkeypatch, tmp_path: Path) -> Path:
    """Point the process-wide store at an isolated path per test."""
    store_path = tmp_path / "custom-providers.json"
    monkeypatch.setenv(CUSTOM_PROVIDERS_PATH_ENV, str(store_path))
    return store_path


def _record(
    provider_id: str = "custom_acme",
    display_name: str = "Acme",
    compatible: str = "openai",
    base_url: str = "https://api.acme.example/v1",
    api_key: str = "sk-secret",
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> CustomProviderRecord:
    return CustomProviderRecord(
        provider_id=provider_id,
        display_name=display_name,
        compatible=compatible,
        base_url=base_url,
        api_key=api_key,
        created_at=created_at,
    )


def test_store_defaults_to_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert custom_providers_path() == tmp_path / ".claudey" / "custom-providers.json"


def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(
        CUSTOM_PROVIDERS_PATH_ENV, str(tmp_path / "nested" / "store.json")
    )
    assert custom_providers_path() == tmp_path / "nested" / "store.json"


def test_upsert_then_find_round_trip(redirect_store):
    store = custom_provider_store()
    store.upsert(_record())
    assert store.find("custom_acme") == _record()


def test_upsert_replaces_existing_provider(redirect_store):
    store = custom_provider_store()
    store.upsert(_record())
    store.upsert(
        _record(display_name="Acme Renamed", base_url="https://renamed.example/v1")
    )
    records = store.all_records()
    assert len(records) == 1
    assert records[0].base_url == "https://renamed.example/v1"


def test_remove_deletes_provider(redirect_store):
    store = custom_provider_store()
    store.upsert(_record())
    assert store.remove("custom_acme") is True
    assert store.find("custom_acme") is None
    assert store.remove("custom_acme") is False


def test_persists_across_store_instances(redirect_store):
    custom_provider_store().upsert(_record())
    reloaded = CustomProviderStore(path=redirect_store)
    assert reloaded.find("custom_acme") is not None


def test_atomic_write_creates_valid_json(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-abc"))
    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    assert raw[0]["api_key"] == "sk-abc"


def test_list_in_creation_order(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(provider_id="custom_alpha"))
    store.upsert(_record(provider_id="custom_beta"))
    assert [r.provider_id for r in store.all_records()] == [
        "custom_alpha",
        "custom_beta",
    ]


def test_parse_skips_invalid_rows(redirect_store):
    store_path = redirect_store
    store_path.write_text(
        json.dumps(
            [
                {"provider_id": "custom_ok", "base_url": "https://ok.example"},
                {"provider_id": "", "base_url": "https://bad.example"},
                {
                    "provider_id": "custom_badtype",
                    "base_url": "https://b.example",
                    "compatible": "weird",
                },
                {"provider_id": "custom_nourl"},
                "not-a-dict",
            ]
        ),
        encoding="utf-8",
    )
    store = CustomProviderStore(path=store_path)
    ids = [r.provider_id for r in store.all_records()]
    assert ids == ["custom_ok"]


def test_secret_payload_masks_api_key():
    payload = _record(api_key="sk-topsecret").secret_payload()
    assert payload["has_api_key"] is True
    assert "api_key" not in payload


def test_secret_payload_without_key(redirect_store):
    payload = _record(api_key="").secret_payload()
    assert payload["has_api_key"] is False


def test_slug_for_display_name():
    assert slug_for_display_name("My Cool Provider!") == "my_cool_provider"
    assert slug_for_display_name("   ") == "provider"
    assert slug_for_display_name("Anthropic API") == "anthropic_api"


def test_make_unique_provider_id():
    existing = {"custom_acme", "custom_acme_2"}
    assert make_unique_provider_id("Acme", existing) == "custom_acme_3"
    assert make_unique_provider_id("Brand New", set()) == "custom_brand_new"


def test_custom_provider_ids_from_store(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(provider_id="custom_acme"))
    assert custom_provider_ids() == {"custom_acme"}


def test_list_custom_providers(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(provider_id="custom_acme"))
    assert [r.provider_id for r in list_custom_providers()] == ["custom_acme"]


def test_find_custom_provider(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(provider_id="custom_acme"))
    assert find_custom_provider("custom_acme") is not None
    assert find_custom_provider("custom_missing") is None


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("openai", True),
        ("anthropic", True),
        ("garbage", False),
        ("", False),
    ],
)
def test_is_valid_compatible_type(value, valid):
    assert is_valid_compatible_type(value) is valid


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://example.com",
        "not a url",
        "http://",  # no netloc
    ],
)
def test_validate_base_url_rejects(raw):
    with pytest.raises(ValueError):
        validate_base_url(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://api.example.com/v1", "https://api.example.com/v1"),
        ("https://api.example.com/v1/", "https://api.example.com/v1"),
        ("  http://localhost:8080  ", "http://localhost:8080"),
    ],
)
def test_validate_base_url_normalizes(raw, expected):
    assert validate_base_url(raw) == expected
