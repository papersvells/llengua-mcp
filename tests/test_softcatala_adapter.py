from __future__ import annotations

import asyncio

import pytest

from llengua_mcp.adapters.softcatala import SoftcatalaAdapter
from llengua_mcp.config import Settings
from llengua_mcp.errors import DataUnavailableError
from llengua_mcp.sinonims import SinonimsIndex


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


def _write_data(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text("-adj: maliciós, mordaç\n", encoding="utf-8")


def test_index_reports_loaded_state(tmp_path) -> None:
    _write_data(tmp_path)
    index = SinonimsIndex(tmp_path)
    assert index.loaded is False
    index.load()
    assert index.loaded is True


@pytest.mark.asyncio
async def test_warm_loads_the_index_before_the_first_query(tmp_path) -> None:
    _write_data(tmp_path)
    adapter = SoftcatalaAdapter(_settings(tmp_path))
    await adapter.warm()
    assert adapter.index.loaded is True
    result = await adapter.cerca_async("maliciós")
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_warm_is_idempotent_and_concurrent(tmp_path) -> None:
    _write_data(tmp_path)
    adapter = SoftcatalaAdapter(_settings(tmp_path))
    loads = 0
    original = adapter.index.load

    def counting_load() -> None:
        nonlocal loads
        if not adapter.index.loaded:
            loads += 1
        original()

    adapter.index.load = counting_load  # type: ignore[method-assign]
    await asyncio.gather(adapter.warm(), adapter.warm(), adapter.cerca_async("maliciós"))
    await adapter.warm()
    assert loads == 1


@pytest.mark.asyncio
async def test_warm_without_data_does_not_raise(tmp_path) -> None:
    adapter = SoftcatalaAdapter(_settings(tmp_path))
    with pytest.raises(DataUnavailableError):
        await adapter.warm()
