from __future__ import annotations

import asyncio

import httpx
import pytest

from llengua_mcp.config import Settings
from llengua_mcp.errors import UnexpectedResponseError
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
@pytest.mark.parametrize("invalid_body", ["<html>Error transitori</html>", "[]"])
async def test_post_json_caches_only_valid_objects(tmp_path, invalid_body) -> None:
    client = _client(tmp_path)
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, text=invalid_body)
        return httpx.Response(200, json={"data": []})

    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    url = "https://example.test/ajax"
    meter = start_meter()
    try:
        with pytest.raises(UnexpectedResponseError):
            await client.post_json(url, "draw=1")

        payload, fresh = await client.post_json(url, "draw=1")
        cached_payload, cached = await client.post_json(url, "draw=1")
    finally:
        reset_meter(meter)
        await client.aclose()

    assert payload == cached_payload == {"data": []}
    assert not fresh.from_cache
    assert cached.from_cache
    assert calls == meter.upstream_requests == 2
    assert meter.cache_hits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("warnings", "response_headers"),
    [([], {"cache-control": "no-store"}), (["transport_eof"], {})],
)
async def test_post_json_respects_cache_restrictions(
    tmp_path, monkeypatch, warnings, response_headers
) -> None:
    client = _client(tmp_path)
    calls = 0

    async def respond(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        return '{"data":[]}', 200, warnings, 11, response_headers

    monkeypatch.setattr(client, "_one_request", respond)
    try:
        for _ in range(2):
            payload, result = await client.post_json("https://example.test/ajax", "draw=1")
            assert payload == {"data": []}
            assert not result.from_cache
    finally:
        await client.aclose()
    assert calls == 2


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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["get", "post", "json"])
async def test_concurrent_identical_requests_share_cached_result(
    tmp_path, monkeypatch, mode
) -> None:
    client = _client(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def respond(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return '{"data":[]}', 200, [], 11, {}

    async def invoke():
        meter = start_meter()
        try:
            if mode == "get":
                result = await client.get_text("https://example.test/a")
            elif mode == "post":
                result = await client.post_text("https://example.test/a", "q=1")
            else:
                _, result = await client.post_json("https://example.test/a", "q=1")
            return result, meter.payload()
        finally:
            reset_meter(meter)

    monkeypatch.setattr(client, "_one_request", respond)
    tasks = [asyncio.create_task(invoke()) for _ in range(4)]
    try:
        await started.wait()
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*tasks)
        assert calls == 1
        assert sum(result.from_cache for result, _ in results) == 3
        assert sum(meter["upstream_requests"] for _, meter in results) == 1
        assert sum(meter["cache_hits"] for _, meter in results) == 3
        assert not client._cache_locks
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["no_store", "eof", "uncached", "invalid_json", "error"])
async def test_concurrent_unusable_results_are_not_shared(tmp_path, monkeypatch, kind) -> None:
    client = _client(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def respond(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        if kind == "error":
            return "error", 500, [], 5, {}
        if kind == "invalid_json":
            return "[]", 200, [], 2, {}
        return (
            "ok",
            200,
            ["transport_eof"] if kind == "eof" else [],
            2,
            ({"cache-control": "no-store"} if kind == "no_store" else {}),
        )

    async def invoke():
        if kind == "invalid_json":
            return await client.post_json("https://example.test/a", "q=1")
        return await client.get_text("https://example.test/a", use_cache=kind != "uncached")

    monkeypatch.setattr(client, "_one_request", respond)
    tasks = [asyncio.create_task(invoke()) for _ in range(3)]
    try:
        await started.wait()
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert calls == 3
        assert all(isinstance(result, Exception) for result in results) == (
            kind in {"invalid_json", "error"}
        )
        assert not client._cache_locks
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_distinct_headers_do_not_share_cached_responses(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path)
    both_started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def respond(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        if calls == 2:
            both_started.set()
        await release.wait()
        return headers["X-Variant"], 200, [], 1, {}

    monkeypatch.setattr(client, "_one_request", respond)
    tasks = [
        asyncio.create_task(client.get_text("https://example.test/a", headers={"X-Variant": v}))
        for v in ("a", "b")
    ]
    try:
        await asyncio.wait_for(both_started.wait(), timeout=2)
        release.set()
        assert [result.text for result in await asyncio.gather(*tasks)] == ["a", "b"]
        assert calls == 2
        assert not client._cache_locks
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_leader", [False, True])
async def test_cancelled_cache_waiter_or_leader_releases_lock(
    tmp_path, monkeypatch, cancel_leader
) -> None:
    client = _client(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def respond(method, url, *, body, headers):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return "ok", 200, [], 2, {}

    monkeypatch.setattr(client, "_one_request", respond)
    first = asyncio.create_task(client.get_text("https://example.test/a"))
    await started.wait()
    second = asyncio.create_task(client.get_text("https://example.test/a"))
    await asyncio.sleep(0)
    cancelled, survivor = (first, second) if cancel_leader else (second, first)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    release.set()
    try:
        assert (await survivor).text == "ok"
        assert calls == (2 if cancel_leader else 1)
        assert not client._cache_locks
    finally:
        await client.aclose()
