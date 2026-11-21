from __future__ import annotations

import httpx
import pytest

from llengua_mcp.config import Settings
from llengua_mcp.http import HttpClient, current_meter, reset_meter, start_meter


def _settings(tmp_path) -> Settings:
    return Settings(
        user_agent="test",
        contact="",
        rate_per_second=1.0,
        timeout_seconds=5,
        max_response_bytes=1_000_000,
        max_occurrences=50,
        cache_ttl_seconds=60,
        data_dir=tmp_path,
        cache_dir=tmp_path,
    )


def _client(tmp_path) -> HttpClient:
    client = HttpClient(_settings(tmp_path))
    client.limiter.interval = 0
    client.limiter._next_allowed.clear()
    return client


@pytest.mark.asyncio
async def test_transient_error_is_retried(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    calls = 0

    async def fake_request(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("fallada transitòria")
        return "ok", 200, [], 2, {}

    async def no_sleep(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(client, "_one_request", fake_request)
    monkeypatch.setattr("llengua_mcp.http.asyncio.sleep", no_sleep)
    result = await client._request(
        "GET",
        "https://example.test/",
        body=None,
        headers=None,
        cache_ttl=None,
        use_cache=False,
    )
    assert calls == 3
    assert result.text == "ok"


@pytest.mark.asyncio
async def test_no_store_is_not_cached(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    calls = 0

    async def fake_request(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        return "ok", 200, [], 2, {"cache-control": "no-store, no-cache"}

    monkeypatch.setattr(client, "_one_request", fake_request)
    for _ in range(2):
        await client._request(
            "GET",
            "https://example.test/",
            body=None,
            headers=None,
            cache_ttl=None,
            use_cache=True,
        )
    assert calls == 2


@pytest.mark.asyncio
async def test_cacheable_response_is_cached(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    calls = 0

    async def fake_request(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        return "ok", 200, [], 2, {"cache-control": "max-age=60"}

    monkeypatch.setattr(client, "_one_request", fake_request)
    for _ in range(2):
        await client._request(
            "GET",
            "https://example.test/",
            body=None,
            headers=None,
            cache_ttl=None,
            use_cache=True,
        )
    assert calls == 1


@pytest.mark.asyncio
async def test_meter_counts_network_and_cache(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    calls = 0

    async def fake_request(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        return "ok", 200, [], 2, {"cache-control": "max-age=60"}

    monkeypatch.setattr(client, "_one_request", fake_request)

    token = start_meter()
    try:
        await client.get_text("https://example.test/a")
        first = current_meter().payload()
        await client.get_text("https://example.test/a")
        second = current_meter().payload()
    finally:
        reset_meter(token)

    assert calls == 1
    assert first["upstream_requests"] == 1
    assert first["from_cache"] is False
    assert second["upstream_requests"] == 1
    assert second["cache_hits"] == 1
    assert second["from_cache"] is False
    assert second["elapsed_ms"] >= first["elapsed_ms"]


@pytest.mark.asyncio
async def test_meter_marks_a_pure_cache_hit(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)

    async def fake_request(method, url, *, body, headers):
        return "ok", 200, [], 2, {"cache-control": "max-age=60"}

    monkeypatch.setattr(client, "_one_request", fake_request)
    await client.get_text("https://example.test/b")

    token = start_meter()
    try:
        await client.get_text("https://example.test/b")
        payload = current_meter().payload()
    finally:
        reset_meter(token)

    assert payload["upstream_requests"] == 0
    assert payload["from_cache"] is True


@pytest.mark.asyncio
async def test_meter_counts_retries_as_separate_requests(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    calls = 0

    async def fake_request(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("fallada transitòria")
        return "ok", 200, [], 2, {}

    async def no_sleep(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(client, "_one_request", fake_request)
    monkeypatch.setattr("llengua_mcp.http.asyncio.sleep", no_sleep)

    token = start_meter()
    try:
        await client.get_text("https://example.test/c")
        payload = current_meter().payload()
    finally:
        reset_meter(token)

    assert calls == 3
    assert payload["upstream_requests"] == 3
    assert payload["from_cache"] is False
