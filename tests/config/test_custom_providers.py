"""Unit tests for the runtime custom-provider registry."""

import json
from collections.abc import Callable, Coroutine
from pathlib import Path

import httpx
import pytest

from claudey.config.custom_provider_check import check_compatible_connection
from claudey.config.custom_providers import (
    CUSTOM_PROVIDERS_PATH_ENV,
    PROVIDER_ENCRYPTION_KEY_ENV,
    CustomProviderRecord,
    CustomProviderStore,
    custom_provider_ids,
    custom_provider_store,
    custom_providers_path,
    effective_api_key,
    find_custom_provider,
    is_valid_compatible_type,
    list_custom_providers,
    make_unique_provider_id,
    slug_for_display_name,
    validate_base_url,
)
from claudey.core.secret_crypto import ENCRYPTED_PREFIX, SecretCryptoError


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


def test_without_key_writes_remain_plaintext(redirect_store):
    """Back-compat: no CLAUDEY_PROVIDER_ENCRYPTION_KEY leaves keys as-is."""
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-plain"))
    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    assert raw[0]["api_key"] == "sk-plain"


def test_with_key_encrypts_keys_on_write(redirect_store, monkeypatch):
    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "k" * 64)
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-topsecret"))

    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    assert raw[0]["api_key"].startswith(ENCRYPTED_PREFIX)
    assert "sk-topsecret" not in raw[0]["api_key"]
    record = store.find("custom_acme")
    assert record is not None
    assert effective_api_key(record) == "sk-topsecret"


def test_existing_plaintext_upgraded_on_next_write(redirect_store, monkeypatch):
    """Plaintext rows are transparently re-encrypted on the next write."""
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-legacy"))
    assert (
        json.loads(redirect_store.read_text(encoding="utf-8"))[0]["api_key"]
        == "sk-legacy"
    )

    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "k" * 64)
    store.upsert(_record(provider_id="custom_other", api_key="sk-new"))

    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    by_id = {entry["provider_id"]: entry for entry in raw}
    assert by_id["custom_acme"]["api_key"].startswith(ENCRYPTED_PREFIX)
    another = store.find("custom_other")
    assert another is not None
    assert effective_api_key(another) == "sk-new"


def test_already_encrypted_keys_are_not_double_encrypted(redirect_store, monkeypatch):
    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "k" * 64)
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-first"))

    # Same key persists alongside a newly written provider.
    store.upsert(_record(provider_id="custom_second", api_key="sk-second"))
    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    first = next(e for e in raw if e["provider_id"] == "custom_acme")
    assert first["api_key"].startswith(ENCRYPTED_PREFIX)
    first_count = first["api_key"].count(ENCRYPTED_PREFIX)
    assert first_count == 1


def test_encrypted_key_without_configured_key_fails_fast(redirect_store, monkeypatch):
    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "k" * 64)
    custom_provider_store().upsert(_record(api_key="sk-secret"))

    monkeypatch.delenv(PROVIDER_ENCRYPTION_KEY_ENV)
    record = custom_provider_store().find("custom_acme")
    assert record is not None
    with pytest.raises(SecretCryptoError):
        effective_api_key(record)


def test_wrong_key_raises_when_decrypting(redirect_store, monkeypatch):
    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "right" + "0" * 60)
    custom_provider_store().upsert(_record(api_key="sk-guarded"))

    monkeypatch.setenv(PROVIDER_ENCRYPTION_KEY_ENV, "wrong" + "0" * 60)
    record = custom_provider_store().find("custom_acme")
    assert record is not None
    with pytest.raises(SecretCryptoError) as exc_info:
        effective_api_key(record)
    assert "failed authentication" in str(exc_info.value)


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


# --- check_compatible_connection probe tests (httpx.MockTransport, no network) ---


async def _run_check(
    handler: Callable[[httpx.Request], Coroutine[None, None, httpx.Response]],
    *,
    base_url: str = "https://api.example.com/v1",
    api_key: str = "sk-key",
    compatible: str = "openai",
    model_id: str | None = None,
) -> dict:
    transport = httpx.MockTransport(handler)
    return await check_compatible_connection(
        base_url,
        api_key,
        compatible,
        model_id,
        transport=transport,
    )


@pytest.mark.asyncio
async def test_check_invalid_type_fails_closed():
    result = await check_compatible_connection(
        "https://api.example.com", "sk-key", "garbage"
    )
    assert result == {
        "valid": False,
        "method": None,
        "error": "Invalid provider type.",
    }


@pytest.mark.asyncio
async def test_check_invalid_base_url_no_network():
    result = await check_compatible_connection("ftp://nope", "sk-key", "openai")
    assert result["valid"] is False
    assert "Base URL" in result["error"]
    assert result["method"] is None
    # Fail-closed: no transport was even invoked because validation runs first.
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json={"data": []})

    result = await _run_check(handler, base_url="  ", api_key="sk-key")
    assert result["valid"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_check_valid_openai_models_headers():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    result = await _run_check(handler, compatible="openai")
    assert result["valid"] is True
    assert result["method"] == "models"
    assert requests[0].url.path == "/v1/models"
    headers = requests[0].headers
    assert headers["Authorization"] == "Bearer sk-key"
    assert "x-api-key" not in headers


@pytest.mark.asyncio
async def test_check_valid_anthropic_models_headers():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    result = await _run_check(handler, compatible="anthropic")
    assert result["valid"] is True
    assert result["method"] == "models"
    assert requests[0].url.path == "/v1/models"
    headers = requests[0].headers
    assert headers["x-api-key"] == "sk-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["Authorization"] == "Bearer sk-key"


@pytest.mark.asyncio
async def test_check_unauthorized_401():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    # No model_id: return straight away without a chat fallback.
    result = await _run_check(handler)
    assert result == {
        "valid": False,
        "method": "models",
        "error": "API key unauthorized.",
    }


@pytest.mark.asyncio
async def test_check_chat_fallback_openai():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(500, json={})
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o-mini"
        assert body["max_tokens"] == 1
        return httpx.Response(200, json={"id": "ok"})

    result = await _run_check(handler, model_id="gpt-4o-mini")
    assert result == {"valid": True, "method": "chat", "error": None}


@pytest.mark.asyncio
async def test_check_chat_fallback_anthropic_posts_messages():
    routes: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        routes.append(request.url.path)
        if request.url.path.endswith("/models"):
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"id": "ok"})

    result = await _run_check(handler, compatible="anthropic", model_id="claude-3")
    assert result == {"valid": True, "method": "chat", "error": None}
    # Anthropic fallback must hit /v1/messages, not /chat/completions.
    assert routes[-1] == "/v1/messages"


@pytest.mark.asyncio
async def test_check_chat_fallback_no_model_id_skips():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(500, json={})
        raise AssertionError("chat fallback must not be reached without model_id")

    result = await _run_check(handler)
    assert result["valid"] is False
    assert result["method"] == "models"


@pytest.mark.asyncio
async def test_check_network_error_mapping_refused():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    result = await _run_check(handler)
    assert result["valid"] is False
    assert "connection refused" in result["error"]


@pytest.mark.asyncio
async def test_check_network_error_mapping_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    result = await _run_check(handler)
    assert result["valid"] is False
    assert "timed out" in result["error"]


@pytest.mark.asyncio
async def test_check_blank_api_key_still_attempts_probe():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    result = await _run_check(handler, api_key="")
    assert result["valid"] is True
    assert "authorization" not in requests[0].headers
    assert "x-api-key" not in requests[0].headers


# ---------------------------------------------------------------------------
# At-rest key encryption (P3-D1)
# ---------------------------------------------------------------------------


def _raw_row(path: Path) -> dict:
    """Return the first stored JSON row at ``path``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload, "expected a non-empty store on disk"
    return payload[0]


def test_no_key_keeps_plaintext_back_compat(redirect_store):
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-plain"))
    raw = _raw_row(redirect_store)
    assert raw["api_key"] == "sk-plain"


def test_configured_key_encrypts_on_write(monkeypatch, redirect_store):
    monkeypatch.setenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY", "test-passphrase")
    store = custom_provider_store()
    store.upsert(_record(api_key="sk-to-encrypt"))
    raw = _raw_row(redirect_store)
    assert raw["api_key"].startswith("enc:v1:")
    assert "sk-to-encrypt" not in redirect_store.read_text(encoding="utf-8")


def test_configured_key_does_not_double_encrypt(monkeypatch, redirect_store):
    from claudey.config.custom_providers import encrypt_secret
    from claudey.core.secret_crypto import is_encrypted

    monkeypatch.setenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY", "test-passphrase")
    already = encrypt_secret("sk-secret", "test-passphrase")
    store = custom_provider_store()
    store.upsert(_record(api_key=already))
    raw = _raw_row(redirect_store)
    assert is_encrypted(raw["api_key"])
    assert raw["api_key"] == already


def test_encrypted_round_trip_via_effective_key(monkeypatch, redirect_store):
    from claudey.config.custom_providers import effective_api_key

    monkeypatch.setenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY", "test-passphrase")
    custom_provider_store().upsert(_record(api_key="sk-secret"))
    raw = _raw_row(redirect_store)
    assert raw["api_key"].startswith("enc:v1:")
    # Reload from disk (what the next process sees) and recover the secret.
    reloaded = CustomProviderStore(path=redirect_store).find("custom_acme")
    assert reloaded is not None
    assert reloaded.api_key.startswith("enc:v1:")
    assert effective_api_key(reloaded) == "sk-secret"


def test_plaintext_effective_key_passes_through_without_key(redirect_store):
    from claudey.config.custom_providers import effective_api_key

    store = custom_provider_store()
    store.upsert(_record(api_key="sk-plain"))
    record = store.find("custom_acme")
    assert record is not None
    assert effective_api_key(record) == "sk-plain"


def test_encrypted_read_without_key_fails_fast(monkeypatch, redirect_store):
    from claudey.config.custom_providers import effective_api_key
    from claudey.core.secret_crypto import SecretCryptoError

    # Write an encrypted record while the key is configured, then drop the key
    # and load the ciphertext from disk (a fresh process has no in-memory copy).
    monkeypatch.setenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY", "secret-key")
    custom_provider_store().upsert(_record(api_key="sk-secret"))
    monkeypatch.delenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY")
    reloaded = CustomProviderStore(path=redirect_store).find("custom_acme")
    assert reloaded is not None
    assert reloaded.api_key.startswith("enc:v1:")
    with pytest.raises(SecretCryptoError):
        effective_api_key(reloaded)


def test_plaintext_read_is_transparently_upgraded_on_next_write(
    monkeypatch, redirect_store
):
    from claudey.core.secret_crypto import is_encrypted

    # Write plaintext with no key...
    custom_provider_store().upsert(_record(api_key="sk-secret"))
    assert _raw_row(redirect_store)["api_key"] == "sk-secret"
    # ...then enable a key and trigger another write: plaintext upgraded.
    monkeypatch.setenv("CLAUDEY_PROVIDER_ENCRYPTION_KEY", "later-key")
    custom_provider_store().upsert(_record(provider_id="custom_second"))
    assert is_encrypted(_raw_row(redirect_store)["api_key"])
    second = json.loads(redirect_store.read_text(encoding="utf-8"))[1]
    assert is_encrypted(second["api_key"])
