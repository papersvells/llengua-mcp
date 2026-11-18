from __future__ import annotations

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


def test_no_store_is_not_cacheable() -> None:
    from llengua_mcp.http import is_cacheable

    assert is_cacheable({})
    assert is_cacheable({"Cache-Control": "max-age=60"})
    assert not is_cacheable({"cache-control": "no-store, no-cache"})
