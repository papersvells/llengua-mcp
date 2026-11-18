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
    assert disp["data_valid"] is True
    assert disp["unvalidated"] is None
    assert disp["totals_match_search"] is True
    assert len(disp["periods"]) >= 5
    first = disp["periods"][0]
    assert first["corpus_units"] > 0
    assert first["per_million"] == round(first["hits"] / first["corpus_units"] * 1_000_000, 2)


@pytest.mark.asyncio
async def test_live_dispersio_duna_sola_pagina() -> None:
    app = App(Settings.from_env())
    try:
        start = await app.ctilc.search_phrase("somriure maliciós", limit=50)
        variant = start["variants"][0]
        assert variant["total"] < 50
        assert variant["has_more"] is False
        assert variant["next_cursor"] is None
        assert variant["search_cursor"]
        disp = await app.ctilc.dispersio_cronologica(variant["search_cursor"])
    finally:
        await app.aclose()
    assert disp["status"] == "ok"
    assert disp["data_valid"] is True
    assert disp["search_total"] == variant["total"]
    assert disp["periods"]


@pytest.mark.asyncio
async def test_live_oiec() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.oiec.cerca("apostrofa")
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["hits"]
    codis = [hit["codi_text"] for hit in result["hits"]]
    assert any(codi and codi.startswith("4.") for codi in codis)


@pytest.mark.asyncio
async def test_live_gramatiques() -> None:
    app = App(Settings.from_env())
    try:
        gbu = await app.gramatiques.cerca("perífrasi verbal", font="gbu")
        giec = await app.gramatiques.cerca("haver de", font="giec")
        text = await app.gramatiques.text("28.1", font="gbu")
    finally:
        await app.aclose()
    assert gbu["status"] == "ok" and gbu["hits"]
    assert giec["status"] == "ok" and giec["hits"]
    assert text["status"] == "ok" and "perífrasi" in text["content"].lower()


@pytest.mark.asyncio
async def test_live_collocacions() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.ctilc.collocacions("somriure", limit=3)
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["lema_echo_verified"] is True
    assert result["total"] > 0
    categories = {cat["categoria"] for cat in result["categories"]}
    assert "nom" in categories
    names = next(cat for cat in result["categories"] if cat["categoria"] == "nom")
    assert names["items"]
    assert all(item["freq"] >= 5 for item in names["items"])
