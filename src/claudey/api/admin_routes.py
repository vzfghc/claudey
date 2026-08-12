"""Local admin UI routes and APIs."""

import ipaddress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from claudey.application.connected_accounts import (
    ConnectedAccountLoginMode,
)
from claudey.application.model_metadata import ProviderModelRefreshResult
from claudey.config import custom_provider_check
from claudey.config.admin.manifest import FIELD_BY_KEY
from claudey.config.admin.persistence import validate_updates
from claudey.config.admin.values import load_config_response
from claudey.config.combos import (
    ComboNode,
    ComboRecord,
    combo_ids,
    combo_store,
    make_unique_combo_id,
    validate_provider_model_ref,
)
from claudey.config.custom_providers import (
    CustomProviderRecord,
    custom_provider_ids,
    custom_provider_store,
    is_valid_compatible_type,
    make_unique_provider_id,
    validate_base_url,
)
from claudey.config.model_refs import configured_chat_model_refs
from claudey.config.provider_catalog import (
    PROVIDER_CATALOG,
    ProviderAuthKind,
)
from claudey.core.version import asset_version

from .admin_dashboard import dashboard_payload
from .deepseek_billing import billing_payload
from .dependencies import get_services
from .ports import ApiServices
from .usage_aggregate import usage_payload

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "admin_static"
LOCAL_PROVIDER_PATHS = {
    "lmstudio": "/models",
    "llamacpp": "/models",
    "ollama": "/api/tags",
}


class AdminConfigPayload(BaseModel):
    """Partial config update submitted by the admin UI."""

    values: dict[str, Any] = Field(default_factory=dict)


class ConnectedAccountLoginPayload(BaseModel):
    """Interactive connected-account login selection."""

    mode: ConnectedAccountLoginMode = ConnectedAccountLoginMode.BROWSER


class CustomProviderPayload(BaseModel):
    """Registration payload for an admin-defined custom provider."""

    type: str = Field(default="openai", description="wire type: openai | anthropic")
    name: str = Field(default="", min_length=1)
    base_url: str = Field(default="")
    api_key: str = Field(default="")


class ProviderValidatePayload(BaseModel):
    """Probe payload for the custom-provider "Check" button (persists nothing)."""

    base_url: str = Field(default="")
    api_key: str = Field(default="")
    type: str = Field(default="openai", description="wire type: openai | anthropic")
    model_id: str | None = Field(default=None)


class ComboNodePayload(BaseModel):
    """One hop of an admin-managed combo (routing metadata; no secrets)."""

    provider_model_ref: str = Field(default="")
    enabled: bool = True
    priority: int = Field(default=0, ge=0)


class ComboPayload(BaseModel):
    """Create/update payload for an admin-managed combo (no secrets)."""

    display_name: str = Field(default="", min_length=1)
    nodes: list[ComboNodePayload] = Field(default_factory=list)
    enabled: bool = True


def _build_combo_nodes(
    payload_nodes: list[ComboNodePayload],
) -> tuple[ComboNode, ...]:
    """Validate and build combo nodes from a payload."""
    nodes: list[ComboNode] = []
    for item in payload_nodes:
        try:
            provider_model_ref = validate_provider_model_ref(item.provider_model_ref)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        nodes.append(
            ComboNode(
                provider_model_ref=provider_model_ref,
                enabled=item.enabled,
                priority=item.priority,
            )
        )
    return tuple(nodes)


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _origin_is_local(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlsplit(origin)
    return _is_loopback_host(parsed.hostname)


def require_loopback_admin(request: Request) -> None:
    """Allow admin access only from the local machine."""

    client_host = request.client.host if request.client else None
    if not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")

    origin = request.headers.get("origin")
    if not _origin_is_local(origin):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")


def _asset_response(filename: str) -> FileResponse:
    path = STATIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return FileResponse(path)


@router.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    require_loopback_admin(request)
    template = (STATIC_DIR / "index.html").read_text("utf-8")
    rendered = template.replace("__ASSET_VERSION__", asset_version())
    return HTMLResponse(rendered, media_type="text/html")


@router.get("/admin/assets/{filename}", include_in_schema=False)
async def admin_asset(filename: str, request: Request):
    require_loopback_admin(request)
    if filename not in {
        "admin.css",
        "admin.js",
        "admin-animations.css",
        "admin-animations.js",
        "beam.bundle.js",
    }:
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return _asset_response(filename)


@router.get("/admin/assets/logos/{filename}", include_in_schema=False)
async def admin_logo_asset(filename: str, request: Request):
    require_loopback_admin(request)
    logos_dir = (STATIC_DIR / "logos").resolve()
    path = (logos_dir / filename).resolve()
    if logos_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Provider logo not found")
    return FileResponse(path, media_type="image/svg+xml")


@router.get("/admin/api/dashboard")
async def get_admin_dashboard(request: Request):
    require_loopback_admin(request)
    return dashboard_payload()


@router.get("/admin/api/usage")
async def get_admin_usage(request: Request):
    require_loopback_admin(request)
    payload = usage_payload()
    payload["billing"] = billing_payload()
    return payload


@router.get("/admin/api/config")
async def get_admin_config(request: Request):
    require_loopback_admin(request)
    return load_config_response()


@router.post("/admin/api/config/validate")
async def validate_admin_config(payload: AdminConfigPayload, request: Request):
    require_loopback_admin(request)
    return validate_updates(_filtered_values(payload.values))


@router.post("/admin/api/config/apply")
async def apply_admin_config(
    payload: AdminConfigPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    result = await services.admin.apply_admin_config(_filtered_values(payload.values))
    restart = result.get("restart")
    if isinstance(restart, dict) and restart.get("automatic"):
        background_tasks.add_task(services.admin.request_restart)
    return result


@router.post("/admin/api/restart")
async def restart_server(
    request: Request,
    background_tasks: BackgroundTasks,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    background_tasks.add_task(services.admin.request_restart)
    return {"restarting": True, "admin_url": "/admin"}


@router.get("/admin/api/status")
async def admin_status(
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return services.admin.admin_status()


@router.get("/admin/api/providers/local-status")
async def local_provider_status(request: Request):
    require_loopback_admin(request)
    config = load_config_response()
    values = {field["key"]: field["value"] for field in config["fields"]}
    checks = []
    for provider_id, path in LOCAL_PROVIDER_PATHS.items():
        base_url = _local_provider_url(provider_id, values)
        checks.append(await _check_local_provider(provider_id, base_url, path))
    return {"providers": checks}


@router.post("/admin/api/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.test_provider(provider_id)


@router.get("/admin/api/providers/{provider_id}/auth")
async def connected_account_status(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    _require_connected_account_provider(provider_id)
    status = await services.admin.connected_account_status(provider_id)
    return _no_store(status.as_dict())


@router.post("/admin/api/providers/{provider_id}/auth/login")
async def start_connected_account_login(
    provider_id: str,
    payload: ConnectedAccountLoginPayload,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    _require_connected_account_provider(provider_id)
    try:
        status = await services.admin.start_connected_account_login(
            provider_id, payload.mode
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(f"Could not start connected-account login ({type(exc).__name__})."),
        ) from exc
    return _no_store(status.as_dict())


@router.post("/admin/api/providers/{provider_id}/auth/cancel")
async def cancel_connected_account_login(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    _require_connected_account_provider(provider_id)
    status = await services.admin.cancel_connected_account_login(provider_id)
    return _no_store(status.as_dict())


@router.delete("/admin/api/providers/{provider_id}/auth")
async def disconnect_connected_account(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    _require_connected_account_provider(provider_id)
    status = await services.admin.disconnect_connected_account(provider_id)
    return _no_store(status.as_dict())


@router.get("/admin/api/models")
async def models(
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return _model_options(services)


@router.post("/admin/api/models/refresh")
async def refresh_models(
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    result = await services.admin.refresh_models()
    return _model_options(services, refresh_result=result)


def _model_options(
    services: ApiServices,
    *,
    refresh_result: ProviderModelRefreshResult | None = None,
) -> dict[str, list[str]]:
    configured = {
        ref.model_ref
        for ref in configured_chat_model_refs(services.requests.current_settings())
    }
    discovered = {
        info.model_id for info in services.requests.cached_prefixed_model_infos()
    }
    failed_provider_ids = (
        refresh_result.failed_provider_ids if refresh_result is not None else ()
    )
    return {
        "models": sorted(configured | discovered, key=str.casefold),
        "failed_providers": list(failed_provider_ids),
    }


def _filtered_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in FIELD_BY_KEY}


def _local_provider_url(provider_id: str, values: dict[str, str]) -> str:
    if provider_id == "lmstudio":
        return values.get("LM_STUDIO_BASE_URL", "")
    if provider_id == "llamacpp":
        return values.get("LLAMACPP_BASE_URL", "")
    if provider_id == "ollama":
        return values.get("OLLAMA_BASE_URL", "")
    return ""


async def _check_local_provider(
    provider_id: str, base_url: str, path: str
) -> dict[str, Any]:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        return {
            "provider_id": provider_id,
            "status": "missing_url",
            "label": "Missing URL",
            "base_url": base_url,
        }

    url = f"{clean_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(url)
        ok = 200 <= response.status_code < 300
        return {
            "provider_id": provider_id,
            "status": "reachable" if ok else "offline",
            "label": "Reachable" if ok else "Offline",
            "base_url": base_url,
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "status": "offline",
            "label": "Offline",
            "base_url": base_url,
            "error_type": type(exc).__name__,
        }


def _require_connected_account_provider(provider_id: str) -> None:
    descriptor = PROVIDER_CATALOG.get(provider_id)
    if (
        descriptor is None
        or descriptor.auth_kind is not ProviderAuthKind.CONNECTED_ACCOUNT
    ):
        raise HTTPException(
            status_code=404,
            detail="Provider does not support connected-account login.",
        )


@router.get("/admin/api/providers/custom")
async def list_custom_providers(request: Request) -> JSONResponse:
    """List admin-defined custom providers with secrets masked."""
    require_loopback_admin(request)
    records = custom_provider_store().all_records()
    return _no_store({"providers": [record.secret_payload() for record in records]})


@router.post("/admin/api/providers/custom")
async def create_custom_provider(
    payload: CustomProviderPayload,
    request: Request,
) -> JSONResponse:
    """Register a real admin-defined custom provider and persist it."""
    require_loopback_admin(request)
    provider_type = payload.type.strip().lower()
    if not is_valid_compatible_type(provider_type):
        raise HTTPException(status_code=400, detail="Invalid provider type")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not payload.base_url.strip():
        raise HTTPException(status_code=400, detail="Base URL is required")
    try:
        base_url = validate_base_url(payload.base_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None

    store = custom_provider_store()
    provider_id = make_unique_provider_id(name, set(custom_provider_ids()))
    record = CustomProviderRecord(
        provider_id=provider_id,
        display_name=name,
        compatible=provider_type,
        base_url=base_url,
        api_key=payload.api_key.strip(),
        created_at=datetime.now(UTC).isoformat(),
    )
    store.upsert(record)
    return _no_store(
        {
            "success": True,
            "provider_id": provider_id,
            "display_name": name,
            **record.secret_payload(),
            "message": f"Custom {provider_type} provider '{name}' created",
        }
    )


@router.post("/admin/api/providers/custom/validate")
async def validate_custom_provider(
    payload: ProviderValidatePayload,
    request: Request,
) -> JSONResponse:
    """Live-probe a custom provider's base URL + key without registering it."""
    require_loopback_admin(request)
    compatible = payload.type.strip().lower()
    if not is_valid_compatible_type(compatible):
        return _no_store(
            {"valid": False, "method": None, "error": "Invalid provider type."}
        )
    result = await custom_provider_check.check_compatible_connection(
        payload.base_url,
        payload.api_key,
        compatible,
        payload.model_id,
    )
    return _no_store(result)


@router.delete("/admin/api/providers/custom/{provider_id}")
async def delete_custom_provider(
    provider_id: str,
    request: Request,
) -> JSONResponse:
    """Delete an admin-defined custom provider and persist the removal."""
    require_loopback_admin(request)
    removed = custom_provider_store().remove(provider_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Custom provider not found")
    return _no_store(
        {"success": True, "message": f"Custom provider '{provider_id}' deleted"}
    )


@router.get("/admin/api/combos")
async def list_combos(request: Request) -> JSONResponse:
    """List admin-managed model combos (routing metadata; no secrets)."""
    require_loopback_admin(request)
    records = combo_store().all_records()
    return _no_store({"combos": [record.public_payload() for record in records]})


@router.post("/admin/api/combos")
async def create_combo(payload: ComboPayload, request: Request) -> JSONResponse:
    """Register a named model combo and persist it (no secrets)."""
    require_loopback_admin(request)
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not payload.nodes:
        raise HTTPException(
            status_code=400, detail="At least one model node is required"
        )
    nodes = _build_combo_nodes(payload.nodes)
    store = combo_store()
    combo_id = make_unique_combo_id(name, set(combo_ids()))
    record = ComboRecord(
        combo_id=combo_id,
        display_name=name,
        nodes=nodes,
        enabled=payload.enabled,
        created_at=datetime.now(UTC).isoformat(),
    )
    store.upsert(record)
    return _no_store(
        {
            "success": True,
            "combo_id": combo_id,
            "message": f"Combo '{name}' created",
            **record.public_payload(),
        }
    )


@router.put("/admin/api/combos/{combo_id}")
async def update_combo(
    combo_id: str,
    payload: ComboPayload,
    request: Request,
) -> JSONResponse:
    """Replace an existing combo's definition and persist the change."""
    require_loopback_admin(request)
    store = combo_store()
    existing = store.find(combo_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Combo not found")
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not payload.nodes:
        raise HTTPException(
            status_code=400, detail="At least one model node is required"
        )
    record = ComboRecord(
        combo_id=combo_id,
        display_name=name,
        nodes=_build_combo_nodes(payload.nodes),
        enabled=payload.enabled,
        created_at=existing.created_at,
    )
    store.upsert(record)
    return _no_store(
        {
            "success": True,
            "combo_id": combo_id,
            "message": f"Combo '{name}' updated",
            **record.public_payload(),
        }
    )


@router.post("/admin/api/combos/validate")
async def validate_combo(payload: ComboPayload, request: Request) -> JSONResponse:
    """Validate a combo definition without persisting it."""
    require_loopback_admin(request)
    name = payload.display_name.strip()
    if not name:
        return _no_store({"valid": False, "error": "Name is required."})
    if not payload.nodes:
        return _no_store(
            {"valid": False, "error": "At least one model node is required."}
        )
    try:
        _build_combo_nodes(payload.nodes)
    except HTTPException as error:
        return _no_store({"valid": False, "error": error.detail})
    return _no_store({"valid": True, "error": None})


@router.delete("/admin/api/combos/{combo_id}")
async def delete_combo(combo_id: str, request: Request) -> JSONResponse:
    """Delete an admin-managed combo and persist the removal."""
    require_loopback_admin(request)
    removed = combo_store().remove(combo_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Combo not found")
    return _no_store({"success": True, "message": f"Combo '{combo_id}' deleted"})


def _no_store(payload: Any) -> JSONResponse:
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})
