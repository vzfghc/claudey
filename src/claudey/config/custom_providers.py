"""User-defined custom providers: a JSON-persisted registry.

The static :data:`PROVIDER_CATALOG` describes providers that ship with the
package. Admin-created custom providers (OpenAI- or Anthropic-compatible SDK
endpoints entered in the Admin UI) cannot live in that frozen catalog — the
factory asserts exactly one construction owner per catalog id, and contract
tests enumerate the catalog exhaustively. This module is their runtime
counterpart: a small atomic JSON store under ``~/.claudey`` that the factory
consults before the catalog, and that routing and the Admin UI share in-process.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from claudey.config.paths import config_dir_path
from claudey.core.secret_crypto import (
    SecretCryptoError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)

CUSTOM_PROVIDERS_FILENAME = "custom-providers.json"
CUSTOM_PROVIDER_ID_PREFIX = "custom_"
CUSTOM_PROVIDERS_PATH_ENV = "CLAUDEY_CUSTOM_PROVIDERS_PATH"
PROVIDER_ENCRYPTION_KEY_ENV = "CLAUDEY_PROVIDER_ENCRYPTION_KEY"
MASKED_SECRET = "********"

_COMPATIBLE_TYPES = frozenset({"openai", "anthropic"})
_SLUG_CHARS = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True, slots=True)
class CustomProviderRecord:
    """Immutable definition of one user-defined provider."""

    provider_id: str
    display_name: str
    compatible: str  # "openai" | "anthropic"
    base_url: str
    api_key: str
    created_at: str

    def secret_payload(self) -> dict[str, Any]:
        """Return a JSON payload with the API key masked."""
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "compatible": self.compatible,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "created_at": self.created_at,
        }


def custom_providers_path() -> Path:
    """Return the on-disk path backing the custom-provider store.

    An explicit ``CLAUDEY_CUSTOM_PROVIDERS_PATH`` env override wins so tests
    (and power users) can redirect the store without touching the catalog.
    """
    override = os.getenv(CUSTOM_PROVIDERS_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return config_dir_path() / CUSTOM_PROVIDERS_FILENAME


def is_valid_compatible_type(compatible: str) -> bool:
    """Return whether a type maps to a supported wire transport."""
    return compatible in _COMPATIBLE_TYPES


def slug_for_display_name(display_name: str) -> str:
    """Return an ASCII slug suitable for the id suffix of a custom provider."""
    lowered = display_name.strip().lower()
    slug = _SLUG_CHARS.sub("_", lowered).strip("_")
    return slug or "provider"


def make_unique_provider_id(display_name: str, existing_ids: set[str]) -> str:
    """Build a unique ``custom_<slug>`` id for a display name."""
    base = f"{CUSTOM_PROVIDER_ID_PREFIX}{slug_for_display_name(display_name)}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def validate_base_url(base_url: str) -> str:
    """Validate and normalize a custom-provider base URL.

    Raises ``ValueError`` with a user-facing message when the URL is unusable.
    """
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("Base URL is required.")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError("Base URL is not a valid URL.") from None
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Base URL must use http:// or https://.")
    if not parsed.netloc:
        raise ValueError("Base URL must include a host.")
    return value


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
            json.dumps(_encrypt_for_write(records), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class CustomProviderStore:
    """In-process registry backed by the atomic JSON file.

    Entries are immutable. Mutations persist atomically and update the cache.
    The store re-resolves its path whenever the ``CLAUDEY_CUSTOM_PROVIDERS_PATH``
    override changes, so tests can redirect the store per-test.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._default_path = path or config_dir_path() / CUSTOM_PROVIDERS_FILENAME
        self._active_path = self._default_path
        self._records: list[CustomProviderRecord] | None = None

    @property
    def path(self) -> Path:
        return self._resolved_path()

    def _resolved_path(self) -> Path:
        override = os.getenv(CUSTOM_PROVIDERS_PATH_ENV, "").strip()
        return self._default_path if not override else Path(override)

    def _load(self) -> list[CustomProviderRecord]:
        path = self._resolved_path()
        if self._records is None or path != self._active_path:
            self._active_path = path
            self._records = _parse_records(_read_records(path))
        return self._records

    def all_records(self) -> list[CustomProviderRecord]:
        """Return all custom providers in creation order."""
        return list(self._load())

    def find(self, provider_id: str) -> CustomProviderRecord | None:
        """Return one custom provider by id, else None."""
        for record in self._load():
            if record.provider_id == provider_id:
                return record
        return None

    def has(self, provider_id: str) -> bool:
        """Return whether a provider id belongs to this store."""
        return self.find(provider_id) is not None

    def upsert(self, record: CustomProviderRecord) -> list[CustomProviderRecord]:
        """Persist a record, replacing one with the same id."""
        records = self._load()
        updated = [
            existing
            for existing in records
            if existing.provider_id != record.provider_id
        ] + [record]
        path = self._resolved_path()
        _write_records(path, _dump_records(updated))
        # Reload so the in-memory view mirrors what is on disk (e.g. keys that
        # were transparently encrypted at-rest by a configured key).
        self._records = _parse_records(_read_records(path))
        return list(self._records)

    def remove(self, provider_id: str) -> bool:
        """Remove a provider and persist atomically. Returns whether removed."""
        records = self._load()
        kept = [record for record in records if record.provider_id != provider_id]
        if len(kept) == len(records):
            return False
        path = self._resolved_path()
        _write_records(path, _dump_records(kept))
        self._records = _parse_records(_read_records(path))
        return True


_store = CustomProviderStore()


def custom_provider_store() -> CustomProviderStore:
    """Return the process-wide custom-provider store."""
    return _store


def find_custom_provider(provider_id: str) -> CustomProviderRecord | None:
    """Return a custom provider record by id, or None."""
    return _store.find(provider_id)


def custom_provider_ids() -> set[str]:
    """Return the set of registered custom provider ids."""
    return {record.provider_id for record in _store.all_records()}


def list_custom_providers() -> list[CustomProviderRecord]:
    """Return all registered custom providers."""
    return _store.all_records()


def _parse_records(raw: list[dict[str, Any]]) -> list[CustomProviderRecord]:
    """Parse raw JSON rows into valid records, skipping invalid ones."""
    records: list[CustomProviderRecord] = []
    for entry in raw:
        provider_id = entry.get("provider_id")
        base_url = entry.get("base_url")
        compatible = entry.get("compatible", "openai")
        if not isinstance(provider_id, str) or not provider_id:
            continue
        if not isinstance(base_url, str) or not base_url:
            continue
        if compatible not in _COMPATIBLE_TYPES:
            continue
        records.append(
            CustomProviderRecord(
                provider_id=provider_id,
                display_name=str(entry.get("display_name") or provider_id),
                compatible=compatible,
                base_url=base_url,
                api_key=str(entry.get("api_key") or ""),
                created_at=str(entry.get("created_at") or ""),
            )
        )
    return records


def _dump_records(records: list[CustomProviderRecord]) -> list[dict[str, Any]]:
    """Serialize records back to fully-fielded JSON rows."""
    return [
        {
            "provider_id": record.provider_id,
            "display_name": record.display_name,
            "compatible": record.compatible,
            "base_url": record.base_url,
            "api_key": record.api_key,
            "created_at": record.created_at,
        }
        for record in records
    ]


def _configured_key() -> str:
    """Return the configured at-rest encryption key, or '' when unset."""
    return (os.getenv(PROVIDER_ENCRYPTION_KEY_ENV) or "").strip()


def _encrypt_for_write(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Encrypt plaintext API keys at-rest, leaving ciphertext untouched.

    Opt-in: with no key configured, rows pass through as-is (back-compat and
    the documented default). When a key is present, any existing plaintext row
    is transparently upgraded on this write; already-encrypted rows are never
    double-encrypted.
    """
    key_material = _configured_key()
    if not key_material:
        return records
    encrypted: list[dict[str, Any]] = []
    for entry in records:
        row = dict(entry)
        api_key = row.get("api_key")
        if isinstance(api_key, str) and api_key and not is_encrypted(api_key):
            row["api_key"] = encrypt_secret(api_key, key_material)
        encrypted.append(row)
    return encrypted


def effective_api_key(record: CustomProviderRecord) -> str:
    """Return the usable API key for a record.

    Legacy plaintext and empty keys pass through; ``enc:v1:`` envelopes are
    decrypted with the configured key. A ciphertext value without a configured
    key fails fast (the secret cannot be recovered).
    """
    if not is_encrypted(record.api_key):
        return record.api_key
    key_material = _configured_key()
    if not key_material:
        raise SecretCryptoError(
            f"Custom provider '{record.provider_id}' stores an encrypted key, "
            f"but {PROVIDER_ENCRYPTION_KEY_ENV} is not set."
        )
    return decrypt_secret(record.api_key, key_material)
