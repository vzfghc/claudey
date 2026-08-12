"""Unit tests for the persisted combo (model fallback chain) registry."""

import json
from pathlib import Path

import pytest

from claudey.config.combos import (
    COMBOS_PATH_ENV,
    ComboNode,
    ComboRecord,
    ComboStore,
    combo_ids,
    combo_store,
    combos_path,
    find_combo,
    list_combos,
    make_unique_combo_id,
    resolve_combo,
    resolved_nodes,
    validate_provider_model_ref,
)


@pytest.fixture
def redirect_store(monkeypatch, tmp_path: Path) -> Path:
    """Point the process-wide combo store at an isolated path per test."""
    store_path = tmp_path / "combos.json"
    monkeypatch.setenv(COMBOS_PATH_ENV, str(store_path))
    return store_path


def _node(
    provider_model_ref: str = "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
    enabled: bool = True,
    priority: int = 0,
) -> ComboNode:
    return ComboNode(
        provider_model_ref=provider_model_ref,
        enabled=enabled,
        priority=priority,
    )


def _combo(
    combo_id: str = "combo_flagship",
    display_name: str = "Flagship",
    nodes: tuple[ComboNode, ...] = (_node(),),
    enabled: bool = True,
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> ComboRecord:
    return ComboRecord(
        combo_id=combo_id,
        display_name=display_name,
        nodes=nodes,
        enabled=enabled,
        created_at=created_at,
    )


def test_store_defaults_to_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert combos_path() == tmp_path / ".claudey" / "combos.json"


def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(COMBOS_PATH_ENV, str(tmp_path / "nested" / "combos.json"))
    assert combos_path() == tmp_path / "nested" / "combos.json"


def test_upsert_then_find_round_trip(redirect_store):
    store = combo_store()
    store.upsert(_combo())
    assert store.find("combo_flagship") == _combo()


def test_upsert_replaces_existing_combo(redirect_store):
    store = combo_store()
    store.upsert(_combo())
    store.upsert(
        _combo(
            display_name="Flagship Renamed",
            nodes=(_node(provider_model_ref="routeway/meta-llama/llama-3.1-70b"),),
        )
    )
    records = store.all_records()
    assert len(records) == 1
    assert records[0].display_name == "Flagship Renamed"
    assert records[0].nodes[0].provider_model_ref == "routeway/meta-llama/llama-3.1-70b"


def test_remove_deletes_combo(redirect_store):
    store = combo_store()
    store.upsert(_combo())
    assert store.remove("combo_flagship") is True
    assert store.find("combo_flagship") is None
    assert store.remove("combo_flagship") is False


def test_persists_across_store_instances(redirect_store):
    combo_store().upsert(_combo())
    reloaded = ComboStore(path=redirect_store)
    assert reloaded.find("combo_flagship") is not None


def test_atomic_write_creates_valid_json(redirect_store):
    store = combo_store()
    store.upsert(
        _combo(
            nodes=(
                _node(),
                _node(provider_model_ref="novita/deepseek/deepseek-r1-0528"),
            )
        )
    )
    raw = json.loads(redirect_store.read_text(encoding="utf-8"))
    assert raw[0]["combo_id"] == "combo_flagship"
    assert [node["provider_model_ref"] for node in raw[0]["nodes"]] == [
        "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
        "novita/deepseek/deepseek-r1-0528",
    ]


def test_list_in_creation_order(redirect_store):
    store = combo_store()
    store.upsert(_combo(combo_id="combo_alpha"))
    store.upsert(_combo(combo_id="combo_beta"))
    assert [c.combo_id for c in store.all_records()] == ["combo_alpha", "combo_beta"]


def test_parse_skips_invalid_rows(redirect_store):
    store_path = redirect_store
    store_path.write_text(
        json.dumps(
            [
                {
                    "combo_id": "combo_ok",
                    "display_name": "Ok",
                    "nodes": [
                        {"provider_model_ref": "routeway/meta-llama/llama-3.1-70b"}
                    ],
                },
                {
                    "combo_id": "",
                    "display_name": "Empty id",
                    "nodes": [_node().provider_model_ref],
                },
                {
                    "combo_id": "combo_badnodes",
                    "display_name": "Bad nodes",
                    "nodes": [{"provider_model_ref": ""}],
                },
                {"combo_id": "combo_nonodes", "display_name": "No nodes"},
                "not-a-dict",
                {
                    "combo_id": "combo_string_nodes",
                    "display_name": "String nodes",
                    "nodes": ["routeway/meta-llama/llama-3.1-70b"],
                },
            ]
        ),
        encoding="utf-8",
    )
    store = ComboStore(path=store_path)
    ids = [c.combo_id for c in store.all_records()]
    assert ids == ["combo_ok"]


def test_combo_ids_from_store(redirect_store):
    combo_store().upsert(_combo(combo_id="combo_flagship"))
    assert combo_ids() == {"combo_flagship"}


def test_list_combos(redirect_store):
    combo_store().upsert(_combo(combo_id="combo_flagship"))
    assert [c.combo_id for c in list_combos()] == ["combo_flagship"]


def test_find_combo(redirect_store):
    combo_store().upsert(_combo(combo_id="combo_flagship"))
    assert find_combo("combo_flagship") is not None
    assert find_combo("combo_missing") is None


def test_combo_node_provider_first_path_segment():
    assert _node("vertex/google/gemini-3.5-flash").provider == "vertex"
    assert (
        _node("nvidia_nim/nvidia/nemotron-3-super-120b-a12b").provider == "nvidia_nim"
    )
    assert _node("custom_acme/gpt-4o-mini").provider == "custom_acme"


def test_combo_public_payload_has_no_secrets():
    payload = _combo().public_payload()
    expected_keys = {"combo_id", "display_name", "nodes", "enabled", "created_at"}
    assert set(payload) == expected_keys
    assert all(
        "api" not in key and "key" not in key and "secret" not in key for key in payload
    )


def test_enabled_nodes_filters_disabled_and_sorts_by_priority():
    combo = _combo(
        combo_id="combo_priority",
        nodes=(
            _node(provider_model_ref="a/model", priority=2, enabled=False),
            _node(provider_model_ref="b/model", priority=0),
            _node(provider_model_ref="c/model", priority=1),
            _node(provider_model_ref="d/model"),
        ),
    )
    resolved = resolved_nodes(combo)
    assert [node.provider_model_ref for node in resolved] == [
        "b/model",  # priority 0, stable sort keeps insertion order
        "d/model",
        "c/model",
    ]


def test_resolved_nodes_missing_combo_returns_none(redirect_store):
    assert resolve_combo("combo_ghost") is None


def test_resolved_nodes_store_lookup_uses_enabled_records(redirect_store):
    combo_store().upsert(
        _combo(
            combo_id="combo_disabled",
            enabled=False,
            nodes=(_node(provider_model_ref="a/model"),),
        )
    )
    assert resolve_combo("combo_disabled") is None
    combo_store().upsert(
        _combo(
            combo_id="combo_enabled",
            enabled=True,
            nodes=(_node(provider_model_ref="a/model", priority=1),),
        )
    )
    resolved = resolve_combo("combo_enabled")
    assert resolved is not None
    assert [n.provider_model_ref for n in resolved] == ["a/model"]


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "provider",  # no model segment
        "/model",
        "provider/",
        "@combo:flagship",  # nested combo references are not nodes
        "@combo/flagship",
    ],
)
def test_validate_provider_model_ref_rejects(raw):
    with pytest.raises(ValueError):
        validate_provider_model_ref(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("routeway/meta-llama/llama-3.1-70b", "routeway/meta-llama/llama-3.1-70b"),
        ("  vertex/google/gemini-3.5-flash  ", "vertex/google/gemini-3.5-flash"),
        ("custom_acme/gpt-4o-mini", "custom_acme/gpt-4o-mini"),
    ],
)
def test_validate_provider_model_ref_normalizes(raw, expected):
    assert validate_provider_model_ref(raw) == expected


def test_make_unique_combo_id_trims_to_prefix():
    existing = {"combo_alpha", "combo_alpha_2"}
    assert make_unique_combo_id("Alpha", existing) == "combo_alpha_3"
    assert make_unique_combo_id("Combo Aliases", set()) == "combo_combo_aliases"


def test_upsert_with_unvalidated_ref_raises(redirect_store):
    store = combo_store()
    with pytest.raises(ValueError):
        store.upsert(_combo(nodes=(_node(provider_model_ref="just-a-provider"),)))
