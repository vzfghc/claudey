"""Admin combos CRUD + validate endpoints (secret-free routing metadata)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.support import create_test_app


@pytest.fixture
def combos_store_path(monkeypatch, tmp_path: Path) -> Path:
    store_path = tmp_path / "combos.json"
    monkeypatch.setenv("CLAUDEY_COMBOS_PATH", str(store_path))
    return store_path


def _set_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDEY_CONFIG_DIR", str(tmp_path / ".claudey"))


def _client(app, *, remote: bool = False) -> TestClient:
    host = "203.0.113.10" if remote else "127.0.0.1"
    return TestClient(app, client=(host, 50000))


def _body(*, name: str = "Flagship", nodes: list[dict] | None = None) -> dict:
    return {
        "display_name": name,
        "nodes": (
            nodes
            if nodes is not None
            else [
                {"provider_model_ref": "routeway/meta-llama/llama-3.1-70b"},
                {"provider_model_ref": "novita/deepseek/deepseek-r1", "priority": 1},
            ]
        ),
        "enabled": True,
    }


def test_admin_combos_crud(monkeypatch, tmp_path, combos_store_path):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    created = client.post("/admin/api/combos", json=_body())
    assert created.status_code == 200
    payload = created.json()
    assert payload["success"] is True
    assert payload["combo_id"].startswith("combo_flagship")
    assert payload["display_name"] == "Flagship"
    assert [n["provider_model_ref"] for n in payload["nodes"]] == [
        "routeway/meta-llama/llama-3.1-70b",
        "novita/deepseek/deepseek-r1",
    ]
    # No secrets surface on a combo payload.
    assert all("api" not in k and "key" not in k and "secret" not in k for k in payload)

    listed = client.get("/admin/api/combos")
    assert listed.status_code == 200
    combos = listed.json()["combos"]
    assert len(combos) == 1
    assert combos[0]["combo_id"] == payload["combo_id"]
    assert "api_key" not in combos[0]["nodes"][0]

    updated = client.put(
        f"/admin/api/combos/{payload['combo_id']}",
        json=_body(name="Flagship Renamed"),
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Flagship Renamed"

    deleted = client.delete(f"/admin/api/combos/{payload['combo_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    assert client.get("/admin/api/combos").json()["combos"] == []


def test_admin_combo_generates_unique_id_on_duplicate_name(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    first = client.post("/admin/api/combos", json=_body(name="Acme")).json()
    second = client.post("/admin/api/combos", json=_body(name="Acme")).json()

    assert first["combo_id"] == "combo_acme"
    assert second["combo_id"] == "combo_acme_2"


def test_admin_combo_rejects_missing_nodes(monkeypatch, tmp_path, combos_store_path):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post("/admin/api/combos", json=_body(nodes=[]))
    assert response.status_code == 400


def test_admin_combo_rejects_empty_name(monkeypatch, tmp_path, combos_store_path):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post("/admin/api/combos", json=_body(name="   "))
    assert response.status_code == 400


def test_admin_combo_rejects_bad_node_ref(monkeypatch, tmp_path, combos_store_path):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post(
        "/admin/api/combos",
        json=_body(nodes=[{"provider_model_ref": "just-a-provider"}]),
    )
    assert response.status_code == 400


def test_admin_combo_update_unknown_returns_404(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.put("/admin/api/combos/combo_ghost", json=_body())
    assert response.status_code == 404


def test_admin_combo_delete_unknown_returns_404(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    assert client.delete("/admin/api/combos/combo_ghost").status_code == 404


def test_admin_combos_are_loopback_only(monkeypatch, tmp_path, combos_store_path):
    _set_home(monkeypatch, tmp_path)
    remote = _client(create_test_app(), remote=True)

    assert remote.get("/admin/api/combos").status_code == 403
    assert remote.post("/admin/api/combos", json=_body()).status_code == 403
    assert remote.delete("/admin/api/combos/combo_x").status_code == 403


def test_admin_combo_validate_accepts_wellformed(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post("/admin/api/combos/validate", json=_body())
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_admin_combo_validate_rejects_bad_node(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post(
        "/admin/api/combos/validate",
        json=_body(nodes=[{"provider_model_ref": "provider-only"}]),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_admin_combo_validate_allows_custom_provider_nodes(
    monkeypatch, tmp_path, combos_store_path
):
    _set_home(monkeypatch, tmp_path)
    client = _client(create_test_app())

    response = client.post(
        "/admin/api/combos/validate",
        json=_body(nodes=[{"provider_model_ref": "custom_acme/gpt-4o-mini"}]),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
