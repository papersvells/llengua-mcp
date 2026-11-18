from __future__ import annotations

import os

import pytest

from llengua_mcp.app import App
from llengua_mcp.config import Settings
from llengua_mcp.models import PatternElement

pytestmark = pytest.mark.skipif(
    os.getenv("LLENGUA_LIVE") != "1",
    reason="Prova en directe optativa; defineix LLENGUA_LIVE=1 per executar-la.",
)


@pytest.mark.asyncio
async def test_live_ctilc_control() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.ctilc.salut()
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["echo_verified"] is True
    assert result["pattern_echo"] == "somriure adj:-"
    assert isinstance(result["observed_total"], int)
    assert result["observed_total"] > 0


@pytest.mark.asyncio
async def test_live_bdlex() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.bdlex.consulta("engrunar", limit=1)
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["entries"]
    assert result["entries"][0]["headword"]
    assert result["entries"][0]["dictionary"] in {"DCVB", "DIEe"}


@pytest.mark.asyncio
async def test_live_dispersio_cronologica() -> None:
    app = App(Settings.from_env())
    try:
        start = await app.ctilc.search_pattern(
            [
                PatternElement(type="lema", value="somriure"),
                PatternElement(type="cg", category="adj"),
            ],
            limit=1,
        )
        assert start["status"] == "ok"
        assert start["next_cursor"]
        disp = await app.ctilc.dispersio_cronologica(start["next_cursor"])
    finally:
        await app.aclose()
    assert disp["status"] == "ok"
    assert disp["totals_match_search"] is True
    assert len(disp["periods"]) >= 5
    first = disp["periods"][0]
    assert first["corpus_units"] > 0
    assert first["per_million"] == round(first["hits"] / first["corpus_units"] * 1_000_000, 2)
