import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from claudey.api import admin_dashboard
from claudey.application.connected_accounts import (
    ConnectedAccountLoginMode,
    ConnectedAccountState,
    ConnectedAccountStatus,
)
from claudey.application.model_metadata import (
    ProviderModelInfo,
    ProviderModelRefreshResult,
)
from claudey.config.admin.values import MASKED_SECRET
from claudey.config.server_urls import local_admin_url
from claudey.config.settings import Settings
from tests.api.support import create_test_app, provider_manager_for_app


def _local_client(app):
    return TestClient(app, client=("127.0.0.1", 50000))


def _set_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def _clear_process_config(monkeypatch) -> None:
    for key in (
        "MODEL",
        "NVIDIA_NIM_API_KEY",
        "HUGGINGFACE_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "PECUT_API_KEY",
        "DEEPSEEK_SESSION_TOKEN",
        "AWS_BEARER_TOKEN_BEDROCK",
        "BEDROCK_BASE_URL",
        "BEDROCK_PROXY",
        "OLLAMA_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "TELEGRAM_PROXY_URL",
        "HANS_ENV_FILE",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "GITHUB_MODELS_TOKEN",
        "SAMBANOVA_API_KEY",
        "HOST",
        "PORT",
        "HANS_OPEN_BROWSER",
        "VOICE_NOTE_ENABLED",
        "WHISPER_DEVICE",
        "LOG_FILE",
        "ZAI_BASE_URL",
        "CLAUDE_WORKSPACE",
        "CLAUDE_CLI_BIN",
    ):
        monkeypatch.delenv(key, raising=False)


def test_admin_page_is_loopback_only(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()

    assert _local_client(app).get("/admin").status_code == 200
    remote_client = TestClient(app, client=("203.0.113.10", 50000))
    assert remote_client.get("/admin").status_code == 403


def _react_asset_paths() -> list[str]:
    """Resolve the hashed JS/CSS paths the built React entry references."""
    entry = Path("src/claudey/api/admin_static/admin_ui_dist/index.html").read_text(
        encoding="utf-8"
    )
    return re.findall(r'(?:src|href)="(/admin/assets/[^"]+)"', entry)


def test_admin_responses_are_never_cached(monkeypatch, tmp_path):
    # Resolve the asset paths from the committed build BEFORE _set_home chdirs
    # into tmp_path (the build lives at a repo-relative path).
    asset_paths = _react_asset_paths()

    _set_home(monkeypatch, tmp_path)
    client = _local_client(create_test_app())

    for path in ["/admin", "/admin/api/config", *asset_paths]:
        response = client.get(path)

        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "no-store", path


@pytest.mark.parametrize(
    ("path", "client_host", "expected_status"),
    (
        ("/admin", "203.0.113.10", 403),
        ("/admin/assets/missing.js", "127.0.0.1", 404),
    ),
)
def test_admin_http_errors_are_never_cached(
    monkeypatch,
    tmp_path,
    path,
    client_host,
    expected_status,
):
    _set_home(monkeypatch, tmp_path)
    client = TestClient(create_test_app(), client=(client_host, 50000))

    response = client.get(path)

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "provider_id",
    (
        "openai",
        "nvidia_nim",
        "anthropic",
        "wafer",
        "pecut",
    ),
)
def test_admin_provider_logos_are_served(monkeypatch, tmp_path, provider_id):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get(
        f"/admin/assets/logos/{provider_id}.svg"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in response.content


def test_admin_fallback_provider_logo_is_served(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get("/admin/assets/logos/_fallback.svg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in response.content


@pytest.mark.parametrize(
    "path",
    (
        "/admin/assets/logos/missing.svg",
        "/admin/assets/logos/..%2fadmin.css",
        "/admin/assets/logos/..%2Fadmin.js",
    ),
)
def test_admin_provider_logos_reject_unknown_and_traversal(
    monkeypatch,
    tmp_path,
    path,
):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get(path)

    assert response.status_code == 404


def test_admin_validation_errors_are_never_cached(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)

    response = _local_client(create_test_app()).post(
        "/admin/api/config/validate",
        content="{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


def test_admin_unexpected_errors_are_never_cached(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    client = TestClient(
        create_test_app(),
        client=("127.0.0.1", 50000),
        raise_server_exceptions=False,
    )

    with patch(
        "claudey.api.admin_routes.load_config_response",
        side_effect=RuntimeError("test error"),
    ):
        response = client.get("/admin/api/config")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"


def test_admin_cache_policy_does_not_match_similar_public_paths(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)

    response = _local_client(create_test_app()).get("/administrator")

    assert response.status_code == 404
    assert "cache-control" not in response.headers


def _react_bundle() -> str:
    """Read the committed React bundle (Phase 4: the app at /admin)."""
    assets = Path("src/claudey/api/admin_static/admin_ui_dist/assets")
    bundles = sorted(assets.glob("index-*.js"))
    assert bundles, "admin-ui build must be committed"
    return bundles[-1].read_text(encoding="utf-8")


def test_admin_api_fetches_bypass_browser_cache():
    # The Vite minifier may emit the cache value as a double-quoted string or a
    # backtick template literal, so assert on the directive itself.
    bundle = _react_bundle()
    assert "no-store" in bundle
    # The directive must be attached to the fetch cache option, not some other
    # string — confirm it sits in a fetch(...) cache: assignment.
    match = re.search(r"cache:\s*[`\"']no-store[`\"']", bundle)
    assert match is not None, "fetch cache directive not found in bundle"


def test_admin_custom_providers_render_fallback_logo():
    bundle = _react_bundle()

    assert "/admin/assets/logos/_fallback.svg" in bundle
    assert "custom_".strip() in bundle  # custom provider id prefix
    assert "_fallback.svg" in bundle


def test_admin_ui_entry_is_served(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get("/admin")

    assert response.status_code == 200
    assert 'id="root"' in response.text
    # Same cache policy as every other admin response; hashed asset names carry
    # the immutable cache-busting.
    assert response.headers["cache-control"] == "no-store"


def test_admin_ui_legacy_path_redirects(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get("/admin/ui", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/admin"


def test_admin_ui_is_loopback_only(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    remote_client = TestClient(create_test_app(), client=("203.0.113.10", 50000))

    assert remote_client.get("/admin/ui").status_code == 403


def test_admin_ui_assets_are_served(monkeypatch, tmp_path):
    # Read the committed build before _set_home chdirs into tmp_path.
    entry = Path("src/claudey/api/admin_static/admin_ui_dist/index.html").read_text(
        encoding="utf-8"
    )
    asset_src = re.search(r'(?:src|href)="(/admin/assets/[^"]+)"', entry)
    assert asset_src is not None, "built entry must reference /admin/assets chunks"

    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get(asset_src.group(1))

    assert response.status_code == 200
    assert len(response.content) > 0


@pytest.mark.parametrize(
    "path",
    (
        "/admin/assets/missing.js",
        "/admin/assets/..%2fadmin.js",
        "/admin/assets/..%2Fadmin.js",
    ),
)
def test_admin_ui_rejects_unknown_and_traversal(monkeypatch, tmp_path, path):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get(path)

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


class _FakeConnectedAccount:
    def __init__(self) -> None:
        self.connected = False
        self.revision = 0
        self.cancelled = False

    def is_connected(self) -> bool:
        return self.connected

    def status(self) -> ConnectedAccountStatus:
        return ConnectedAccountStatus(
            provider_id="openai",
            state=(
                ConnectedAccountState.CONNECTED
                if self.connected
                else ConnectedAccountState.DISCONNECTED
            ),
            connected=self.connected,
            revision=self.revision,
            email="safe@example.com" if self.connected else None,
        )

    async def start_login(
        self, mode: ConnectedAccountLoginMode
    ) -> ConnectedAccountStatus:
        return ConnectedAccountStatus(
            provider_id="openai",
            state=ConnectedAccountState.CONNECTING,
            connected=False,
            revision=self.revision,
            attempt_id="login_safe",
            mode=mode,
            authorization_url="https://auth.openai.com/safe",
        )

    async def cancel_login(self) -> ConnectedAccountStatus:
        self.cancelled = True
        return self.status()

    async def disconnect(self) -> ConnectedAccountStatus:
        self.connected = False
        self.revision += 1
        return self.status()

    async def close(self) -> None:
        return None


def test_admin_connected_account_routes_are_safe_loopback_only_and_uncached(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    account = _FakeConnectedAccount()
    app = create_test_app(connected_accounts={"openai": account})
    client = _local_client(app)

    status_response = client.get("/admin/api/providers/openai/auth")
    login_response = client.post(
        "/admin/api/providers/openai/auth/login",
        json={"mode": "browser"},
    )
    cancel_response = client.post("/admin/api/providers/openai/auth/cancel")

    assert status_response.status_code == 200
    assert status_response.headers["cache-control"] == "no-store"
    assert status_response.json()["state"] == "disconnected"
    assert login_response.status_code == 200
    assert login_response.json() == {
        "provider_id": "openai",
        "state": "connecting",
        "connected": False,
        "revision": 0,
        "attempt_id": "login_safe",
        "mode": "browser",
        "authorization_url": "https://auth.openai.com/safe",
    }
    assert "token" not in login_response.text.lower()
    assert cancel_response.status_code == 200
    assert account.cancelled is True
    remote = TestClient(app, client=("203.0.113.10", 50000))
    assert remote.get("/admin/api/providers/openai/auth").status_code == 403


def test_admin_rejects_auth_routes_for_non_connected_provider(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)

    response = _local_client(create_test_app()).get(
        "/admin/api/providers/nvidia_nim/auth"
    )

    assert response.status_code == 404


def test_admin_page_no_longer_renders_generated_env_panel(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()

    response = _local_client(app).get("/admin")

    assert response.status_code == 200
    assert "Generated Env" not in response.text
    assert "envPreview" not in response.text


def test_admin_config_masks_secrets_and_exposes_manifest(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).get("/admin/api/config")

    assert response.status_code == 200
    body = response.json()
    keys = {field["key"] for field in body["fields"]}
    assert "MODEL_FABLE" in keys
    assert "REASONING_FABLE" in keys
    assert "ANTHROPIC_AUTH_TOKEN" in keys
    assert "OPENROUTER_API_KEY" in keys
    assert "DEEPSEEK_API_KEY" in keys
    assert "PECUT_API_KEY" in keys
    assert "DEEPSEEK_SESSION_TOKEN" in keys
    assert "AWS_BEARER_TOKEN_BEDROCK" in keys
    assert "BEDROCK_BASE_URL" in keys
    assert "FIREWORKS_API_KEY" in keys
    assert "CLOUDFLARE_API_TOKEN" in keys
    assert "CLOUDFLARE_ACCOUNT_ID" in keys
    assert "GITHUB_MODELS_TOKEN" in keys
    assert "GEMINI_API_KEY" in keys
    assert "GROQ_API_KEY" in keys
    assert "SAMBANOVA_API_KEY" in keys
    assert "TELEGRAM_PROXY_URL" in keys
    assert "CEREBRAS_API_KEY" in keys
    assert "OLLAMA_API_KEY" in keys
    assert "HANS_OPEN_BROWSER" in keys
    assert "ZAI_BASE_URL" not in keys
    assert "CLAUDE_WORKSPACE" not in keys
    assert "CLAUDE_CLI_BIN" not in keys
    assert "LOG_FILE" not in keys
    auth_field = next(
        field for field in body["fields"] if field["key"] == "ANTHROPIC_AUTH_TOKEN"
    )
    assert auth_field["secret"] is True
    assert auth_field["value"] == MASKED_SECRET
    assert auth_field["source"] == "template"
    telegram_proxy_field = next(
        field for field in body["fields"] if field["key"] == "TELEGRAM_PROXY_URL"
    )
    assert telegram_proxy_field["secret"] is True
    open_browser_field = next(
        field for field in body["fields"] if field["key"] == "HANS_OPEN_BROWSER"
    )
    assert open_browser_field["type"] == "boolean"
    assert open_browser_field["value"] == "true"
    assert open_browser_field["restart_required"] is False
    model_field_types = {
        field["key"]: field["type"]
        for field in body["fields"]
        if field["key"]
        in {"MODEL", "MODEL_FABLE", "MODEL_OPUS", "MODEL_SONNET", "MODEL_HAIKU"}
    }
    assert model_field_types == {
        "MODEL": "model",
        "MODEL_FABLE": "optional_model",
        "MODEL_OPUS": "optional_model",
        "MODEL_SONNET": "optional_model",
        "MODEL_HAIKU": "optional_model",
    }
    reasoning_policy = next(
        field for field in body["fields"] if field["key"] == "REASONING_POLICY"
    )
    assert reasoning_policy["section"] == "reasoning"
    assert reasoning_policy["type"] == "select"
    assert reasoning_policy["value"] == "client"
    assert reasoning_policy["options"] == [
        {"value": "off", "label": "Off"},
        {"value": "client", "label": "From client"},
        {"value": "low", "label": "Low"},
        {"value": "medium", "label": "Medium"},
        {"value": "high", "label": "High"},
        {"value": "xhigh", "label": "X-High"},
        {"value": "max", "label": "Max"},
    ]
    route_reasoning = next(
        field for field in body["fields"] if field["key"] == "REASONING_FABLE"
    )
    assert route_reasoning["options"] == [
        {"value": "inherit", "label": "Inherit"},
        *reasoning_policy["options"],
    ]
    restart_required = {
        field["key"] for field in body["fields"] if field["restart_required"] is True
    }
    assert {
        "ANTHROPIC_AUTH_TOKEN",
        "DEBUG_PLATFORM_EDITS",
        "DEBUG_SUBAGENT_STACK",
        "LOG_RAW_API_PAYLOADS",
        "LOG_API_ERROR_TRACEBACKS",
        "LOG_RAW_MESSAGING_CONTENT",
        "LOG_RAW_CLI_DIAGNOSTICS",
        "LOG_MESSAGING_ERROR_DETAILS",
    } <= restart_required


def test_admin_models_include_configured_and_cached_canonical_slugs():
    settings = Settings()
    settings.model = "nvidia_nim/configured-model"
    settings.model_opus = "open_router/anthropic/configured-opus"
    settings.open_router_api_key = "open-router-key"
    app = create_test_app(settings)
    provider_manager_for_app(app).cache_model_infos(
        "open_router",
        {
            ProviderModelInfo("anthropic/configured-opus"),
            ProviderModelInfo("meta/llama-3.3"),
        },
    )

    response = _local_client(app).get("/admin/api/models")

    assert response.status_code == 200
    assert response.json() == {
        "models": [
            "nvidia_nim/configured-model",
            "open_router/anthropic/configured-opus",
            "open_router/meta/llama-3.3",
        ],
        "failed_providers": [],
    }


def test_admin_model_refresh_returns_the_updated_canonical_catalog():
    settings = Settings()
    settings.model = "deepseek/deepseek-chat"
    settings.deepseek_api_key = "deepseek-key"
    app = create_test_app(settings)
    runtime = app.state.services.admin

    async def refresh_models() -> ProviderModelRefreshResult:
        provider_manager_for_app(app).cache_model_infos(
            "deepseek",
            {ProviderModelInfo("deepseek-reasoner")},
        )
        return ProviderModelRefreshResult(refreshed_provider_ids=("deepseek",))

    runtime.refresh_models = AsyncMock(side_effect=refresh_models)

    response = _local_client(app).post("/admin/api/models/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "models": ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
        "failed_providers": [],
    }
    runtime.refresh_models.assert_awaited_once_with()


def test_admin_model_refresh_reports_partial_provider_failures():
    settings = Settings()
    settings.model = "deepseek/deepseek-chat"
    app = create_test_app(settings)
    runtime = app.state.services.admin
    runtime.refresh_models = AsyncMock(
        return_value=ProviderModelRefreshResult(
            refreshed_provider_ids=("deepseek",),
            failed_provider_ids=("open_router",),
        )
    )

    response = _local_client(app).post("/admin/api/models/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "models": ["deepseek/deepseek-chat"],
        "failed_providers": ["open_router"],
    }


def test_admin_config_preserves_managed_env_source_contract(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("MODEL=open_router/managed-model\n", encoding="utf-8")
    app = create_test_app()

    response = _local_client(app).get("/admin/api/config")

    assert response.status_code == 200
    body = response.json()
    model_field = next(field for field in body["fields"] if field["key"] == "MODEL")
    assert model_field["source"] == "managed_env"
    assert model_field["locked"] is False


def test_admin_apply_persists_open_browser_for_next_launch(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"HANS_OPEN_BROWSER": False}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == []
    assert body["restart"] == {
        "required": False,
        "automatic": False,
        "admin_url": None,
        "fields": [],
    }
    managed_env = tmp_path / ".claudey" / ".env"
    assert "HANS_OPEN_BROWSER=false" in managed_env.read_text(encoding="utf-8")


def test_admin_apply_masks_telegram_proxy_credentials(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()
    proxy_url = "https://user:password@proxy.example:8443"

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"TELEGRAM_PROXY_URL": proxy_url}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "TELEGRAM_PROXY_URL=********" in body["env_preview"]
    assert proxy_url not in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert f"TELEGRAM_PROXY_URL={proxy_url}" in text


def test_admin_validate_rejects_bad_model_shape(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/validate",
        json={"values": {"MODEL": "missing-provider-prefix"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any("provider type" in error for error in body["errors"])


def test_admin_apply_writes_complete_managed_env_and_masks_preview(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "open_router/test-model",
                "OPENROUTER_API_KEY": "router-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "OPENROUTER_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text("utf-8")
    assert "MODEL=open_router/test-model" in text
    assert "OPENROUTER_API_KEY=router-secret" in text
    assert "ANTHROPIC_AUTH_TOKEN=" in text
    assert body["restart"] == {
        "required": False,
        "automatic": False,
        "admin_url": None,
        "fields": [],
    }


def test_admin_apply_writes_fireworks_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "fireworks/test-model",
                "FIREWORKS_API_KEY": "fw-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "FIREWORKS_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=fireworks/test-model" in text
    assert "FIREWORKS_API_KEY=fw-secret" in text


def test_admin_apply_writes_gemini_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "gemini/models/gemini-3.1-flash-lite",
                "GEMINI_API_KEY": "gm-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "GEMINI_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=gemini/models/gemini-3.1-flash-lite" in text
    assert "GEMINI_API_KEY=gm-secret" in text


def test_admin_apply_writes_groq_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "groq/llama-3.3-70b-versatile",
                "GROQ_API_KEY": "gq-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "GROQ_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=groq/llama-3.3-70b-versatile" in text
    assert "GROQ_API_KEY=gq-secret" in text


def test_admin_apply_writes_sambanova_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "sambanova/Meta-Llama-3.3-70B-Instruct",
                "SAMBANOVA_API_KEY": "sn-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "SAMBANOVA_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=sambanova/Meta-Llama-3.3-70B-Instruct" in text
    assert "SAMBANOVA_API_KEY=sn-secret" in text


def test_admin_apply_writes_cerebras_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "cerebras/llama3.1-8b",
                "CEREBRAS_API_KEY": "cb-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "CEREBRAS_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=cerebras/llama3.1-8b" in text
    assert "CEREBRAS_API_KEY=cb-secret" in text


def test_admin_apply_writes_bedrock_region_config_and_masks_key(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "bedrock/openai.gpt-oss-120b",
                "AWS_BEARER_TOKEN_BEDROCK": "bedrock-secret",
                "BEDROCK_BASE_URL": ("https://bedrock-mantle.us-west-2.api.aws/v1"),
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "AWS_BEARER_TOKEN_BEDROCK=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=bedrock/openai.gpt-oss-120b" in text
    assert "AWS_BEARER_TOKEN_BEDROCK=bedrock-secret" in text
    assert "BEDROCK_BASE_URL=https://bedrock-mantle.us-west-2.api.aws/v1" in text


def test_admin_apply_writes_cloudflare_fields_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "cloudflare/@cf/moonshotai/kimi-k2.6",
                "CLOUDFLARE_API_TOKEN": "cf-secret",
                "CLOUDFLARE_ACCOUNT_ID": "cf-account",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "CLOUDFLARE_API_TOKEN=********" in body["env_preview"]
    assert "CLOUDFLARE_ACCOUNT_ID=cf-account" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=cloudflare/@cf/moonshotai/kimi-k2.6" in text
    assert "CLOUDFLARE_API_TOKEN=cf-secret" in text
    assert "CLOUDFLARE_ACCOUNT_ID=cf-account" in text


def test_admin_apply_writes_huggingface_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "huggingface/openai/gpt-oss-120b:fastest",
                "HUGGINGFACE_API_KEY": "hf-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == []
    assert "HUGGINGFACE_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=huggingface/openai/gpt-oss-120b:fastest" in text
    assert "HUGGINGFACE_API_KEY=hf-secret" in text


@pytest.mark.parametrize(
    ("device", "credential_key"),
    [
        ("nvidia_nim", "NVIDIA_NIM_API_KEY"),
        ("cpu", "HUGGINGFACE_API_KEY"),
    ],
)
def test_admin_key_change_requires_restart_for_active_voice_backend(
    monkeypatch,
    tmp_path,
    device,
    credential_key,
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                "VOICE_NOTE_ENABLED=true",
                f"WHISPER_DEVICE={device}",
                f"{credential_key}=old-key",
                "",
            ]
        ),
        encoding="utf-8",
    )
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {credential_key: "new-key"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == [credential_key]
    assert body["restart"] == {
        "required": True,
        "automatic": False,
        "admin_url": None,
        "fields": [credential_key],
    }


@pytest.mark.parametrize(
    ("key", "initial", "updated"),
    [
        ("ANTHROPIC_AUTH_TOKEN", "old-token", "new-token"),
        ("DEBUG_PLATFORM_EDITS", "true", "false"),
        ("DEBUG_SUBAGENT_STACK", "true", "false"),
        ("LOG_RAW_API_PAYLOADS", "true", "false"),
        ("LOG_API_ERROR_TRACEBACKS", "true", "false"),
        ("LOG_RAW_MESSAGING_CONTENT", "true", "false"),
        ("LOG_RAW_CLI_DIAGNOSTICS", "true", "false"),
        ("LOG_MESSAGING_ERROR_DETAILS", "true", "false"),
    ],
)
def test_admin_constructor_captured_setting_requires_restart(
    monkeypatch,
    tmp_path,
    key,
    initial,
    updated,
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(f"{key}={initial}\n", encoding="utf-8")
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {key: updated}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == [key]
    assert body["restart"] == {
        "required": True,
        "automatic": False,
        "admin_url": None,
        "fields": [key],
    }


def test_admin_apply_writes_cohere_key_and_masks_preview(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "cohere/command-a-plus-05-2026",
                "COHERE_API_KEY": "cohere-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "COHERE_API_KEY=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=cohere/command-a-plus-05-2026" in text
    assert "COHERE_API_KEY=cohere-secret" in text


def test_admin_apply_writes_github_models_token_and_masks_preview(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={
            "values": {
                "MODEL": "github_models/openai/gpt-4.1",
                "GITHUB_MODELS_TOKEN": "github-secret",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "GITHUB_MODELS_TOKEN=********" in body["env_preview"]
    env_file = tmp_path / ".claudey" / ".env"
    text = env_file.read_text(encoding="utf-8")
    assert "MODEL=github_models/openai/gpt-4.1" in text
    assert "GITHUB_MODELS_TOKEN=github-secret" in text


def test_admin_apply_preserves_hidden_diagnostics_and_smoke_values(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                "MODEL=nvidia_nim/old-model",
                "LOG_RAW_API_PAYLOADS=true",
                "HANS_SMOKE_MODEL_ZAI=zai/smoke-model",
                "",
            ]
        ),
        encoding="utf-8",
    )
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"MODEL": "open_router/test-model"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    text = env_file.read_text("utf-8")
    assert "MODEL=open_router/test-model" in text
    assert "LOG_RAW_API_PAYLOADS=true" in text
    assert "HANS_SMOKE_MODEL_ZAI=zai/smoke-model" in text


def test_admin_apply_omits_stale_zai_base_url(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                "MODEL=zai/glm-5.2",
                "ZAI_API_KEY=zai-secret",
                "ZAI_BASE_URL=https://custom.zai.invalid/v1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"MODEL": "zai/glm-5.2"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    text = env_file.read_text("utf-8")
    assert "ZAI_API_KEY=zai-secret" in text
    assert "ZAI_BASE_URL" not in text


def test_admin_apply_omits_stale_fixed_claude_runtime_settings(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    env_file = tmp_path / ".claudey" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                "MODEL=open_router/test-model",
                "CLAUDE_WORKSPACE=C:/custom/workspace",
                "CLAUDE_CLI_BIN=claude-custom",
                "",
            ]
        ),
        encoding="utf-8",
    )
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"MODEL": "open_router/test-model"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    text = env_file.read_text("utf-8")
    assert "MODEL=open_router/test-model" in text
    assert "CLAUDE_WORKSPACE" not in text
    assert "CLAUDE_CLI_BIN" not in text


def test_admin_apply_restart_required_reports_automatic_restart(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    callbacks: list[str] = []

    async def restart_callback() -> None:
        callbacks.append("restart")

    app = create_test_app(restart_callback=restart_callback)

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"PORT": "9090"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == ["PORT"]
    assert body["restart"] == {
        "required": True,
        "automatic": True,
        "admin_url": "http://127.0.0.1:9090/admin",
        "fields": ["PORT"],
    }
    assert callbacks == ["restart"]


def test_admin_apply_restart_required_reports_manual_fallback(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"PORT": "9091"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["pending_fields"] == ["PORT"]
    assert body["restart"] == {
        "required": True,
        "automatic": False,
        "admin_url": None,
        "fields": ["PORT"],
    }


def test_admin_restart_endpoint_triggers_restart(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    callbacks: list[str] = []

    async def restart_callback() -> None:
        callbacks.append("restart")

    app = create_test_app(restart_callback=restart_callback)

    response = _local_client(app).post("/admin/api/restart")

    assert response.status_code == 200
    assert response.json() == {"restarting": True, "admin_url": "/admin"}
    assert callbacks == ["restart"]


def test_admin_restart_endpoint_is_loopback_only(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    remote_client = TestClient(app, client=("203.0.113.10", 50000))
    response = remote_client.post("/admin/api/restart")

    assert response.status_code == 403


def test_admin_process_env_values_are_locked_and_not_written(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("MODEL", "open_router/process-model")
    app = create_test_app()

    config = _local_client(app).get("/admin/api/config").json()
    model_field = next(field for field in config["fields"] if field["key"] == "MODEL")
    assert model_field["locked"] is True
    assert model_field["source"] == "process"

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"MODEL": "deepseek/managed-model"}},
    )

    assert response.status_code == 200
    env_file = tmp_path / ".claudey" / ".env"
    assert "deepseek/managed-model" not in env_file.read_text("utf-8")


def test_admin_first_apply_migrates_repo_env(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "MODEL=deepseek/deepseek-chat\nDEEPSEEK_API_KEY=deepseek-secret\n",
        encoding="utf-8",
    )
    app = create_test_app()

    config = _local_client(app).get("/admin/api/config").json()
    model_field = next(field for field in config["fields"] if field["key"] == "MODEL")
    assert model_field["value"] == "deepseek/deepseek-chat"
    assert model_field["source"] == "repo_env"

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {}},
    )

    assert response.status_code == 200
    managed_text = (tmp_path / ".claudey" / ".env").read_text("utf-8")
    assert "MODEL=deepseek/deepseek-chat" in managed_text
    assert "DEEPSEEK_API_KEY=deepseek-secret" in managed_text


def test_admin_deepseek_session_token_applies_and_persists(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    config = _local_client(app).get("/admin/api/config").json()
    field = next(
        field for field in config["fields"] if field["key"] == "DEEPSEEK_SESSION_TOKEN"
    )
    assert field["secret"] is True
    assert field["type"] == "secret"
    # Empty secrets are exposed as empty (only non-empty values are masked).
    assert field["value"] == ""

    response = _local_client(app).post(
        "/admin/api/config/apply",
        json={"values": {"DEEPSEEK_SESSION_TOKEN": "user-tok-123"}},
    )

    assert response.status_code == 200
    assert response.json()["applied"] is True
    managed_text = (tmp_path / ".claudey" / ".env").read_text("utf-8")
    assert "DEEPSEEK_SESSION_TOKEN=user-tok-123" in managed_text


def test_admin_local_provider_status_reports_reachable(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            return httpx.Response(200, json={"data": []})

    with patch("claudey.api.admin_routes.httpx.AsyncClient", FakeAsyncClient):
        response = _local_client(app).get("/admin/api/providers/local-status")

    assert response.status_code == 200
    providers = response.json()["providers"]
    assert {provider["status"] for provider in providers} == {"reachable"}


def test_admin_launch_url_uses_loopback_for_wildcard_host():
    settings = Settings.model_construct(host="0.0.0.0", port=8082)

    assert local_admin_url(settings) == "http://127.0.0.1:8082/admin"


def test_admin_dashboard_endpoint_loopback_and_shape(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    with patch("claudey.api.admin_dashboard.usd_to_idr", return_value=18000.0):
        app = create_test_app()
        response = _local_client(app).get("/admin/api/dashboard")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert set(payload) == {
        "commits",
        "stats",
        "usd_to_idr",
        "monthly_spend_usd",
        "monthly_limit_usd",
    }
    assert payload["usd_to_idr"] == 18000.0
    assert isinstance(payload["monthly_spend_usd"], (int, float))
    assert payload["monthly_limit_usd"] == 100.0
    assert payload["stats"] == {"agents": 0, "skills": 0}
    # Commits come from the real repo; only the shape is asserted.
    for commit in payload["commits"]:
        assert set(commit) == {
            "hash",
            "short",
            "subject",
            "date_iso",
            "tokens",
            "cost_usd",
        }


def test_admin_dashboard_is_loopback_only(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()
    client = TestClient(app, client=("203.0.113.10", 50000))

    assert client.get("/admin/api/dashboard").status_code == 403


def test_dashboard_payload_attributes_usage_to_commit_windows(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    metrics = tmp_path / ".claude" / "metrics" / "costs.jsonl"
    metrics.parent.mkdir(parents=True)
    project_dir = str(repo).replace("/", "-")

    def entry(timestamp: str, tokens: int, cost: float) -> str:
        payload = {
            "timestamp": timestamp,
            "transcript_path": f"/x/.claude/projects/{project_dir}/session.jsonl",
            "input_tokens": tokens,
            "output_tokens": 0,
            "estimated_cost_usd": cost,
        }
        return json.dumps(payload)

    # Newest-first commit list; windows are (next-older commit, this commit].
    commits = [
        {
            "hash": "c" * 40,
            "short": "c" * 7,
            "subject": "newest",
            "date_iso": "2026-08-05T04:00:00+00:00",
        },
        {
            "hash": "b" * 40,
            "short": "b" * 7,
            "subject": "middle",
            "date_iso": "2026-08-05T02:30:00+00:00",
        },
        {
            "hash": "a" * 40,
            "short": "a" * 7,
            "subject": "oldest",
            "date_iso": "2026-08-05T00:30:00+00:00",
        },
    ]
    lines = [
        entry("2026-08-05T00:00:00+00:00", 100, 0.01),  # oldest window
        entry("2026-08-05T01:00:00+00:00", 200, 0.02),  # oldest window
        entry("2026-08-05T02:00:00+00:00", 300, 0.03),  # oldest window
        entry("2026-08-05T03:00:00+00:00", 400, 0.04),  # newest window
        entry("2026-08-05T04:00:00+00:00", 500, 0.05),  # newest window (inclusive)
        entry("2026-08-05T02:30:00+00:00", 600, 0.06),  # middle window (inclusive)
    ]
    metrics.write_text("\n".join(lines) + "\n")

    with (
        patch("claudey.api.admin_dashboard.latest_commits", return_value=commits),
        patch("claudey.api.admin_dashboard.usd_to_idr", return_value=18000.0),
    ):
        payload = admin_dashboard.dashboard_payload(home=tmp_path, repo_root=repo)

    assert payload["usd_to_idr"] == 18000.0
    assert payload["stats"] == {"agents": 0, "skills": 0}
    newest, middle, oldest = payload["commits"]
    assert (newest["tokens"], newest["cost_usd"]) == (900, 0.09)
    assert (middle["tokens"], middle["cost_usd"]) == (1100, 0.11)
    assert (oldest["tokens"], oldest["cost_usd"]) == (100, 0.01)


def test_dashboard_payload_degrades_when_sources_missing(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    with patch("claudey.api.admin_dashboard.usd_to_idr", return_value=18000.0):
        payload = admin_dashboard.dashboard_payload(
            home=tmp_path, repo_root=tmp_path / "missing"
        )

    assert payload["commits"] == []
    assert payload["stats"] == {"agents": 0, "skills": 0}


def test_dashboard_counts_agents_and_skills_deduplicated(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "planner.md").write_text("x", encoding="utf-8")
    (tmp_path / ".claude" / "agents" / "reviewer.md").write_text("x", encoding="utf-8")
    skills = tmp_path / ".claude" / "skills"
    (skills / "alpha" / "SKILL.md").parent.mkdir(parents=True)
    (skills / "alpha" / "SKILL.md").write_text("x", encoding="utf-8")
    (skills / "beta" / "SKILL.md").parent.mkdir(parents=True)
    (skills / "beta" / "SKILL.md").write_text("x", encoding="utf-8")
    (skills / "alpha" / "SKILL.md").unlink()  # keep alpha via marketplace below
    marketplaces = tmp_path / ".claude" / "plugins" / "marketplaces"
    (marketplaces / "ecc" / "agents" / "planner.md").parent.mkdir(parents=True)
    (marketplaces / "ecc" / "agents" / "planner.md").write_text("x", encoding="utf-8")
    (marketplaces / "ecc" / "skills" / "alpha" / "SKILL.md").parent.mkdir(parents=True)
    (marketplaces / "ecc" / "skills" / "alpha" / "SKILL.md").write_text(
        "x", encoding="utf-8"
    )

    counts = admin_dashboard.agents_skills_counts(tmp_path)

    # planner.md appears in both places but counts once.
    assert counts == {"agents": 2, "skills": 2}


def test_usd_to_idr_falls_back_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(
        admin_dashboard, "_rate_cache", {"rate": None, "fetched_at": None}
    )
    with patch(
        "claudey.api.admin_dashboard.httpx.Client", side_effect=OSError("offline")
    ):
        assert admin_dashboard.usd_to_idr() == admin_dashboard.USD_IDR_FALLBACK


def test_admin_usage_endpoint_is_loopback_only(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()
    client = TestClient(app, client=("203.0.113.10", 50000))

    assert client.get("/admin/api/usage").status_code == 403


def test_admin_usage_endpoint_degrades_when_log_missing(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    with patch(
        "claudey.api.deepseek_billing.get_settings",
        return_value=Settings.model_construct(
            deepseek_session_token="", deepseek_api_key=""
        ),
    ):
        response = _local_client(create_test_app()).get("/admin/api/usage")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert set(payload) == {
        "available",
        "total_entries",
        "last_updated",
        "totals",
        "windows",
        "daily",
        "models",
        "providers",
        "heatmap",
        "billing",
    }
    assert "sources" not in payload
    assert payload["available"] is False
    assert payload["total_entries"] == 0
    assert payload["last_updated"] is None


def test_admin_usage_endpoint_includes_billing_with_expected_subkeys(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    with patch(
        "claudey.api.deepseek_billing.get_settings",
        return_value=Settings.model_construct(
            deepseek_session_token="", deepseek_api_key=""
        ),
    ):
        payload = _local_client(create_test_app()).get("/admin/api/usage").json()

    billing = payload["billing"]
    assert set(billing) == {
        "available",
        "configured",
        "status",
        "total_cost_usd",
        "total_tokens",
        "total_requests",
        "balance_usd",
        "currency",
        "days",
        "last_synced",
    }
    assert billing["configured"] is False
    assert billing["status"] == "not_configured"
    assert billing["available"] is False
    assert billing["days"] == []
    assert billing["total_cost_usd"] == 0.0
    assert billing["total_tokens"] == 0
    assert billing["total_requests"] == 0
    assert billing["balance_usd"] is None
    assert billing["currency"] is None
    assert billing["last_synced"] is None


def test_admin_usage_endpoint_returns_aggregated_data(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    log = tmp_path / ".claudey" / "usage.jsonl"
    log.parent.mkdir(parents=True)
    ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    lines = [
        json.dumps(
            {
                "ts": ts,
                "request_id": "req_1",
                "wire_api": "messages",
                "provider_id": "nvidia_nim",
                "provider_model": "m1",
                "original_model": "nvidia_nim/m1",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "conversations": 1,
            }
        ),
        json.dumps(
            {
                "ts": ts,
                "request_id": "req_2",
                "wire_api": "messages",
                "provider_id": "open_router",
                "provider_model": "m2",
                "original_model": "open_router/m2",
                "input_tokens": 20,
                "output_tokens": 10,
                "cached_input_tokens": 2,
                "total_tokens": 32,
                "conversations": 1,
            }
        ),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    response = _local_client(create_test_app()).get("/admin/api/usage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["total_entries"] == 2
    assert payload["totals"]["total_tokens"] == 47
    assert payload["totals"]["cached_input_tokens"] == 2
    assert payload["totals"]["conversations"] == 2
    assert payload["windows"]["24h"] == 47
    assert payload["models"] == [
        {
            "model": "m2",
            "provider_id": "open_router",
            "total_tokens": 32,
            "conversations": 1,
        },
        {
            "model": "m1",
            "provider_id": "nvidia_nim",
            "total_tokens": 15,
            "conversations": 1,
        },
    ]
    assert payload["providers"] == [
        {
            "provider": "open_router",
            "total_tokens": 32,
            "conversations": 1,
            "model_count": 1,
        },
        {
            "provider": "nvidia_nim",
            "total_tokens": 15,
            "conversations": 1,
            "model_count": 1,
        },
    ]
    assert len(payload["daily"]) == 30
    assert len(payload["heatmap"]["weeks"]) == 52


def test_admin_usage_payload_uses_providers_not_sources(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    log = tmp_path / ".claudey" / "usage.jsonl"
    log.parent.mkdir(parents=True)
    ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": ts,
                        "request_id": "req_1",
                        "wire_api": "messages",
                        "provider_id": "nvidia_nim",
                        "provider_model": "m1",
                        "original_model": "nvidia_nim/m1",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "conversations": 1,
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = _local_client(create_test_app()).get("/admin/api/usage").json()

    assert "sources" not in payload
    assert payload["providers"][0]["provider"] == "nvidia_nim"


@pytest.fixture
def custom_store_path(monkeypatch, tmp_path):
    """Isolate the process-wide custom-provider store for an admin test."""
    store_path = tmp_path / "custom-providers.json"
    monkeypatch.setenv("CLAUDEY_CUSTOM_PROVIDERS_PATH", str(store_path))
    return store_path


def _custom_client(app, *, remote=False):
    if remote:
        return TestClient(app, client=("203.0.113.10", 50000))
    return TestClient(app, client=("127.0.0.1", 50000))


def test_admin_custom_providers_crud(monkeypatch, tmp_path, custom_store_path):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    created = client.post(
        "/admin/api/providers/custom",
        json={
            "type": "openai",
            "name": "Acme",
            "base_url": "https://api.acme.example/v1",
            "api_key": "sk-acme-secret",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["success"] is True
    assert payload["provider_id"].startswith("custom_acme")
    assert payload["has_api_key"] is True
    assert "api_key" not in payload

    listed = client.get("/admin/api/providers/custom")
    assert listed.status_code == 200
    providers = listed.json()["providers"]
    assert len(providers) == 1
    assert providers[0]["provider_id"] == payload["provider_id"]
    assert "api_key" not in providers[0]

    deleted = client.delete(f"/admin/api/providers/custom/{payload['provider_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    assert client.get("/admin/api/providers/custom").json()["providers"] == []


def test_admin_custom_provider_generates_unique_id_on_duplicate_name(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())
    body = {
        "type": "openai",
        "name": "Acme",
        "base_url": "https://api.acme.example/v1",
        "api_key": "sk-acme",
    }
    first = client.post("/admin/api/providers/custom", json=body).json()
    second = client.post("/admin/api/providers/custom", json=body).json()

    assert first["provider_id"] == "custom_acme"
    assert second["provider_id"] == "custom_acme_2"


def test_admin_custom_provider_rejects_invalid_type(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom",
        json={
            "type": "garbage",
            "name": "Acme",
            "base_url": "https://api.acme.example/v1",
        },
    )

    assert response.status_code == 400
    assert "provider type" in response.json()["detail"].lower()


def test_admin_custom_provider_rejects_bad_base_url(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom",
        json={"type": "openai", "name": "Acme", "base_url": "not-a-url"},
    )

    assert response.status_code == 400
    assert "url" in response.json()["detail"].lower()


def test_admin_custom_provider_rejects_missing_name(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom",
        json={
            "type": "openai",
            "name": "   ",
            "base_url": "https://api.acme.example/v1",
        },
    )

    assert response.status_code == 400


def test_admin_custom_provider_delete_missing_returns_404(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    response = client.delete("/admin/api/providers/custom/custom_nope")

    assert response.status_code == 404


def test_admin_custom_providers_are_loopback_only(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    remote = _custom_client(create_test_app(), remote=True)

    assert remote.get("/admin/api/providers/custom").status_code == 403
    assert (
        remote.post(
            "/admin/api/providers/custom",
            json={
                "type": "openai",
                "name": "Acme",
                "base_url": "https://api.acme.example/v1",
            },
        ).status_code
        == 403
    )
    assert remote.delete("/admin/api/providers/custom/custom_acme").status_code == 403


def test_admin_custom_provider_appears_in_config_provider_status(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    from claudey.config.custom_providers import (
        CustomProviderRecord,
        custom_provider_store,
    )

    custom_provider_store().upsert(
        CustomProviderRecord(
            provider_id="custom_acme",
            display_name="Acme",
            compatible="anthropic",
            base_url="https://api.acme.example/anthropic",
            api_key="sk-acme",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    client = _custom_client(create_test_app())

    response = client.get("/admin/api/config")
    assert response.status_code == 200
    statuses = response.json()["provider_status"]
    custom = [s for s in statuses if s["provider_id"] == "custom_acme"]
    assert len(custom) == 1
    assert custom[0]["kind"] == "custom"
    assert custom[0]["compatible"] == "anthropic"
    assert custom[0]["status"] == "configured"
    assert "api_key" not in custom[0]


def test_admin_custom_provider_validate_returns_result(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    from claudey.config import custom_provider_check

    async def fake_check(base_url, api_key, compatible, model_id=None, **kwargs):
        assert compatible == "openai"
        assert model_id == "gpt-4o-mini"
        return {"valid": True, "method": "models", "error": None}

    monkeypatch.setattr(
        custom_provider_check, "check_compatible_connection", fake_check
    )
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom/validate",
        json={
            "base_url": "https://api.acme.example/v1",
            "api_key": "sk-key",
            "type": "openai",
            "model_id": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"valid": True, "method": "models", "error": None}


def test_admin_custom_provider_validate_invalid_type(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    from claudey.config import custom_provider_check

    called = False

    async def fake_check(*args, **kwargs):
        nonlocal called
        called = True
        return {"valid": False, "method": None, "error": "unused"}

    monkeypatch.setattr(
        custom_provider_check, "check_compatible_connection", fake_check
    )
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom/validate",
        json={"base_url": "https://api.acme.example/v1", "type": "garbage"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["error"] == "Invalid provider type."
    assert called is False


def test_admin_custom_provider_validate_bad_type_upper_ok(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    from claudey.config import custom_provider_check

    async def fake_check(base_url, api_key, compatible, model_id=None, **kwargs):
        assert compatible == "anthropic"
        return {"valid": True, "method": "chat", "error": None}

    monkeypatch.setattr(
        custom_provider_check, "check_compatible_connection", fake_check
    )
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom/validate",
        json={
            "base_url": "https://api.acme.example",
            "api_key": "k",
            "type": "ANTHROPIC",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_admin_custom_provider_validate_bad_base_url_fails_closed(
    monkeypatch, tmp_path, custom_store_path
):
    """A blank base URL must fail closed in the probe without any network."""

    _set_home(monkeypatch, tmp_path)
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom/validate",
        json={"base_url": "", "api_key": "sk-key", "type": "openai"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["method"] is None
    assert "Base URL" in body["error"]


def test_admin_custom_provider_validate_returns_chat_method(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    from claudey.config import custom_provider_check

    async def fake_check(base_url, api_key, compatible, model_id=None, **kwargs):
        return {"valid": True, "method": "chat", "error": None}

    monkeypatch.setattr(
        custom_provider_check, "check_compatible_connection", fake_check
    )
    client = _custom_client(create_test_app())

    response = client.post(
        "/admin/api/providers/custom/validate",
        json={
            "base_url": "https://api.acme.example",
            "api_key": "sk-key",
            "type": "openai",
            "model_id": "custom-model",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "method": "chat", "error": None}


def test_admin_custom_provider_validate_is_loopback_only(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    remote = _custom_client(create_test_app(), remote=True)

    response = remote.post(
        "/admin/api/providers/custom/validate",
        json={"base_url": "https://api.acme.example", "type": "openai"},
    )

    assert response.status_code == 403


def test_admin_custom_provider_status_missing_key(
    monkeypatch, tmp_path, custom_store_path
):
    _set_home(monkeypatch, tmp_path)
    from claudey.config.custom_providers import (
        CustomProviderRecord,
        custom_provider_store,
    )

    custom_provider_store().upsert(
        CustomProviderRecord(
            provider_id="custom_keyless",
            display_name="Keyless",
            compatible="openai",
            base_url="https://api.keyless.example/v1",
            api_key="",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    client = _custom_client(create_test_app())

    response = client.get("/admin/api/config")
    statuses = response.json()["provider_status"]
    custom = next(s for s in statuses if s["provider_id"] == "custom_keyless")
    assert custom["status"] == "missing_key"
