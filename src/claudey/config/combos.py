"""User-defined model combos: a JSON-persisted fallback-chain registry.

Combos are named, admin-managed **fallback chains** (OmniRoute's persisted-combo
shape): an ordered list of traversable provider/model references tried in turn by
the failover executor. They are routing metadata only — **no secrets are stored** —
so unlike :mod:`custom_providers` there is no masking payload. The store mirrors
that module's proven atomic-JSON idiom (tmp file + ``os.replace``, in-process
cache, env-overridable path) so the Admin UI and routing share one authoritative
view, and so tests can redirect the store per-test.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claudey.config.custom_providers import slug_for_display_name
from claudey.config.paths import config_dir_path

COMBOS_FILENAME = "combos.json"
COMBO_ID_PREFIX = "combo_"
COMBOS_PATH_ENV = "CLAUDEY_COMBOS_PATH"


@dataclass(frozen=True, slots=True)
class ComboNode:
    """One hop in a persisted fallback chain."""

    provider_model_ref: str  # "provider/model" from the catalog or custom providers
    enabled: bool = True
    priority: int = 0  # lower = tried first; ties keep insertion order

    @property
    def provider(self) -> str:
        """Return the provider id (first path segment) for this node."""
        return self.provider_model_ref.split("/", 1)[0]


@dataclass(frozen=True, slots=True)
class ComboRecord:
    """Immutable definition of one persisted combo."""

    combo_id: str  # "combo_<slug>", unique like custom_* ids
    display_name: str
    nodes: tuple[ComboNode, ...] = field(default_factory=tuple)
    enabled: bool = True
    created_at: str = ""

    def public_payload(self) -> dict[str, Any]:
        """Return a JSON payload (routing metadata only; no secrets)."""
        return {
            "combo_id": self.combo_id,
            "display_name": self.display_name,
            "nodes": [
                {
                    "provider_model_ref": node.provider_model_ref,
                    "enabled": node.enabled,
                    "priority": node.priority,
                }
                for node in self.nodes
            ],
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


def combos_path() -> Path:
    """Return the on-disk path backing the combo store.

    An explicit ``CLAUDEY_COMBOS_PATH`` env override wins so tests (and power
    users) can redirect the store without touching user configuration.
    """
    override = os.getenv(COMBOS_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return config_dir_path() / COMBOS_FILENAME


def validate_provider_model_ref(provider_model_ref: str) -> str:
    """Validate and normalize one combo node reference.

    A node references exactly one routable ``provider/model`` pair. ``@combo:``
    grammar tokens and nested combo references are rejected here — combos nest
    only at the tier-setting level (:mod:`config.model_refs`).
    """
    value = provider_model_ref.strip()
    if not value:
        raise ValueError("Provider model reference is required.")
    if value.startswith("@"):
        raise ValueError(
            "Provider model reference must be a provider/model pair, "
            f"not a combo token (got {value!r})."
        )
    provider, separator, model = value.partition("/")
    if not separator or not provider or not model:
        raise ValueError("Provider model reference must be provider/model.")
    return value


def make_unique_combo_id(display_name: str, existing_ids: set[str]) -> str:
    """Build a unique ``combo_<slug>`` id for a display name."""
    base = f"{COMBO_ID_PREFIX}{slug_for_display_name(display_name)}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def resolved_nodes(record: ComboRecord) -> tuple[ComboNode, ...]:
    """Return a combo's nodes filtered to enabled, sorted by priority.

    Ties preserve insertion order (Python's stable sort). The record must be the
    resolved, currently enabled combo — callers decide identity up front.
    """
    return tuple(
        sorted(
            (node for node in record.nodes if node.enabled),
            key=lambda node: node.priority,
        )
    )


def _read_records(path: Path) -> list[dict[str, Any]]:
    """Read raw JSON rows, tolerating a missing or corrupt store."""
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return []
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    """Atomically persist JSON rows (tmp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(records, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class ComboStore:
    """In-process registry backed by the atomic JSON file.

    Entries are immutable. Mutations validate nodes, persist atomically, and
    update the cache. The store re-resolves its path whenever the
    ``CLAUDEY_COMBOS_PATH`` override changes, so tests can redirect per-test.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._default_path = path or config_dir_path() / COMBOS_FILENAME
        self._active_path = self._default_path
        self._records: list[ComboRecord] | None = None

    @property
    def path(self) -> Path:
        return self._resolved_path()

    def _resolved_path(self) -> Path:
        override = os.getenv(COMBOS_PATH_ENV, "").strip()
        return self._default_path if not override else Path(override)

    def _load(self) -> list[ComboRecord]:
        path = self._resolved_path()
        if self._records is None or path != self._active_path:
            self._active_path = path
            self._records = _parse_records(_read_records(path))
        return self._records

    def all_records(self) -> list[ComboRecord]:
        """Return all combos in creation order."""
        return list(self._load())

    def find(self, combo_id: str) -> ComboRecord | None:
        """Return one combo by id, else None."""
        for record in self._load():
            if record.combo_id == combo_id:
                return record
        return None

    def has(self, combo_id: str) -> bool:
        """Return whether a combo id belongs to this store."""
        return self.find(combo_id) is not None

    def upsert(self, record: ComboRecord) -> list[ComboRecord]:
        """Persist a validated record, replacing one with the same id."""
        for node in record.nodes:
            validate_provider_model_ref(node.provider_model_ref)
        records = self._load()
        updated = [
            existing for existing in records if existing.combo_id != record.combo_id
        ] + [record]
        self._records = updated
        _write_records(self._resolved_path(), _dump_records(updated))
        return list(updated)

    def remove(self, combo_id: str) -> bool:
        """Remove a combo and persist atomically. Returns whether removed."""
        records = self._load()
        kept = [record for record in records if record.combo_id != combo_id]
        if len(kept) == len(records):
            return False
        self._records = kept
        _write_records(self._resolved_path(), _dump_records(kept))
        return True


_store = ComboStore()


def combo_store() -> ComboStore:
    """Return the process-wide combo store."""
    return _store


def find_combo(combo_id: str) -> ComboRecord | None:
    """Return a combo record by id, or None."""
    return _store.find(combo_id)


def combo_ids() -> set[str]:
    """Return the set of registered combo ids."""
    return {record.combo_id for record in _store.all_records()}


def list_combos() -> list[ComboRecord]:
    """Return all registered combos."""
    return _store.all_records()


def resolve_combo(combo_id: str) -> tuple[ComboNode, ...] | None:
    """Return the traversable nodes for a combo id, or None.

    Unknown and disabled combos resolve to ``None`` so tier settings can fail
    config validation day-0 rather than at request time.
    """
    record = _store.find(combo_id)
    if record is None or not record.enabled:
        return None
    return resolved_nodes(record)


def _parse_records(raw: list[dict[str, Any]]) -> list[ComboRecord]:
    """Parse raw JSON rows into valid records, skipping invalid ones."""
    records: list[ComboRecord] = []
    for entry in raw:
        combo_id = entry.get("combo_id")
        if not isinstance(combo_id, str) or not combo_id:
            continue
        nodes = tuple(_parse_nodes(entry.get("nodes")))
        if not nodes:
            continue
        records.append(
            ComboRecord(
                combo_id=combo_id,
                display_name=str(entry.get("display_name") or combo_id),
                nodes=nodes,
                enabled=entry.get("enabled", True) is True,
                created_at=str(entry.get("created_at") or ""),
            )
        )
    return records


def _parse_nodes(raw: Any) -> list[ComboNode]:
    """Parse raw JSON node rows, skipping node entries that are unusable."""
    nodes: list[ComboNode] = []
    if not isinstance(raw, list):
        return nodes
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            provider_model_ref = validate_provider_model_ref(
                str(entry.get("provider_model_ref") or "")
            )
        except ValueError:
            continue
        nodes.append(
            ComboNode(
                provider_model_ref=provider_model_ref,
                enabled=entry.get("enabled", True) is True,
                priority=int(entry.get("priority", 0)),
            )
        )
    return nodes


def _dump_records(records: list[ComboRecord]) -> list[dict[str, Any]]:
    """Serialize records back to fully-fielded JSON rows."""
    return [record.public_payload() for record in records]
