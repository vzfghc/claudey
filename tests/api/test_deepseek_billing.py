"""Unit tests for the DeepSeek platform billing sync module."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from claudey.api import deepseek_billing
from claudey.config.settings import Settings

# Real response shapes captured from platform.deepseek.com (ground truth).
AMOUNT_MONTH = {
    "code": 0,
    "msg": "",
    "data": {
        "biz_code": 0,
        "biz_msg": "",
        "biz_data": {
            "total": [
                {
                    "model": "deepseek-v4-flash",
                    "usage": [
                        {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "100686720"},
                        {"type": "PROMPT_CACHE_MISS_TOKEN", "amount": "1305432"},
                        {"type": "RESPONSE_TOKEN", "amount": "656338"},
                        {"type": "REQUEST", "amount": "1212"},
                    ],
                }
            ],
            "days": [
                {
                    "date": "2026-05-26",
                    "data": [
                        {
                            "model": "deepseek-v4-flash",
                            "usage": [
                                {
                                    "type": "PROMPT_CACHE_HIT_TOKEN",
                                    "amount": "100000000",
                                },
                                {
                                    "type": "PROMPT_CACHE_MISS_TOKEN",
                                    "amount": "1000000",
                                },
                                {"type": "RESPONSE_TOKEN", "amount": "500000"},
                                {"type": "REQUEST", "amount": "1000"},
                            ],
                        }
                    ],
                },
                {
                    "date": "2026-05-27",
                    "data": [
                        {
                            "model": "deepseek-v4-flash",
                            "usage": [
                                {"type": "PROMPT_CACHE_HIT_TOKEN", "amount": "686720"},
                                {"type": "PROMPT_CACHE_MISS_TOKEN", "amount": "305432"},
                                {"type": "RESPONSE_TOKEN", "amount": "156338"},
                                {"type": "PROMPT_TOKEN", "amount": "1000"},
                                {"type": "REQUEST", "amount": "212"},
                            ],
                        }
                    ],
                },
            ],
        },
    },
}

COST_MONTH = {
    "code": 0,
    "msg": "",
    "data": {
        "biz_code": 0,
        "biz_msg": "",
        "biz_data": [
            {
                "total": [
                    {
                        "model": "deepseek-v4-flash",
                        "usage": [
                            {
                                "type": "PROMPT_CACHE_HIT_TOKEN",
                                "amount": "2.0137344000000000",
                            }
                        ],
                    }
                ],
                "days": [
                    {
                        "date": "2026-05-26",
                        "data": [
                            {
                                "model": "deepseek-v4-flash",
                                "usage": [
                                    {
                                        "type": "PROMPT_CACHE_HIT_TOKEN",
                                        "amount": "1.5000000000000000",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "date": "2026-05-27",
                        "data": [
                            {
                                "model": "deepseek-v4-flash",
                                "usage": [
                                    {
                                        "type": "PROMPT_CACHE_HIT_TOKEN",
                                        "amount": "0.5137344000000000",
                                    }
                                ],
                            }
                        ],
                    },
                ],
                "currency": "CNY",
            },
            {
                "total": [
                    {
                        "model": "deepseek-v4-flash",
                        "usage": [
                            {
                                "type": "PROMPT_CACHE_HIT_TOKEN",
                                "amount": "1.0000000000000000",
                            }
                        ],
                    }
                ],
                "days": [
                    {
                        "date": "2026-05-26",
                        "data": [
                            {
                                "model": "deepseek-v4-flash",
                                "usage": [
                                    {
                                        "type": "PROMPT_CACHE_HIT_TOKEN",
                                        "amount": "0.7500000000000000",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "date": "2026-05-27",
                        "data": [
                            {
                                "model": "deepseek-v4-flash",
                                "usage": [
                                    {
                                        "type": "PROMPT_CACHE_HIT_TOKEN",
                                        "amount": "0.2500000000000000",
                                    }
                                ],
                            }
                        ],
                    },
                ],
                "currency": "USD",
            },
        ],
    },
}

COST_MONTH_CNY_ONLY = {
    "code": 0,
    "msg": "",
    "data": {
        "biz_code": 0,
        "biz_msg": "",
        "biz_data": [
            {
                "total": [],
                "days": [
                    {
                        "date": "2026-05-26",
                        "data": [
                            {
                                "model": "deepseek-v4-flash",
                                "usage": [
                                    {
                                        "type": "PROMPT_CACHE_HIT_TOKEN",
                                        "amount": "9.9900000000000000",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "currency": "CNY",
            }
        ],
    },
}

API_BALANCE = {
    "is_available": True,
    "balance_infos": [
        {
            "currency": "USD",
            "total_balance": "110.00",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        }
    ],
}


class FakeBillingClient:
    """Synchronous httpx.Client stand-in serving queued responses."""

    def __init__(self, responses: Sequence[httpx.Response | Exception]):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __enter__(self) -> FakeBillingClient:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        self.calls.append((url, headers or {}))
        if not self._responses:
            raise httpx.ConnectError("no queued response")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        item.request = httpx.Request("GET", url)
        return item


class MustNotBeUsed:
    """httpx.Client stand-in that fails when instantiated."""

    def __init__(self, *args: object, **kwargs: object):
        raise AssertionError("httpx.Client must not be called")


def _install_client(
    monkeypatch: pytest.MonkeyPatch, responses: Sequence[httpx.Response | Exception]
) -> FakeBillingClient:
    client = FakeBillingClient(responses)
    monkeypatch.setattr(
        deepseek_billing.httpx, "Client", lambda *args, **kwargs: client
    )
    return client


def _install_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deepseek_billing.httpx, "Client", MustNotBeUsed)


def _settings(
    monkeypatch: pytest.MonkeyPatch, *, token: str = "", api_key: str = ""
) -> None:
    monkeypatch.setattr(
        deepseek_billing,
        "get_settings",
        lambda: Settings.model_construct(
            deepseek_session_token=token, deepseek_api_key=api_key
        ),
    )


def _write_store(home: Path, days: dict[str, dict]) -> Path:
    path = home / ".claudey" / "deepseek_billing.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"date": date, **values}, sort_keys=True) + "\n"
        for date, values in sorted(days.items())
    ]
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _fresh_synced_at() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture(autouse=True)
def _clear_balance_cache():
    deepseek_billing._balance_cache["value"] = None
    deepseek_billing._balance_cache["fetched_at"] = None
    yield
    deepseek_billing._balance_cache["value"] = None
    deepseek_billing._balance_cache["fetched_at"] = None


# ---------------------------------------------------------------- _as_float


def test_as_float_accepts_strings_numbers_and_garbage():
    assert deepseek_billing._as_float("2.0137344000000000") == 2.0137344
    assert deepseek_billing._as_float(110.0) == 110.0
    assert deepseek_billing._as_float(12) == 12.0
    assert deepseek_billing._as_float("not-a-number") == 0.0
    assert deepseek_billing._as_float(None) == 0.0
    assert deepseek_billing._as_float({"nested": 1}) == 0.0


# ---------------------------------------------------------- fetch_month_usage


def test_fetch_month_usage_parses_real_shapes_including_legacy_prompt_tokens(
    monkeypatch,
):
    client = _install_client(
        monkeypatch,
        [
            httpx.Response(200, json=AMOUNT_MONTH),
            httpx.Response(200, json=COST_MONTH),
        ],
    )

    days = deepseek_billing.fetch_month_usage("tok-123", 5, 2026)

    assert days == {
        "2026-05-26": {"tokens": 101500000, "requests": 1000, "cost_usd": 0.75},
        # PROMPT_TOKEN (legacy) counts as input tokens on top of the cache types.
        "2026-05-27": {"tokens": 1149490, "requests": 212, "cost_usd": 0.25},
    }
    assert len(client.calls) == 2
    amount_url, amount_headers = client.calls[0]
    assert amount_url == (
        "https://platform.deepseek.com/api/v0/usage/amount?month=5&year=2026"
    )
    assert amount_headers == {
        "Authorization": "Bearer tok-123",
        "Accept": "application/json",
    }
    cost_url, _ = client.calls[1]
    assert (
        cost_url == "https://platform.deepseek.com/api/v0/usage/cost?month=5&year=2026"
    )


def test_fetch_month_usage_falls_back_to_first_cost_entry_when_no_usd(monkeypatch):
    _install_client(
        monkeypatch,
        [
            httpx.Response(200, json=AMOUNT_MONTH),
            httpx.Response(200, json=COST_MONTH_CNY_ONLY),
        ],
    )

    days = deepseek_billing.fetch_month_usage("tok-123", 5, 2026)

    assert days is not None
    assert days["2026-05-26"]["cost_usd"] == 9.99


@pytest.mark.parametrize(
    "response",
    [
        {"code": 40002, "msg": "expired", "data": {}},
        {"code": 40003, "msg": "expired", "data": {}},
        {"code": 0, "data": {"biz_code": 40002, "biz_data": {}}},
        {"code": 0, "data": {"biz_code": 40003, "biz_data": {}}},
    ],
)
def test_fetch_month_usage_raises_invalid_token_on_expired_session_codes(
    monkeypatch, response
):
    _install_client(monkeypatch, [httpx.Response(200, json=response)])

    with pytest.raises(ValueError, match="invalid_token"):
        deepseek_billing.fetch_month_usage("tok-123", 5, 2026)


@pytest.mark.parametrize("status_code", [401, 403])
def test_fetch_month_usage_raises_invalid_token_on_http_401_403(
    monkeypatch, status_code
):
    _install_client(monkeypatch, [httpx.Response(status_code, json={})])

    with pytest.raises(ValueError, match="invalid_token"):
        deepseek_billing.fetch_month_usage("tok-123", 5, 2026)


def test_fetch_month_usage_returns_none_for_other_api_codes(monkeypatch):
    _install_client(
        monkeypatch,
        [httpx.Response(200, json={"code": 50000, "msg": "boom", "data": {}})],
    )

    assert deepseek_billing.fetch_month_usage("tok-123", 5, 2026) is None


def test_fetch_month_usage_returns_none_on_network_failure(monkeypatch):
    _install_client(monkeypatch, [httpx.ConnectError("network down")])

    assert deepseek_billing.fetch_month_usage("tok-123", 5, 2026) is None


def test_fetch_month_usage_returns_none_on_malformed_json(monkeypatch):
    response = httpx.Response(200, text="not-json{")
    _install_client(monkeypatch, [response])

    assert deepseek_billing.fetch_month_usage("tok-123", 5, 2026) is None


# --------------------------------------------------------------- sync_billing


def _sync_response_pairs(*month_pairs: tuple[dict, dict]) -> list[httpx.Response]:
    responses = []
    for amount, cost in month_pairs:
        responses.append(httpx.Response(200, json=amount))
        responses.append(httpx.Response(200, json=cost))
    return responses


def test_sync_billing_merges_months_dedups_by_date_and_writes_sorted(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 2)
    month_one_amount = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": {
                "days": [
                    {
                        "date": "2026-06-01",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "10"},
                                    {"type": "REQUEST", "amount": "1"},
                                ],
                            }
                        ],
                    },
                    {
                        "date": "2026-06-02",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "20"},
                                    {"type": "REQUEST", "amount": "2"},
                                ],
                            }
                        ],
                    },
                ]
            },
        },
    }
    month_two_amount = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": {
                "days": [
                    {
                        "date": "2026-06-02",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "99"},
                                    {"type": "REQUEST", "amount": "9"},
                                ],
                            }
                        ],
                    },
                    {
                        "date": "2026-07-01",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "5"},
                                    {"type": "REQUEST", "amount": "1"},
                                ],
                            }
                        ],
                    },
                ]
            },
        },
    }

    def cost_pair(amounts: list[str], dates: list[str]) -> dict:
        return {
            "code": 0,
            "data": {
                "biz_code": 0,
                "biz_data": [
                    {
                        "currency": "USD",
                        "days": [
                            {
                                "date": date,
                                "data": [
                                    {
                                        "model": "m",
                                        "usage": [
                                            {
                                                "type": "PROMPT_CACHE_HIT_TOKEN",
                                                "amount": amount,
                                            }
                                        ],
                                    }
                                ],
                            }
                            for date, amount in zip(dates, amounts, strict=True)
                        ],
                    }
                ],
            },
        }

    month_one_cost = cost_pair(["1.00", "2.00"], ["2026-06-01", "2026-06-02"])
    month_two_cost = cost_pair(["9.00", "0.50"], ["2026-06-02", "2026-07-01"])
    client = _install_client(
        monkeypatch,
        _sync_response_pairs(
            (month_one_amount, month_one_cost),
            (month_two_amount, month_two_cost),
        ),
    )

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result == {"synced_days": 4, "error": None}
    stored = deepseek_billing._read_store(tmp_path)
    assert list(stored) == ["2026-06-01", "2026-06-02", "2026-07-01"]
    assert stored["2026-06-01"] == {
        "tokens": 10,
        "requests": 1,
        "cost_usd": 1.0,
        "synced_at": stored["2026-06-01"]["synced_at"],
    }
    # Latest month wins for the shared date.
    assert stored["2026-06-02"]["tokens"] == 99
    assert stored["2026-06-02"]["requests"] == 9
    assert stored["2026-06-02"]["cost_usd"] == 9.0
    assert stored["2026-07-01"]["tokens"] == 5
    assert stored["2026-07-01"]["cost_usd"] == 0.5
    assert len(client.calls) == 4


def test_sync_billing_continues_after_failed_month(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 2)
    ok_amount = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": {
                "days": [
                    {
                        "date": "2026-07-01",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "7"},
                                    {"type": "REQUEST", "amount": "1"},
                                ],
                            }
                        ],
                    }
                ]
            },
        },
    }
    ok_cost = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": [
                {
                    "currency": "USD",
                    "days": [
                        {
                            "date": "2026-07-01",
                            "data": [
                                {
                                    "model": "m",
                                    "usage": [
                                        {
                                            "type": "PROMPT_CACHE_HIT_TOKEN",
                                            "amount": "0.70",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    _install_client(
        monkeypatch,
        [
            httpx.ConnectError("offline"),
            httpx.Response(200, json=ok_amount),
            httpx.Response(200, json=ok_cost),
        ],
    )

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    # A failed month must not stop the loop or fail the whole sync:
    # partial success reports ok (error None).
    assert result["error"] is None
    assert result["synced_days"] == 1
    stored = deepseek_billing._read_store(tmp_path)
    assert stored["2026-07-01"]["tokens"] == 7


def test_sync_billing_stops_on_invalid_token(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 12)
    client = _install_client(monkeypatch, [httpx.Response(401, json={})])

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result == {"synced_days": 0, "error": "invalid_token"}
    assert len(client.calls) == 1


def test_sync_billing_stops_on_nested_biz_code_40003(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 12)
    expired = {
        "code": 0,
        "msg": "",
        "data": {"biz_code": 40003, "biz_msg": "expired", "biz_data": {}},
    }
    client = _install_client(monkeypatch, [httpx.Response(200, json=expired)])

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result == {"synced_days": 0, "error": "invalid_token"}
    assert len(client.calls) == 1


def test_sync_billing_never_raises_when_all_months_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 3)
    _install_client(
        monkeypatch,
        [
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
        ],
    )

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result == {"synced_days": 0, "error": "offline"}


def test_sync_billing_without_token_is_a_noop(monkeypatch, tmp_path):
    _install_no_http(monkeypatch)

    result = deepseek_billing.sync_billing(tmp_path, "")

    assert result == {"synced_days": 0, "error": None}


# ---------------------------------------------------------------- balance_usd


def test_balance_usd_parses_api_balance(monkeypatch):
    _install_client(monkeypatch, [httpx.Response(200, json=API_BALANCE)])

    balance = deepseek_billing.balance_usd("sk-123")

    assert balance == {"currency": "USD", "total_balance": 110.0}


def test_balance_usd_accepts_number_balance(monkeypatch):
    payload = {
        "is_available": True,
        "balance_infos": [{"currency": "USD", "total_balance": 7.97}],
    }
    _install_client(monkeypatch, [httpx.Response(200, json=payload)])

    balance = deepseek_billing.balance_usd("sk-123")

    assert balance == {"currency": "USD", "total_balance": 7.97}


def test_balance_usd_returns_none_on_any_failure(monkeypatch):
    _install_client(monkeypatch, [httpx.ConnectError("down")])
    assert deepseek_billing.balance_usd("sk-123") is None

    _install_client(monkeypatch, [httpx.Response(500, json={})])
    assert deepseek_billing.balance_usd("sk-123") is None


# ------------------------------------------------------------- billing_payload


def test_unwrap_token_accepts_bare_and_envelope():
    assert deepseek_billing._unwrap_token("abc123") == "abc123"
    envelope = '{"value":"mjF+secret","__version":"0"}'
    assert deepseek_billing._unwrap_token(envelope) == "mjF+secret"
    assert deepseek_billing._unwrap_token('{"other":1}') == '{"other":1}'
    assert deepseek_billing._unwrap_token("not json {") == "not json {"


def test_billing_payload_unwraps_enveloped_session_token(monkeypatch, tmp_path):
    _settings(
        monkeypatch,
        token='{"value":"mjF+secret","__version":"0"}',
        api_key="",
    )
    captured: dict[str, str] = {}

    def _fake_sync(home, token):
        captured["token"] = token
        return {"synced_days": 0, "error": None}

    monkeypatch.setattr(deepseek_billing, "sync_billing", _fake_sync)
    monkeypatch.setattr(deepseek_billing, "_read_store", lambda home: {})
    monkeypatch.setattr(deepseek_billing, "_store_is_stale", lambda store: True)

    deepseek_billing.billing_payload(home=tmp_path)

    assert captured["token"] == "mjF+secret"


def test_sync_billing_partial_failure_reports_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 2)

    def _fake_fetch(token, month, year):
        if month == 8:
            return None  # transient failure (e.g. pre-account month)
        return {"2026-07-01": {"tokens": 10, "requests": 1, "cost_usd": 0.5}}

    monkeypatch.setattr(deepseek_billing, "fetch_month_usage", _fake_fetch)

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result["synced_days"] >= 1
    assert result["error"] is None


def test_sync_billing_all_months_failed_reports_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 2)
    monkeypatch.setattr(
        deepseek_billing, "fetch_month_usage", lambda token, month, year: None
    )

    result = deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert result["synced_days"] == 0
    assert result["error"] == "offline"


def test_billing_payload_not_configured_is_safe_and_empty(monkeypatch, tmp_path):
    _settings(monkeypatch, token="", api_key="")
    _install_no_http(monkeypatch)

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload == {
        "available": False,
        "configured": False,
        "status": "not_configured",
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "total_requests": 0,
        "balance_usd": None,
        "currency": None,
        "days": [],
        "last_synced": None,
    }


def test_billing_payload_fresh_store_skips_sync(monkeypatch, tmp_path):
    _settings(monkeypatch, token="tok-123", api_key="")
    _install_no_http(monkeypatch)
    now = _fresh_synced_at()
    _write_store(
        tmp_path,
        {
            "2026-07-01": {
                "tokens": 10,
                "requests": 1,
                "cost_usd": 0.5,
                "synced_at": now,
            }
        },
    )

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["configured"] is True
    assert payload["available"] is True
    assert payload["status"] == "ok"
    assert payload["total_tokens"] == 10
    assert payload["total_requests"] == 1
    assert payload["total_cost_usd"] == 0.5
    assert payload["days"] == [
        {"date": "2026-07-01", "tokens": 10, "requests": 1, "cost_usd": 0.5}
    ]
    assert payload["last_synced"] == now


def test_billing_payload_syncs_when_store_is_stale(monkeypatch, tmp_path):
    _settings(monkeypatch, token="tok-123", api_key="")
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 1)
    stale = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    _write_store(
        tmp_path,
        {
            "2026-07-01": {
                "tokens": 10,
                "requests": 1,
                "cost_usd": 0.5,
                "synced_at": stale,
            }
        },
    )
    fresh_amount = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": {
                "days": [
                    {
                        "date": "2026-08-01",
                        "data": [
                            {
                                "model": "m",
                                "usage": [
                                    {"type": "RESPONSE_TOKEN", "amount": "3"},
                                    {"type": "REQUEST", "amount": "1"},
                                ],
                            }
                        ],
                    }
                ]
            },
        },
    }
    fresh_cost = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": [
                {
                    "currency": "USD",
                    "days": [
                        {
                            "date": "2026-08-01",
                            "data": [
                                {
                                    "model": "m",
                                    "usage": [
                                        {
                                            "type": "PROMPT_CACHE_HIT_TOKEN",
                                            "amount": "0.25",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    _install_client(
        monkeypatch,
        [httpx.Response(200, json=fresh_amount), httpx.Response(200, json=fresh_cost)],
    )

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["status"] == "ok"
    assert payload["available"] is True
    assert {day["date"] for day in payload["days"]} == {"2026-07-01", "2026-08-01"}
    assert payload["total_tokens"] == 13
    assert payload["total_cost_usd"] == 0.75
    assert payload["last_synced"] is not None


def test_billing_payload_invalid_token_keeps_stored_days(monkeypatch, tmp_path):
    _settings(monkeypatch, token="tok-expired", api_key="")
    stale = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    _write_store(
        tmp_path,
        {
            "2026-07-01": {
                "tokens": 10,
                "requests": 1,
                "cost_usd": 0.5,
                "synced_at": stale,
            }
        },
    )
    _install_client(monkeypatch, [httpx.Response(401, json={})])

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["status"] == "invalid_token"
    assert payload["available"] is True
    assert payload["days"][0]["tokens"] == 10
    assert payload["last_synced"] == stale


def test_billing_payload_balances_via_api_key_with_ttl_cache(monkeypatch, tmp_path):
    _settings(monkeypatch, token="", api_key="sk-123")
    instances: list[FakeBillingClient] = []

    def factory(*args: object, **kwargs: object) -> FakeBillingClient:
        client = FakeBillingClient([httpx.Response(200, json=API_BALANCE)])
        instances.append(client)
        return client

    monkeypatch.setattr(deepseek_billing.httpx, "Client", factory)

    first = deepseek_billing.billing_payload(home=tmp_path)
    second = deepseek_billing.billing_payload(home=tmp_path)

    assert first["balance_usd"] == 110.0
    assert first["currency"] == "USD"
    assert second["balance_usd"] == 110.0
    assert len(instances) == 1


def test_billing_payload_degrades_offline_without_raising(monkeypatch, tmp_path):
    _settings(monkeypatch, token="tok-123", api_key="sk-123")
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 1)
    _install_client(
        monkeypatch,
        [httpx.ConnectError("down"), httpx.ConnectError("down")],
    )

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["status"] == "offline"
    assert payload["available"] is False
    assert payload["balance_usd"] is None
    assert payload["currency"] is None
    assert payload["days"] == []


def test_billing_payload_stored_days_survive_removed_token(monkeypatch, tmp_path):
    _settings(monkeypatch, token="", api_key="")
    _install_no_http(monkeypatch)
    _write_store(
        tmp_path,
        {
            "2026-07-01": {
                "tokens": 10,
                "requests": 1,
                "cost_usd": 0.5,
                "synced_at": _fresh_synced_at(),
            }
        },
    )

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["configured"] is False
    assert payload["status"] == "not_configured"
    assert payload["available"] is True
    assert payload["days"][0]["tokens"] == 10


def test_billing_payload_skips_garbage_store_lines_without_raising(
    monkeypatch, tmp_path
):
    _settings(monkeypatch, token="", api_key="")
    _install_no_http(monkeypatch)
    path = tmp_path / ".claudey" / "deepseek_billing.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    garbage = "not-json{\n[]\n"
    garbage += (
        json.dumps(
            {
                "date": "2026-07-01",
                "tokens": 10,
                "requests": 1,
                "cost_usd": 0.5,
                "synced_at": _fresh_synced_at(),
            },
            sort_keys=True,
        )
        + "\n"
    )
    garbage += '{"date": 42, "tokens": "x"}\n'
    path.write_text(garbage, encoding="utf-8")

    payload = deepseek_billing.billing_payload(home=tmp_path)

    assert payload["available"] is True
    assert len(payload["days"]) == 1
    assert payload["days"][0] == {
        "date": "2026-07-01",
        "tokens": 10,
        "requests": 1,
        "cost_usd": 0.5,
    }


# ------------------------------------------------------- security: no token leak


class TraceRecorder:
    """Records trace_event kwargs so tests can assert on them."""

    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_sync_failures_never_include_the_token_in_trace_calls(monkeypatch, tmp_path):
    recorder = TraceRecorder()
    monkeypatch.setattr(deepseek_billing, "trace_event", recorder)
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 1)

    _install_client(
        monkeypatch, [httpx.ConnectError("down"), httpx.ConnectError("down")]
    )
    deepseek_billing.sync_billing(tmp_path, "tok-super-secret")
    assert recorder.calls, "offline sync should emit a trace"

    _install_client(monkeypatch, [httpx.Response(401, json={})])
    deepseek_billing.sync_billing(tmp_path, "tok-super-secret")
    assert len(recorder.calls) == 2, "invalid-token sync should emit a trace"

    for call in recorder.calls:
        assert "tok-super-secret" not in json.dumps(call, default=str)
        assert "reason" in call
        assert call["source"] == "deepseek_billing"


def test_sync_success_emits_no_trace(monkeypatch, tmp_path):
    recorder = TraceRecorder()
    monkeypatch.setattr(deepseek_billing, "trace_event", recorder)
    monkeypatch.setattr(deepseek_billing, "SYNC_MONTHS", 1)
    ok_amount = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": {
                "days": [
                    {
                        "date": "2026-08-01",
                        "data": [
                            {
                                "model": "m",
                                "usage": [{"type": "REQUEST", "amount": "1"}],
                            }
                        ],
                    }
                ]
            },
        },
    }
    ok_cost = {
        "code": 0,
        "data": {
            "biz_code": 0,
            "biz_data": [{"currency": "USD", "days": []}],
        },
    }
    _install_client(
        monkeypatch,
        [httpx.Response(200, json=ok_amount), httpx.Response(200, json=ok_cost)],
    )

    deepseek_billing.sync_billing(tmp_path, "tok-123")

    assert recorder.calls == []
