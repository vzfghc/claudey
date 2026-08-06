"""DeepSeek platform billing sync for the admin Usage view.

DeepSeek has no public usage API. The platform dashboard data comes from
PRIVATE (unversioned) endpoints under ``https://platform.deepseek.com/api/v0``
authenticated with the browser session token (``userToken`` from
localStorage on platform.deepseek.com). Those endpoints may change without
notice and the session token expires periodically, so every response is
parsed defensively and this module never raises: callers always receive a
payload with degraded values.

SECURITY: the session token and API key are never logged or rendered, and
the platform export ZIP is never used — its amount CSV contains plaintext
API keys. Only the ``sk-`` API key balance endpoint (``/user/balance``)
uses the API key.

Data model: one JSONL line per UTC day in the store file
(``~/.claudey/deepseek_billing.jsonl``):

    {"date": "2026-05-26", "tokens": 101500000, "requests": 1212,
     "cost_usd": 0.75, "synced_at": "2026-08-06T12:00:00+00:00"}

``synced_at`` is the write timestamp of the newest sync that produced the
line; the newest one across the store drives the TTL-based re-sync.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from claudey.config.paths import HANS_CONFIG_DIRNAME, config_dir_path
from claudey.config.settings import get_settings
from claudey.core.trace import trace_event

PLATFORM_BASE = "https://platform.deepseek.com/api/v0"
API_BASE = "https://api.deepseek.com"
STORE_NAME = "deepseek_billing.jsonl"
SYNC_MONTHS = 12
SYNC_TTL = timedelta(hours=12)
BALANCE_TTL = timedelta(hours=6)
HTTP_TIMEOUT = 5.0
MAX_STORE_BYTES = 2_000_000  # read only the recent tail of the store

#: Usage-amount types that count toward the token total. ``PROMPT_TOKEN`` is
#: the legacy input type and still counts as input.
_TOKEN_TYPES = {
    "PROMPT_CACHE_HIT_TOKEN",
    "PROMPT_CACHE_MISS_TOKEN",
    "RESPONSE_TOKEN",
    "PROMPT_TOKEN",
}

#: Expired/invalid session-token error codes (top-level ``code`` or nested
#: ``data.biz_code``), plus HTTP 401/403.
_EXPIRED_SESSION_CODES = (40002, 40003)

#: Cached API-key balance; refreshed at most every BALANCE_TTL.
_balance_cache: dict[str, Any] = {
    "value": None,
    "fetched_at": None,
}


def _billing_store_path(home: Path | None = None) -> Path:
    """Return the billing store path under the user config directory.

    ``home`` overrides ``Path.home()`` so tests and callers can point at an
    isolated directory; the default reuses ``config_dir_path()``.
    """
    if home is not None:
        return home / HANS_CONFIG_DIRNAME / STORE_NAME
    return config_dir_path() / STORE_NAME


def _as_float(value: Any) -> float:
    """Coerce a string-or-number amount to float; anything else is 0.0."""
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0


def _read_store(home: Path) -> dict[str, dict[str, Any]]:
    """Parse the store into {date: {tokens, requests, cost_usd, synced_at}}.

    Corrupt or unparsable lines are skipped; only the recent tail is read
    when the file grows past MAX_STORE_BYTES.
    """
    path = _billing_store_path(home)
    try:
        data = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if len(data) > MAX_STORE_BYTES:
        data = data[-MAX_STORE_BYTES:]

    days: dict[str, dict[str, Any]] = {}
    for line in data.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        date = entry.get("date")
        if not isinstance(date, str) or not date:
            continue
        synced_at = entry.get("synced_at")
        days[date] = {
            "tokens": int(_as_float(entry.get("tokens"))),
            "requests": int(_as_float(entry.get("requests"))),
            "cost_usd": _as_float(entry.get("cost_usd")),
            "synced_at": synced_at if isinstance(synced_at, str) else None,
        }
    return days


def _write_store(home: Path, days: dict[str, dict[str, Any]]) -> None:
    """Atomically persist the store, one line per day, sorted by date."""
    path = _billing_store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"date": date, **days[date]}, sort_keys=True) + "\n"
        for date in sorted(days)
    ]
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text("".join(lines), encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _last_synced_dt(store: dict[str, dict[str, Any]]) -> datetime | None:
    """Return the newest synced_at across the store, or None."""
    latest: datetime | None = None
    for values in store.values():
        synced_at = values.get("synced_at")
        if not isinstance(synced_at, str):
            continue
        try:
            when = datetime.fromisoformat(synced_at)
        except ValueError:
            continue
        if latest is None or when > latest:
            latest = when
    return latest


def _store_is_stale(store: dict[str, dict[str, Any]]) -> bool:
    """True when the store is missing or older than SYNC_TTL."""
    last = _last_synced_dt(store)
    if last is None:
        return True
    return datetime.now(UTC) - last >= SYNC_TTL


def _sum_usage(entries: Any) -> tuple[int, int]:
    """Sum token types and REQUEST counts across model usage entries."""
    tokens = 0
    requests = 0
    for model in entries or []:
        if not isinstance(model, dict):
            continue
        for usage in model.get("usage") or []:
            if not isinstance(usage, dict):
                continue
            amount = int(_as_float(usage.get("amount")))
            kind = usage.get("type")
            if kind == "REQUEST":
                requests += amount
            elif kind in _TOKEN_TYPES:
                tokens += amount
    return tokens, requests


def _sum_cost(entries: Any) -> float:
    """Sum every usage amount (all are cost values in the cost endpoint)."""
    total = 0.0
    for model in entries or []:
        if not isinstance(model, dict):
            continue
        for usage in model.get("usage") or []:
            if isinstance(usage, dict):
                total += _as_float(usage.get("amount"))
    return total


def _parse_amount_days(payload: Any) -> dict[str, tuple[int, int]]:
    """Extract {date: (tokens, requests)} from a usage/amount response."""
    data = payload.get("data") if isinstance(payload, dict) else None
    biz_data = data.get("biz_data") if isinstance(data, dict) else None
    if not isinstance(biz_data, dict):
        return {}
    days: dict[str, tuple[int, int]] = {}
    for day in biz_data.get("days") or []:
        if not isinstance(day, dict):
            continue
        date = day.get("date")
        if not isinstance(date, str) or not date:
            continue
        days[date] = _sum_usage(day.get("data"))
    return days


def _parse_cost_days(payload: Any) -> tuple[dict[str, float], str]:
    """Extract {date: cost} and the currency from a usage/cost response.

    ``biz_data`` is an array of entries; the USD entry wins when present,
    otherwise the first entry is used, with its currency.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    biz_data = data.get("biz_data") if isinstance(data, dict) else None
    if not isinstance(biz_data, list):
        return {}, ""
    entry = next(
        (
            item
            for item in biz_data
            if isinstance(item, dict) and item.get("currency") == "USD"
        ),
        None,
    )
    if entry is None:
        entry = next((item for item in biz_data if isinstance(item, dict)), None)
    if not isinstance(entry, dict):
        return {}, ""
    days: dict[str, float] = {}
    for day in entry.get("days") or []:
        if not isinstance(day, dict):
            continue
        date = day.get("date")
        if not isinstance(date, str) or not date:
            continue
        days[date] = _sum_cost(day.get("data"))
    return days, str(entry.get("currency") or "")


def _check_error(payload: Any) -> None:
    """Raise ValueError("invalid_token") for expired sessions.

    Other nonzero error codes raise a generic ValueError; the envelope is
    not schema-stable, so every field lookup is defensive.
    """
    if not isinstance(payload, dict):
        raise ValueError("invalid_envelope")
    code = payload.get("code")
    data = payload.get("data")
    biz_code = data.get("biz_code") if isinstance(data, dict) else None
    if code in _EXPIRED_SESSION_CODES or biz_code in _EXPIRED_SESSION_CODES:
        raise ValueError("invalid_token")
    if code not in (None, 0):
        raise ValueError(f"platform_error_{code}")
    if biz_code not in (None, 0):
        raise ValueError(f"platform_error_{biz_code}")


def _platform_get(client: httpx.Client, token: str, url: str) -> dict[str, Any]:
    """GET a platform endpoint with the session token; raises on failure."""
    response = client.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if response.status_code in (401, 403):
        raise ValueError("invalid_token")
    response.raise_for_status()
    payload = response.json()
    _check_error(payload)
    return payload


def fetch_month_usage(
    token: str, month: int, year: int
) -> dict[str, dict[str, float | int]] | None:
    """Fetch one month of usage amounts and costs from the platform.

    Returns {date: {"tokens": int, "requests": int, "cost_usd": float}},
    or None on any non-token failure (network errors, bad envelopes,
    generic platform error codes).

    Raises ValueError("invalid_token") on HTTP 401/403 or expired-session
    codes (40002/40003) so ``sync_billing`` can classify the outcome.
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            amount_payload = _platform_get(
                client,
                token,
                f"{PLATFORM_BASE}/usage/amount?month={month}&year={year}",
            )
            cost_payload = _platform_get(
                client,
                token,
                f"{PLATFORM_BASE}/usage/cost?month={month}&year={year}",
            )
    except ValueError as exc:
        # Only the invalid-token marker propagates; JSON and envelope
        # failures (JSONDecodeError is a ValueError subclass) degrade to None.
        if str(exc) == "invalid_token":
            raise
        return None
    except Exception:
        return None
    amount_days = _parse_amount_days(amount_payload)
    cost_days, _ = _parse_cost_days(cost_payload)

    days: dict[str, dict[str, float | int]] = {}
    for date in set(amount_days) | set(cost_days):
        tokens, requests = amount_days.get(date, (0, 0))
        days[date] = {
            "tokens": tokens,
            "requests": requests,
            "cost_usd": cost_days.get(date, 0.0),
        }
    return days


def _trace_sync_failure(reason: str) -> None:
    """Emit one structured failure trace; never includes the token."""
    trace_event(
        stage="billing",
        event="deepseek_billing.sync_failed",
        source="deepseek_billing",
        reason=reason,
    )


def sync_billing(home: Path, token: str) -> dict[str, Any]:
    """Backfill the last SYNC_MONTHS months into the store. Never raises.

    Merges per-day values (a later month wins for shared dates), writes the
    store atomically sorted by date, and returns
    ``{"synced_days": n, "error": None | "invalid_token" | "offline"}``.
    A failed month keeps previously stored days; an expired session stops
    the loop immediately.
    """
    if not token:
        return {"synced_days": 0, "error": None}

    days = _read_store(home)
    now = datetime.now(UTC)
    synced_at = now.isoformat()
    year, month = now.year, now.month
    synced_days = 0
    error: str | None = None

    for _ in range(SYNC_MONTHS):
        try:
            month_days = fetch_month_usage(token, month, year)
        except ValueError as exc:
            if str(exc) == "invalid_token":
                error = "invalid_token"
                break
            error = "offline"
        except Exception:
            error = "offline"
        else:
            if month_days is None:
                error = "offline"
            else:
                for date, values in month_days.items():
                    days[date] = {
                        "tokens": values["tokens"],
                        "requests": values["requests"],
                        "cost_usd": values["cost_usd"],
                        "synced_at": synced_at,
                    }
                    synced_days += 1
        # Decrement on every iteration, failed months included — otherwise a
        # failing month retries itself in place and drops the older ones.
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    # A single pre-account or transiently failed month is not an outage:
    # report ok as long as at least one month synced. invalid_token always
    # wins because it stops the loop.
    if error == "offline" and synced_days:
        error = None
    if error is not None:
        _trace_sync_failure(error)
    if synced_days:
        _write_store(home, days)
    return {"synced_days": synced_days, "error": error}


def balance_usd(api_key: str) -> dict[str, Any] | None:
    """Current DeepSeek API-key balance, or None on any failure.

    Returns {"currency": str, "total_balance": float}; amounts on the wire
    may be strings or numbers.
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            response = client.get(
                f"{API_BASE}/user/balance",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None
    infos = payload.get("balance_infos") if isinstance(payload, dict) else None
    if not isinstance(infos, list) or not infos:
        return None
    entry = next(
        (
            item
            for item in infos
            if isinstance(item, dict) and item.get("currency") == "USD"
        ),
        infos[0],
    )
    if not isinstance(entry, dict):
        return None
    return {
        "currency": str(entry.get("currency") or "USD"),
        "total_balance": _as_float(entry.get("total_balance")),
    }


def _cached_balance(api_key: str) -> dict[str, Any] | None:
    """API-key balance, refreshed at most every BALANCE_TTL."""
    now = datetime.now(UTC)
    value = _balance_cache["value"]
    fetched_at = _balance_cache["fetched_at"]
    if (
        isinstance(value, dict)
        and isinstance(fetched_at, datetime)
        and now - fetched_at < BALANCE_TTL
    ):
        return value
    value = balance_usd(api_key)
    _balance_cache["value"] = value
    _balance_cache["fetched_at"] = now
    return value


def _unwrap_token(value: str) -> str:
    """Extract the bearer token from the platform's localStorage format.

    platform.deepseek.com stores `userToken` as a JSON envelope
    ``{"value": "<token>", "__version": "0"}``; accept both the envelope
    and a bare token so either paste works.
    """
    stripped = value.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(parsed, dict) and isinstance(parsed.get("value"), str):
        return parsed["value"]
    return stripped


def billing_payload(home: Path | None = None) -> dict[str, Any]:
    """Assemble the DeepSeek billing payload the Usage view renders.

    Never raises: every source is optional and degrades to empty values.
    The session token drives the sync (bounded by SYNC_TTL / the
    12-month loop); the API key drives the cached balance. ``status``
    reflects the sync outcome: "not_configured" when no token is set,
    "invalid_token"/"offline" after a failed sync attempt, else "ok".
    """
    home = home or Path.home()
    settings = get_settings()
    token = _unwrap_token(settings.deepseek_session_token)
    api_key = settings.deepseek_api_key
    configured = bool(token)

    store = _read_store(home)
    status = "not_configured"
    if configured:
        status = "ok"
        if _store_is_stale(store):
            status = sync_billing(home, token)["error"] or "ok"
            store = _read_store(home)

    balance_usd_value = None
    balance_currency = None
    if api_key:
        balance = _cached_balance(api_key)
        if balance is not None:
            balance_usd_value = balance["total_balance"]
            balance_currency = balance["currency"]

    days = [
        {
            "date": date,
            "tokens": values["tokens"],
            "requests": values["requests"],
            "cost_usd": values["cost_usd"],
        }
        for date, values in sorted(store.items())
    ]
    last_synced = _last_synced_dt(store)
    return {
        "available": bool(days),
        "configured": configured,
        "status": status,
        "total_cost_usd": round(sum(day["cost_usd"] for day in days), 6),
        "total_tokens": sum(day["tokens"] for day in days),
        "total_requests": sum(day["requests"] for day in days),
        "balance_usd": balance_usd_value,
        "currency": balance_currency,
        "days": days,
        "last_synced": last_synced.isoformat() if last_synced else None,
    }
