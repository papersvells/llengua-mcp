from __future__ import annotations

import pytest

from llengua_mcp.server import mcp


@pytest.mark.asyncio
async def test_tools_are_registered() -> None:
    tools = {tool.name for tool in await mcp.list_tools()}
    expected = {
        "optimot_cerca",
        "optimot_fitxa",
        "diec_consulta",
        "esadir_consulta",
        "esadir_fitxa",
        "bdlex_consulta",
        "cerca_sinonims",
        "cerca",
        "cerca_frase",
        "cerca_patro",
        "continuar_cerca",
        "context",
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
