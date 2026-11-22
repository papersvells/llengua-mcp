from __future__ import annotations

import re
from pathlib import Path

import pytest

from llengua_mcp.adapters.ctilc import CtilcAdapter
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import InvalidQueryError, UpstreamError
from llengua_mcp.http import HttpResult
from llengua_mcp.models import CtilcFilters, PatternElement

FIXTURES = Path(__file__).parent / "fixtures"
BASE = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
AUTHORS = (FIXTURES / "obres_autors.html").read_text(encoding="utf-8")
TEMES = (FIXTURES / "ctilc_filtres_temes.html").read_text(encoding="utf-8")

ELEMENTS = [
    PatternElement(type="lema", value="somriure"),
    PatternElement(type="cg", category="adj"),
]


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


def _page(
    *,
    filtered: int = 4,
    unfiltered: int = 2136,
    echo: str | None = None,
    group: str | None = None,
    autor: str | None = None,
    with_rows: bool = True,
) -> str:
    html = BASE.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3",
        f"Freqüència total</b>:&nbsp;&nbsp;{unfiltered}",
    )
    label = "classificació temàtica" if (echo or group) else "autor"
    filter_table = (
        '<center><table class="tableFILTREStop"><tr><td width="75%">'
        f"<b>Filtre per {label}</b>: filtre</td>"
        f"<td><b>Quantitat filtrada</b>:&nbsp;&nbsp;{filtered}</td>"
        "</tr></table></center>"
    )
    html = html.replace(
        '</div>\n<div id="cHTML2">',
        filter_table + '</div>\n<div id="cHTML2">',
    )
    hidden = ""
    if echo:
        hidden += f'<input type="hidden" name="classtemSelec" value="{echo}" />'
    if group:
        hidden += f'<input type="hidden" name="classtemGSelec" value="{group}" />'
    if autor:
        hidden += f'<input type="hidden" name="autSelec" value="{autor}" />'
    html = html.replace("</body>", hidden + "</body>")
    if not with_rows:
        html = re.sub(r'<div id="cHTML2">.*?</div>', "", html, flags=re.DOTALL)
    return html


def _phrase_page(
    *,
    autor: str,
    filtered: int,
    with_rows: bool = False,
) -> str:
    """Adapta la fixture de dos elements a la frase `somriure maliciós`."""

    html = _page(autor=autor, filtered=filtered, with_rows=with_rows)
    html = html.replace(">adj:-</span>", ">maliciós</span>")
    html = html.replace("00*lema=somriure", "00*forma=somriure")
    html = html.replace("01*cg=adj%3A-", "01*forma=malici%C3%B3s")
    return html


class SearchClient:
    """Respon la cerca i el catàleg d'autors (Aut1) amb fixtures."""

    def __init__(
        self,
        html: str,
        *,
        authors: str = AUTHORS,
        fail_authors: bool = False,
        list_html: str | None = None,
    ) -> None:
        self.html = html
        self.authors = authors
        self.fail_authors = fail_authors
        self.list_html = list_html
        self.bodies: list[str] = []
        self.urls: list[str] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.bodies.append(body)
        self.urls.append(url)
        if "CTILCCorpus_Aut1" in url:
            if self.fail_authors:
                raise UpstreamError("No s'ha pogut connectar amb el catàleg.")
            return HttpResult(text=self.authors, status=200, url=url)
        if self.list_html is not None and "FiltObra_filtres" in url:
            return HttpResult(text=self.list_html, status=200, url=url)
        return HttpResult(text=self.html, status=200, url=url)

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


@pytest.mark.asyncio
async def test_classtem_subtema_construeix_i_valida(tmp_path) -> None:
    client = SearchClient(_page(filtered=4, echo="@3.2"))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(classtem=["3.2"]))

    assert result["status"] == "ok"
    assert result["total"] == 4
    assert result["total_unfiltered"] == 2136
    assert result["filters_verified"] is True
    assert result["query"]["filters"]["classtem"] == ["3.2"]
    assert "classtemSelec=%403.2" in client.bodies[0]


@pytest.mark.asyncio
async def test_classtem_grups_sencers(tmp_path) -> None:
    client = SearchClient(_page(filtered=45, group="@3@1"))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(classtem=["3", "1"]))

    assert result["status"] == "ok"
    assert result["filters_verified"] is True
    assert "classtemGSelec=%403%401" in client.bodies[0]
    assert result["query"]["filters"]["classtem"] == ["3", "1"]


@pytest.mark.asyncio
async def test_classtem_rebutja_dos_subtemes(tmp_path) -> None:
    adapter = CtilcAdapter(SearchClient(_page()), _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="subtema"):
        await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(classtem=["3.2", "3.3"]))


@pytest.mark.asyncio
async def test_classtem_rebutja_codi_invalid(tmp_path) -> None:
    adapter = CtilcAdapter(SearchClient(_page()), _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="no és vàlid"):
        await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(classtem=["3.22"]))


@pytest.mark.asyncio
async def test_classtem_i_genere_son_excloents(tmp_path) -> None:
    adapter = CtilcAdapter(SearchClient(_page()), _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="excloents"):
        await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(genere=["N"], classtem=["3.2"]))


@pytest.mark.asyncio
async def test_classtem_amb_tipus_lit_es_invalid(tmp_path) -> None:
    adapter = CtilcAdapter(SearchClient(_page()), _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="LIT"):
        await adapter.search_pattern(
            ELEMENTS, filters=CtilcFilters(tipus=["LIT"], classtem=["3.2"])
        )


@pytest.mark.asyncio
async def test_filtres_disponibles_temes(tmp_path) -> None:
    client = SearchClient(_page(), list_html=TEMES)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(ELEMENTS, limit=2)

    result = await adapter.filtres_disponibles(start["search_cursor"], tipus="temes", limit=100)

    assert result["status"] == "ok"
    assert "filt=lang" in client.bodies[-1]
    assert result["values"][0] == {
        "value": "0.0",
        "label": "Correspondència",
        "count": 3,
    }
    codes = {value["value"] for value in result["values"]}
    assert "3.2" in codes


@pytest.mark.asyncio
async def test_autor_inexistent_es_rebutja_abans_de_filtrar(tmp_path) -> None:
    client = SearchClient(_page(autor="@Inventat, Pere", filtered=1, with_rows=False))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="catàleg"):
        await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Inventat, Pere"]))


@pytest.mark.asyncio
async def test_autor_valid_sense_files_es_zero_verificat(tmp_path) -> None:
    client = SearchClient(_page(autor="@Sagarra, Xavier", filtered=1, with_rows=False))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert result["total_unfiltered"] == 2136
    assert result["filters_verified"] is True
    assert "filtered_empty_verified" in result["warnings"]
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_autor_no_validat_no_bloqueja_la_cerca(tmp_path) -> None:
    client = SearchClient(
        _page(autor="@Sagarra, Xavier", filtered=1237),
        fail_authors=True,
    )
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "ok"
    assert "author_validation_skipped" in result["warnings"]


MAINTENANCE = "<html><body><h1>Servei temporalment indisponible</h1></body></html>"


@pytest.mark.asyncio
async def test_cataleg_illegible_no_invalida_l_autor(tmp_path) -> None:
    client = SearchClient(
        _page(autor="@Sagarra, Xavier", filtered=42),
        authors=MAINTENANCE,
    )
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "ok"
    assert result["total"] == 42
    assert "author_validation_skipped" in result["warnings"]


@pytest.mark.asyncio
async def test_cataleg_illegible_i_total_1_no_es_verificat(tmp_path) -> None:
    client = SearchClient(
        _page(autor="@Sagarra, Xavier", filtered=1, with_rows=False),
        authors=MAINTENANCE,
    )
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "unexpected_response"
    assert "author_validation_skipped" in result["warnings"]
    assert "filtered_empty_unverified" in result["warnings"]
    assert "filtered_empty_verified" not in result["warnings"]


@pytest.mark.asyncio
async def test_filtrat_42_sense_files_no_es_un_fals_zero(tmp_path) -> None:
    client = SearchClient(_page(autor="@Sagarra, Xavier", filtered=42, with_rows=False))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "unexpected_response"
    assert result["total"] == 42
    assert result["total_unfiltered"] == 2136
    assert result["filters_verified"] is True
    assert "filtered_empty_unverified" in result["warnings"]
    assert "filtered_empty_verified" not in result["warnings"]
    assert result["error"]["code"] == "unexpected_response"


@pytest.mark.asyncio
async def test_autor_no_validat_i_total_sense_files_es_unexpected(tmp_path) -> None:
    client = SearchClient(
        _page(autor="@Sagarra, Xavier", filtered=42, with_rows=False),
        fail_authors=True,
    )
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_pattern(ELEMENTS, filters=CtilcFilters(autor=["Sagarra, Xavier"]))

    assert result["status"] == "unexpected_response"
    assert result["total"] == 42
    assert "author_validation_skipped" in result["warnings"]
    assert "filtered_empty_unverified" in result["warnings"]


@pytest.mark.asyncio
async def test_cerca_frase_autor_inexistent_es_invalid_query(tmp_path) -> None:
    client = SearchClient(_page(autor="@Inventat, Pere", filtered=1, with_rows=False))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    with pytest.raises(InvalidQueryError, match="catàleg"):
        await adapter.search_phrase(
            "somriure maliciós", filters=CtilcFilters(autor=["Inventat, Pere"])
        )

    assert any("CTILCCorpus_Aut1" in url for url in client.urls)
    assert not any("CTILCQConc_Coocur2" in url for url in client.urls)


@pytest.mark.asyncio
async def test_cerca_frase_autor_valid_i_zero_verificat(tmp_path) -> None:
    client = SearchClient(_phrase_page(autor="@Sagarra, Xavier", filtered=1))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_phrase(
        "somriure maliciós", filters=CtilcFilters(autor=["Sagarra, Xavier"])
    )

    assert result["status"] == "no_matches"
    variant = result["variants"][0]
    assert variant["status"] == "no_matches"
    assert variant["total"] == 0
    assert "filtered_empty_verified" in variant["warnings"]
    assert any("CTILCCorpus_Aut1" in url for url in client.urls)
    assert any("autSelec=%40Sagarra%2C%20Xavier" in body for body in client.bodies)


@pytest.mark.asyncio
async def test_cerca_frase_cataleg_indisponible_avisa(tmp_path) -> None:
    client = SearchClient(
        _phrase_page(autor="@Sagarra, Xavier", filtered=32, with_rows=True),
        fail_authors=True,
    )
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())

    result = await adapter.search_phrase(
        "somriure maliciós", filters=CtilcFilters(autor=["Sagarra, Xavier"])
    )

    assert result["status"] == "ok"
    assert "author_validation_skipped" in result["variants"][0]["warnings"]
