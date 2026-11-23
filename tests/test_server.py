from __future__ import annotations

import asyncio
import shutil
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from llengua_mcp import __version__
from llengua_mcp.server import INSTRUCTIONS, mcp


@pytest.mark.asyncio
async def test_stdio_initialize_list_and_call_tool(tmp_path) -> None:
    executable = shutil.which("llengua-mcp")
    params = StdioServerParameters(
        command=executable or sys.executable,
        args=[] if executable else ["-m", "llengua_mcp.server"],
        env={
            "LLENGUA_DATA_DIR": str(tmp_path / "data"),
            "LLENGUA_CACHE_DIR": str(tmp_path / "cache"),
        },
    )
    async with asyncio.timeout(20):
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.server_info.name == "llengua"
            assert initialized.server_info.version == __version__
            assert initialized.instructions == INSTRUCTIONS

            tools = {tool.name for tool in (await session.list_tools()).tools}
            assert tools == {tool.name for tool in await mcp.list_tools()}
            assert "etiquetes" in tools

            result = await session.call_tool("etiquetes", {})
            assert not result.is_error
            assert result.structured_content is not None
            assert result.structured_content["status"] == "ok"
            timing = result.structured_content["timing"]
            assert set(timing) == {"elapsed_ms", "upstream_requests", "cache_hits", "from_cache"}
            assert timing["upstream_requests"] == 0
            assert timing["cache_hits"] == 0
            assert timing["from_cache"] is False
            assert timing["elapsed_ms"] >= 0

            missing = await session.call_tool("engcat_cerca", {"terme": "bank"})
            assert not missing.is_error
            assert missing.structured_content["status"] == "unavailable"
            assert missing.structured_content["timing"]["upstream_requests"] == 0
            missing_direlex = await session.call_tool("direlex_cerca", {"lema": "alegria"})
            assert missing_direlex.structured_content["status"] == "unavailable"


@pytest.mark.asyncio
async def test_lifespan_opens_a_new_http_client_on_restart(tmp_path, monkeypatch) -> None:
    import llengua_mcp.server as server

    monkeypatch.setattr(server, "_app", None)
    monkeypatch.setenv("LLENGUA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LLENGUA_CACHE_DIR", str(tmp_path / "cache"))

    async with server._lifespan(mcp):
        first = await server.get_app()
        assert not first.http._client.is_closed
    assert first.http._client.is_closed

    async with server._lifespan(mcp):
        second = await server.get_app()
        assert second is not first
        assert not second.http._client.is_closed
    assert second.http._client.is_closed


@pytest.mark.asyncio
async def test_tools_are_registered() -> None:
    tools = {tool.name for tool in await mcp.list_tools()}
    expected = {
        "optimot_cerca",
        "optimot_fitxa",
        "consultes_iec",
        "diec_consulta",
        "esadir_consulta",
        "esadir_fitxa",
        "bdlex_consulta",
        "oiec_cerca",
        "oiec_text",
        "gramatica_cerca",
        "gramatica_text",
        "cerca_sinonims",
        "engcat_cerca",
        "direlex_cerca",
        "pamies_cerca",
        "dsff_cerca",
        "jane_cerca",
        "cerca",
        "cerca_frase",
        "cerca_forma",
        "cerca_lema",
        "cerca_patro",
        "continuar_cerca",
        "context",
        "collocacions",
        "collocacions_forma",
        "dispersio_cronologica",
        "dispersio_dialectal",
        "dispersio_general",
        "filtres_disponibles",
        "obres",
        "xifres",
        "etiquetes",
        "salut",
    }
    assert expected <= tools


@pytest.mark.asyncio
async def test_pattern_schema_is_typed() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    schema = tools["cerca_patro"].input_schema
    assert "PatternElement" in schema.get("$defs", {})
    element = schema["$defs"]["PatternElement"]
    assert set(element["properties"]["type"]["enum"]) == {
        "lema",
        "forma",
        "formalema",
        "cg",
        "qualsevol",
    }


class _FakeSoftcatala:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error

    async def cerca_async(self, paraula: str, *, context=None, limit=15):
        if self.error is not None:
            raise self.error
        return {"status": "ok", "groups": [], "query": {"paraula": paraula}}


class _FakeApp:
    def __init__(self, softcatala: _FakeSoftcatala) -> None:
        self.softcatala = softcatala


@pytest.mark.asyncio
async def test_tool_payload_includes_timing(monkeypatch) -> None:
    import llengua_mcp.server as server

    monkeypatch.setattr(server, "get_app", lambda: _resolve(_FakeApp(_FakeSoftcatala())))
    payload = await server.cerca_sinonims("maliciós")
    assert payload["status"] == "ok"
    timing = payload["timing"]
    assert set(timing) == {"elapsed_ms", "upstream_requests", "cache_hits", "from_cache"}
    assert timing["upstream_requests"] == 0
    assert timing["from_cache"] is False
    assert timing["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_timing_is_present_on_errors(monkeypatch) -> None:
    import llengua_mcp.server as server
    from llengua_mcp.errors import InvalidQueryError

    fake = _FakeSoftcatala(error=InvalidQueryError("La consulta és buida."))
    monkeypatch.setattr(server, "get_app", lambda: _resolve(_FakeApp(fake)))
    payload = await server.cerca_sinonims("")
    assert payload["status"] == "invalid_query"
    assert payload["error"]["message"] == "La consulta és buida."
    assert "timing" in payload


async def _resolve(value):
    return value


@pytest.mark.asyncio
async def test_failed_warm_does_not_block_startup(monkeypatch) -> None:
    import llengua_mcp.server as server

    class _Failing:
        async def warm(self) -> None:
            raise RuntimeError("dades absents")

    await server._warm_indexes(_FakeApp(_Failing()))  # type: ignore[arg-type]
