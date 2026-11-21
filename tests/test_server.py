from __future__ import annotations

import pytest

from llengua_mcp.server import mcp


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
