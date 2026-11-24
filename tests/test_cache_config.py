from __future__ import annotations

import sys

import pytest

from llengua_mcp.cache import TTLCache
from llengua_mcp.config import Settings


def test_cache_hit_and_expiry() -> None:
    cache = TTLCache(default_ttl=60)
    cache.set("a", "value")
    assert cache.get("a") == "value"
    assert cache.hits == 1
    cache.set("b", "value", ttl=-1)
    assert cache.get("b") is None
    assert cache.misses >= 1


def test_cache_lru_limit() -> None:
    cache = TTLCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_rate_is_clamped_and_contact_added(monkeypatch) -> None:
    monkeypatch.setenv("LLENGUA_RATE", "5")
    monkeypatch.setenv("LLENGUA_CONTACT", "test@example.com")
    monkeypatch.delenv("LLENGUA_USER_AGENT", raising=False)
    monkeypatch.delenv("CTILC_USER_AGENT", raising=False)
    settings = Settings.from_env()
    assert settings.rate_per_second == 1.0
    assert "test@example.com" in settings.user_agent


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("LLENGUA_MAX_BYTES", "1", 1),
        ("LLENGUA_MAX_BYTES", str(sys.maxsize), sys.maxsize),
        ("LLENGUA_MAX_OCCURRENCES", "50", 50),
        ("LLENGUA_CACHE_TTL", "3600", 3600),
    ],
)
def test_integer_settings_accept_values_in_range(monkeypatch, name, value, expected) -> None:
    monkeypatch.setenv(name, value)
    assert getattr(Settings.from_env(), {
        "LLENGUA_MAX_BYTES": "max_response_bytes",
        "LLENGUA_MAX_OCCURRENCES": "max_occurrences",
        "LLENGUA_CACHE_TTL": "cache_ttl_seconds",
    }[name]) == expected


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LLENGUA_MAX_BYTES", "0"),
        ("LLENGUA_MAX_BYTES", "-1"),
        ("LLENGUA_MAX_BYTES", "1.5"),
        ("LLENGUA_MAX_BYTES", "nan"),
        ("LLENGUA_MAX_BYTES", "inf"),
        ("LLENGUA_MAX_BYTES", str(sys.maxsize + 1)),
        ("LLENGUA_MAX_OCCURRENCES", "0"),
        ("LLENGUA_MAX_OCCURRENCES", "-3"),
        ("LLENGUA_CACHE_TTL", "0"),
        ("LLENGUA_CACHE_TTL", "-10"),
        ("LLENGUA_TIMEOUT", "0"),
        ("LLENGUA_TIMEOUT", "-1"),
        ("LLENGUA_TIMEOUT", "nan"),
        ("LLENGUA_TIMEOUT", "inf"),
        ("LLENGUA_TIMEOUT", "-inf"),
        ("LLENGUA_RATE", "nan"),
        ("LLENGUA_RATE", "inf"),
        ("LLENGUA_RATE", "-inf"),
    ],
)
def test_invalid_numeric_settings_name_the_variable(monkeypatch, name, value) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()


def test_invalid_primary_rate_does_not_fall_back_to_legacy_alias(monkeypatch) -> None:
    monkeypatch.setenv("LLENGUA_RATE", "nan")
    monkeypatch.setenv("CTILC_RATE", "1")
    with pytest.raises(ValueError, match="LLENGUA_RATE"):
        Settings.from_env()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0", 0.2), ("-3", 0.2), ("0,5", 0.5), ("5", 1.0)],
)
def test_finite_rate_is_clamped(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("LLENGUA_RATE", value)
    assert Settings.from_env().rate_per_second == expected


def test_no_store_is_not_cacheable() -> None:
    from llengua_mcp.http import is_cacheable

    assert is_cacheable({})
    assert is_cacheable({"Cache-Control": "max-age=60"})
    assert not is_cacheable({"cache-control": "no-store, no-cache"})
