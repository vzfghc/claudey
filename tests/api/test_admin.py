from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

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


@pytest.mark.parametrize(
    "path",
    (
        "/admin",
        "/admin/assets/admin.css",
        "/admin/assets/admin.js",
        "/admin/assets/admin-animations.css",
        "/admin/assets/admin-animations.js",
        "/admin/api/config",
    ),
)
def test_admin_responses_are_never_cached(monkeypatch, tmp_path, path):
    _set_home(monkeypatch, tmp_path)
    response = _local_client(create_test_app()).get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


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


def test_admin_api_fetches_bypass_browser_cache():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'cache: "no-store"' in script


def test_admin_connected_account_login_preopens_sign_in_window():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'window.open("about:blank", "_blank")' in script
    assert "popup.location.replace(target)" in script
    assert "if (popup) popup.close()" in script
    assert '"Reconnect"' in script
    assert '"Copy code"' in script
    assert "Restart your agent to refresh its model picker." in script
    assert 'window.confirm("Disconnect this ChatGPT account from Claudey?")' in script


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


def test_admin_provider_cards_support_non_key_configuration():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert '"missing_config"' in script
    assert "provider.configuration.split" in script  # used by primary field resolver


def test_admin_page_no_longer_renders_generated_env_panel(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()

    response = _local_client(app).get("/admin")

    assert response.status_code == 200
    assert "Generated Env" not in response.text
    assert "envPreview" not in response.text


def test_admin_page_renders_server_status_pill(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    app = create_test_app()

    response = _local_client(app).get("/admin")

    assert response.status_code == 200
    assert 'id="serverStatusPill"' in response.text
    assert 'class="toast-container"' in response.text
    assert 'id="onboardingCard"' in response.text
    assert "aria-keyshortcuts" in response.text
    assert "Local Admin" not in response.text
    assert "modelBadge" not in response.text


def test_admin_static_renders_server_status_pill():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'api("/admin/api/status")' in script
    assert "serverStatusPill" in script
    assert '"Claudey Admin"' in script
    assert "Running on :" in script
    assert "updateHeader" not in script
    assert "modelBadge" not in script


def test_admin_static_guards_unsaved_changes_on_close():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'window.addEventListener("beforeunload",' in script
    assert "event.returnValue" in script
    assert "suppressBeforeUnload" in script
    assert "changedValues()).length" in script
    # The apply-triggered restart navigation must not trip the guard.
    assert "suppressBeforeUnload = true" in script


def test_admin_static_nav_renders_icon_rail_with_labels():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    assert 'icon: `<svg viewBox="0 0 24 24"' in script
    assert 'className = "nav-icon"' in script
    assert 'className = "nav-label"' in script
    assert ".nav-label" in styles
    # Below 900px the sidebar collapses to an icon rail with labels hidden.
    assert "@media (max-width: 900px)" in styles
    assert ".nav-label {\n    display: none;" in styles
    assert "min-height: 44px" in styles


def test_admin_static_buttons_meet_40px_touch_targets():
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    assert "min-height: 40px;" in styles
    assert "min-height: 36px;" not in styles


def test_admin_static_hides_managed_source_label():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'managed_env: "",' in script
    assert "hasOwnProperty.call(labels, source)" in script
    assert 'parts.push("locked")' in script
    assert "sourceEl.textContent = source" in script


def test_admin_static_places_reasoning_fields_in_model_config():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert 'sections: ["models", "reasoning", "web_tools"]' in script
    assert 'sections: ["models", "thinking", "web_tools"]' not in script


def test_admin_static_model_combobox_owns_dropdown_and_search_behavior():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    assert 'api("/admin/api/models" + (refresh ? "/refresh" : "")' in script
    assert 'field.type === "model" || field.type === "optional_model"' in script
    assert 'input.setAttribute("role", "combobox")' in script
    assert 'listbox.setAttribute("role", "listbox")' in script
    assert 'toggle.className = "model-combobox-toggle"' in script
    assert "class ModelCombobox" in script
    assert 'input.addEventListener("click", () => this.open())' in script
    assert "value.toLocaleLowerCase().includes(normalizedQuery)" in script
    assert 'event.key === "ArrowDown" || event.key === "ArrowUp"' in script
    assert "this.setActive(this.visibleOptions.length - 1)" in script
    assert 'event.key === "Enter"' in script
    assert 'event.key === "Escape"' in script
    assert 'document.createElement("datalist")' not in script
    assert ".model-combobox-list" in styles
    assert ".model-combobox-option.active" in styles
    assert styles.count("background-image: var(--dropdown-chevron)") == 2


def test_admin_static_model_combobox_preserves_custom_slugs_and_none_semantics():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert '? ["None", ...state.modelOptions]' in script
    assert "You can still enter a custom slug." in script
    assert 'input.dataset.fieldType === "optional_model"' in script
    assert 'return "";' in script
    assert "await hydrateModelOptions();" in script
    assert "Model fields remain editable" in script
    assert "result.failed_providers || []" in script
    assert '"warn"' in script


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


def test_admin_static_html_loads_animation_assets_in_order():
    html = Path("src/claudey/api/admin_static/index.html").read_text(encoding="utf-8")

    # The animations layer loads after the base admin styles.
    assert html.index("admin-animations.css") > html.index("admin.css")
    # The ES module loads after admin.js and is declared as a module.
    assert html.index("admin-animations.js") > html.index("admin.js")
    assert 'type="module"' in html
    # The marquee is the first child of the providers view.
    providers = html.index('id="view-providers"')
    marquee = html.index('class="provider-marquee"')
    onboarding = html.index('id="onboardingCard"')
    assert providers < marquee < onboarding


def test_admin_static_sidebar_tween_contract():
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")
    animations = Path("src/claudey/api/admin_static/admin-animations.css").read_text(
        encoding="utf-8"
    )

    # The toggle is exposed for admin.js and delegates state to it.
    assert "window.__sidebarTweenToggle" in module
    assert "window.applySidebarCollapsed" in module
    # Per-frame inline writes, not a CSS transition.
    assert "requestAnimationFrame" in module
    assert "sidebar.style.width" in module
    assert 'document.documentElement.style.setProperty("--sidebar-w"' in module
    assert "easeOutQuint" in module
    assert "1 - Math.pow(1 - t, 5)" in module
    assert "cancelAnimationFrame" in module
    assert "parseFloat(sidebar.style.width)" in module
    assert "collapseMs: 350" in module
    assert "expandMs: 220" in module
    assert "collapsed: 64" in module
    assert "expanded: 256" in module
    # The rail class is added only once the tween completes.
    assert 'document.body.classList.add("sidebar-rail")' in module
    # CSS: the width transition is gone; the action bar follows the var.
    assert "transition: width var(--transition-normal)" not in styles
    assert "left: var(--sidebar-w, 256px)" in styles
    assert ":root {\n  --sidebar-w: 256px;" in animations
    # No-JS fallback keeps the collapsed width at 64px.
    assert "body.sidebar-collapsed .sidebar {\n    width: 64px;" in styles


def test_admin_static_sidebar_click_delegates_to_tween():
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    assert "if (window.__sidebarTweenToggle) {" in script
    assert "window.__sidebarTweenToggle();" in script
    assert (
        'applySidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));'
    ) in script
    # State and aria ownership stay with admin.js.
    assert 'sidebarToggle.setAttribute("aria-expanded"' in script
    assert "sectionNav.inert" in script


def test_admin_static_nav_uses_shared_sliding_pills_on_desktop():
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    animations = Path("src/claudey/api/admin_static/admin-animations.css").read_text(
        encoding="utf-8"
    )
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    assert "MutationObserver" in module
    assert 'className = "nav-pill nav-pill-active"' in module
    assert 'className = "nav-pill nav-pill-hover"' in module
    assert 'setAttribute("aria-hidden", "true")' in module
    assert "NAV_PITCH" in module
    assert "nav-pills-ready" in module
    assert "pointermove" in module
    assert "DESKTOP.matches" in module
    # Pill styles live at >=901px; per-item highlights are mobile-only.
    assert "@media (min-width: 901px)" in animations
    assert ".nav-pill-active" in animations
    assert "transform 0.2s cubic-bezier(0.22, 1, 0.36, 1)" in animations
    assert "pointer-events: none" in animations
    assert ".nav-pill {\n    display: none;" in animations
    assert "@media (max-width: 900px)" in animations
    assert "body.sidebar-rail .nav-label {\n    visibility: hidden;" in animations
    # The old desktop per-item highlight is gone from admin.css...
    assert ".nav-link.active {\n  background: var(--accent-muted);" not in styles
    # ...and lives inside the mobile block now.
    mobile = styles.index("@media (max-width: 900px)")
    assert styles.index(".nav-link.active", mobile) > mobile


def test_admin_static_buttons_lift_and_press():
    animations = Path("src/claudey/api/admin_static/admin-animations.css").read_text(
        encoding="utf-8"
    )
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    # Primary base: inner glow + ambient + contact shadows.
    assert "inset 0 -6px 12px rgba(224, 77, 10, 0.25)" in animations
    assert "0 2px 4px rgba(250, 93, 25, 0.12)" in animations
    # Hover lift adds a larger drop plus a 1px ring.
    assert "0 4px 8px rgba(250, 93, 25, 0.16)" in animations
    assert "0 0 0 1px rgba(250, 93, 25, 0.12)" in animations
    # Press contracts the glow and sinks the button.
    assert "inset 0 -3px 6px rgba(224, 77, 10, 0.3)" in animations
    assert "scale(0.995)" in animations
    assert "transition-duration: 0.2s, 0.2s, 0.2s, 0.05s, 0.05s" in animations
    # Sheen overlay: white-to-transparent gradient, 0.06/0.08/0.
    assert (
        "linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0))"
    ) in animations
    assert "opacity: 0.06" in animations
    assert "opacity: 0.08" in animations
    # Disabled: no elevation, no sheen.
    assert (
        ".primary-button:disabled,\n.secondary-button:disabled {\n  box-shadow: none;"
    ) in animations
    # The 0.98 grouped press now applies to the test button only.
    assert (
        ".test-button:not(:disabled):active {\n  transform: scale(0.98);\n}" in styles
    )
    assert ".secondary-button:not(:disabled):active,\n.test-button" not in styles


def test_admin_static_toasts_sonner_style_with_swipe():
    animations = Path("src/claudey/api/admin_static/admin-animations.css").read_text(
        encoding="utf-8"
    )
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")

    # Enter: scale 0.8 -> 1 with the sonner curve.
    assert (
        "animation: sonner-in 0.18s cubic-bezier(0.22, 1, 0.36, 1) backwards;"
    ) in animations
    assert "@keyframes sonner-in" in animations
    assert "transform: scale(0.8)" in animations
    # Exit: shrink + rise.
    assert ".toast.toast-leaving" in animations
    assert "transform: scale(0.9) translateY(-6px)" in animations
    # Swipe: no transition while dragging, springy snap-back.
    assert ".toast.swiping {\n  transition: none;" in animations
    assert "cubic-bezier(0.34, 1.56, 0.64, 1)" in animations
    assert "touch-action: pan-y" in animations
    assert "SWIPE_DISMISS_AT" in module
    assert "SWIPE_FADE_OVER" in module
    assert "SWIPE_FLICK_VELOCITY" in module
    assert "pointerdown" in module
    assert 'closest(".toast")' in module
    assert "snap-back" in module
    assert "stopPropagation" in module
    # Loading variant: spinner icon, spin keyframes, no auto-dismiss.
    assert ".toast.toast-loading .toast-icon" in animations
    assert "animation: toast-spin 0.8s linear infinite" in animations
    assert "@keyframes toast-spin" in animations
    assert "ICON_SPINNER" in script
    assert 'kind === "loading" ? ICON_SPINNER : ICON_INFO' in script
    assert 'container.querySelector(".toast-loading")?.remove();' in script
    assert "M12 3a9 9 0 1 0 9 9" in script
    assert 'showMessage("Restarting server...", "loading")' in script
    assert 'showMessage("Applied. Restarting server...", "loading")' in script
    assert 'showMessage("Refreshing models...", "loading")' in script
    assert 'if (kind !== "loading") {' in script


def test_admin_static_logo_marquee_matches_logos_dir():
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    html = Path("src/claudey/api/admin_static/index.html").read_text(encoding="utf-8")
    logos_dir = Path("src/claudey/api/admin_static/logos")
    slugs = sorted(path.stem for path in logos_dir.glob("*.svg"))
    assert len(slugs) == 32

    # The module embeds the slug list and builds one src per slug.
    start = module.index("MARQUEE_LOGO_SLUGS = [")
    end = module.index("];", start)
    body = module[start:end]
    embedded = [
        line.strip().strip(",").strip('"')
        for line in body.splitlines()
        if line.strip().startswith('"')
    ]
    assert set(embedded) == set(slugs)
    assert len(embedded) == len(slugs)
    assert "img.src = `/admin/assets/logos/${slug}.svg`;" in module
    # The markup hosts the two mirrored tracks behind aria-hidden.
    assert 'class="marquee-track marquee-track-a"' in html
    assert 'class="marquee-track marquee-track-b"' in html
    assert 'class="marquee-caption"' in html
    assert 'aria-hidden="true"' in html
    # The edge fade is a mask gradient, not an overlay image.
    animations_css = Path(
        "src/claudey/api/admin_static/admin-animations.css"
    ).read_text(encoding="utf-8")
    assert (
        "mask-image: linear-gradient(90deg, transparent, #000 8%, "
        "#000 92%, transparent)"
    ) in animations_css


def test_admin_static_reduced_motion_gates_all_loops():
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    # JS never starts the tween or marquee loops under reduced motion.
    assert 'window.matchMedia("(prefers-reduced-motion: reduce)")' in module
    assert "REDUCED_MOTION" in module
    assert "if (REDUCED_MOTION || !DESKTOP.matches) {" in module
    assert "if (!REDUCED_MOTION) startMarquee();" in module
    assert "stopMarquee" in module
    # The CSS baseline zeroes every animation/transition duration.
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert "animation-duration: 0.01ms !important" in styles
    assert "transition-duration: 0.01ms !important" in styles


def test_admin_static_preserves_accessibility_attributes():
    html = Path("src/claudey/api/admin_static/index.html").read_text(encoding="utf-8")
    script = Path("src/claudey/api/admin_static/admin.js").read_text(encoding="utf-8")
    module = Path("src/claudey/api/admin_static/admin-animations.js").read_text(
        encoding="utf-8"
    )
    styles = Path("src/claudey/api/admin_static/admin.css").read_text(encoding="utf-8")

    assert 'aria-expanded="true"' in html
    assert 'aria-controls="sectionNav"' in html
    assert 'aria-label="Collapse sidebar"' in html
    assert 'aria-label="Admin views"' in html
    assert 'aria-label="Notifications"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-hidden="true"' in html
    # Pills are decorative and invisible to assistive tech.
    assert 'setAttribute("aria-hidden", "true")' in module
    # The module never takes over the toggle's aria state.
    assert 'setAttribute("aria-expanded"' not in module
    # Focus-visible outlines and live regions stay untouched.
    assert "focus-visible" in styles
    assert 'sidebarToggle.setAttribute("aria-expanded"' in script
    assert 'toast.setAttribute("role", "status")' in script
