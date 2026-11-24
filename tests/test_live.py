from __future__ import annotations

import os

import pytest

from llengua_mcp.app import App
from llengua_mcp.config import Settings
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.models import CtilcFilters, PatternElement

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
async def test_live_filtres_ctilc() -> None:
    elements = [
        PatternElement(type="lema", value="somriure"),
        PatternElement(type="cg", category="adj"),
    ]
    app = App(Settings.from_env())
    try:
        base = await app.ctilc.search_pattern(elements, limit=1)
        central = await app.ctilc.search_pattern(
            elements, limit=1, filters=CtilcFilters(varietat=["central"])
        )
        values = await app.ctilc.filtres_disponibles(base["search_cursor"], tipus="autors", limit=3)
    finally:
        await app.aclose()
    assert base["status"] == "ok"
    assert central["status"] == "ok"
    assert central["total"] < base["total"]
    assert central["filters_verified"] is True
    assert central["total_unfiltered"] == base["total"]
    assert values["status"] == "ok"
    assert values["values"]


@pytest.mark.asyncio
@pytest.mark.parametrize("varietat", [None, "central"])
async def test_live_continuar_cerca_ctilc(varietat: str | None) -> None:
    elements = [
        PatternElement(type="lema", value="somriure"),
        PatternElement(type="cg", category="adj"),
    ]
    filters = CtilcFilters(varietat=[varietat]) if varietat else None
    app = App(Settings.from_env())
    try:
        first = await app.ctilc.search_pattern(elements, limit=3, filters=filters)
        assert first["status"] == "ok"
        assert first["next_cursor"]
        second = await app.ctilc.continue_search(first["next_cursor"], limit=2)
    finally:
        await app.aclose()
    assert second["status"] == "ok"
    assert second["query"]["start"] == 4
    assert second["total"] == first["total"]
    assert first["returned"] == 3 and second["returned"] == 2
    first_ids = {row["occurrence_id"] for row in first["occurrences"]}
    second_ids = {row["occurrence_id"] for row in second["occurrences"]}
    assert None not in first_ids | second_ids
    assert first_ids.isdisjoint(second_ids)
    if filters:
        assert second["filters_verified"] is True


@pytest.mark.asyncio
async def test_live_consultes() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.consultes.cerca("tenir", limit=2)
        tema = await app.consultes.cerca(tema="Sintaxi", limit=1)
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["total"] > 0
    assert result["results"]
    assert result["available_themes"]
    assert result["results"][0]["pregunta"]
    assert tema["status"] == "ok"
    assert tema["total"] > 0


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
async def test_live_dispersio_dialectal() -> None:
    app = App(Settings.from_env())
    try:
        start = await app.ctilc.search_pattern(
            [
                PatternElement(type="lema", value="somriure"),
                PatternElement(type="cg", category="adj"),
            ],
            limit=1,
        )
        disp = await app.ctilc.dispersio_dialectal(start["search_cursor"])
    finally:
        await app.aclose()
    assert disp["status"] == "ok"
    assert disp["data_valid"] is True
    assert disp["unvalidated"] is None
    assert disp["totals"]["query_hits"] == disp["search_total"]
    assert len(disp["varieties"]) == 6
    assert disp["totals"]["corpus_hits"] > 0
    assert all(item["query_hits"] >= 0 for item in disp["varieties"])


@pytest.mark.asyncio
async def test_live_cerca_forma_i_lema() -> None:
    app = App(Settings.from_env())
    try:
        forma = await app.ctilc.cerca_forma("somriu", limit=2)
        lema = await app.ctilc.cerca_lema("somriure", limit=2)
    finally:
        await app.aclose()
    assert forma["status"] == "ok"
    assert forma["total"] > 0
    assert forma["returned"] == 2
    assert forma["forms"]
    assert forma["occurrences"][0]["occurrence_id"]
    assert forma["echo_verified"] is True
    assert lema["status"] == "ok"
    assert lema["total"] > 0
    assert lema["returned"] == 2
    assert lema["forms"]
    assert lema["echo_verified"] is True


@pytest.mark.asyncio
async def test_live_cerca_basica_negativa() -> None:
    app = App(Settings.from_env())
    try:
        forma = await app.ctilc.cerca_forma("ah", mode="no comença per", cg="I", limit=2)
        lema = await app.ctilc.cerca_lema("ah", mode="no conté", cg="I", limit=2)
    finally:
        await app.aclose()
    for result in (forma, lema):
        assert result["status"] == "ok"
        assert result["echo_verified"] is True
        assert result["total"] > 0
        assert result["returned"] == 2


@pytest.mark.asyncio
async def test_live_dispersio_general() -> None:
    app = App(Settings.from_env())
    try:
        start = await app.ctilc.search_pattern(
            [
                PatternElement(type="lema", value="somriure"),
                PatternElement(type="cg", category="adj"),
            ],
            limit=1,
        )
        disp = await app.ctilc.dispersio_general(start["search_cursor"])
    finally:
        await app.aclose()
    assert disp["status"] == "ok"
    assert disp["data_valid"] is True
    assert disp["unvalidated"] is None
    assert disp["totals"]["query_hits"] == disp["search_total"]
    assert set(disp["attributes"]) == {
        "any",
        "varietat",
        "traduccio",
        "tipus",
        "genere",
        "classificacio",
    }
    assert len(disp["attributes"]["any"]["groups"]) == 10
    assert disp["attributes"]["tipus"]["totals"]["query_hits"] == disp["search_total"]


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
async def test_live_obres() -> None:
    app = App(Settings.from_env())
    try:
        author = await app.ctilc.obres(autor="Sagarra, Xavier")
        title = await app.ctilc.obres(titol="vida", limit=2)
    finally:
        await app.aclose()
    assert author["status"] == "ok"
    assert author["works"]
    assert author["echo_verified"] is True
    assert title["status"] == "ok"
    assert title["total"] > 2
    assert title["returned"] == 2
    assert title["echo_verified"] is True


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


@pytest.mark.asyncio
async def test_live_collocacions_forma() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.ctilc.collocacions_forma("somriures", limit=3)
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    assert result["forma_echo_verified"] is True
    assert result["total"] > 0
    names = next(cat for cat in result["categories"] if cat["categoria"] == "adjectiu")
    assert names["items"]
    assert all("info_mutua" in item for item in names["items"])


@pytest.mark.asyncio
async def test_live_optimot() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.optimot.cerca("tenir que", mode="frase_exacta", limit=5)
        assert result["status"] == "ok"
        candidate = next(item for item in result["results"] if "Teniu que" in item["title"])
        fitxa = await app.optimot.fitxa(candidate["detail_ref"])
    finally:
        await app.aclose()
    assert fitxa["status"] == "ok"
    assert "Teniu que" in fitxa["title"]
    text = " ".join(
        paragraph for section in fitxa["sections"] for paragraph in section["paragraphs"]
    )
    assert "haver de" in text.lower()


@pytest.mark.asyncio
async def test_live_diec() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.diec.consulta("maliciós", max_senses=10)
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    entry = result["entries"][0]
    assert entry["entry"] == "maliciós"
    assert entry["senses"]
    examples = [example for sense in entry["senses"] for example in sense["examples"]]
    assert any("somriure" in example.lower() for example in examples)


@pytest.mark.asyncio
async def test_live_esadir() -> None:
    app = App(Settings.from_env())
    try:
        search = await app.esadir.consulta("a gust", limit=3)
        fitxa = await app.esadir.fitxa("a gust")
    finally:
        await app.aclose()
    assert search["status"] == "ok"
    assert search["results"]
    assert "no_entry_results" in search["warnings"]
    assert search["suggested_fitxa"] == "a gust"
    assert fitxa["status"] == "ok"
    assert fitxa["definitions"] or fitxa["examples"]


@pytest.mark.asyncio
async def test_live_jane() -> None:
    app = App(Settings.from_env())
    try:
        result = await app.jane.cerca("maliciós")
        general = await app.jane.cerca("mala fe", mode="general")
        zero = await app.jane.cerca("zzzqqqxyz")
    finally:
        await app.aclose()
    assert result["status"] == "ok"
    entry = result["results"][0]
    assert entry["lema"] == "maliciós"
    assert [sense["num"] for sense in entry["sentits"]] == [1, 2]
    assert general["status"] == "ok"
    assert any(
        "mala fe" in sense["sinonims"] for item in general["results"] for sense in item["sentits"]
    )
    assert zero["status"] == "no_results"


@pytest.mark.asyncio
async def test_live_filtres_classtem_i_autor() -> None:
    elements = [
        PatternElement(type="lema", value="somriure"),
        PatternElement(type="cg", category="adj"),
    ]
    app = App(Settings.from_env())
    try:
        theme = await app.ctilc.search_pattern(
            elements, limit=1, filters=CtilcFilters(classtem=["3.2"])
        )
        themes = await app.ctilc.filtres_disponibles(theme["search_cursor"], tipus="temes", limit=3)
        author_hits = await app.ctilc.search_pattern(
            elements, limit=1, filters=CtilcFilters(autor=["Sagarra, Josep M. de"])
        )
        author_empty = await app.ctilc.search_pattern(
            elements, limit=1, filters=CtilcFilters(autor=["Sagarra, Xavier"])
        )
        with pytest.raises(InvalidQueryError):
            await app.ctilc.search_pattern(
                elements, limit=1, filters=CtilcFilters(autor=["Inventat, Pere"])
            )
    finally:
        await app.aclose()
    assert theme["status"] == "ok"
    assert theme["total"] and theme["total"] > 0
    assert theme["filters_verified"] is True
    assert themes["status"] == "ok"
    assert themes["values"]
    assert author_hits["status"] == "ok"
    assert author_hits["total"] and author_hits["total"] > 0
    assert author_empty["status"] == "no_matches"
    assert author_empty["total"] == 0
    assert "filtered_empty_verified" in author_empty["warnings"]
