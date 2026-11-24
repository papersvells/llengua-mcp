from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.adapters.esadir import EsadirAdapter
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"

ENTRY_AND_FILM = """<html><body><div id="resultats">
<div>2 elements</div><div id="llista">
<table class="table"><tbody>
<tr><td class="divisor text element"><a href="/filmoteca/fitxa/node/El_gust">El gust</a></td>
<td class="divisor text seccio"><a href="/filmoteca">Filmoteca</a></td></tr>
<tr><td class="divisor text element"><a href="/entrades/fitxa/node/mala_fe">mala fe</a></td>
<td class="divisor text seccio"><a href="/entrades">Lèxic</a></td></tr>
</tbody></table></div></div></body></html>"""


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.urls.append(url)
        return HttpResult(text=self.html, status=200, url=url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html",
    [
        '<div id="resultats">5 elements</div>',
        "<html><body>Servei temporalment indisponible</body></html>",
    ],
    ids=["positive_count_without_rows", "no_count_or_rows"],
)
async def test_sense_files_llegibles_no_es_una_cerca_valida(html: str) -> None:
    result = await EsadirAdapter(FakeClient(html)).consulta("somriure")
    assert result["status"] == "unexpected_response"
    assert result["error"]["code"] == "unexpected_response"
    assert result["result_count"] is None
    assert result["returned"] == 0
    assert result["results"] == []
    assert result["has_more"] is False
    assert result["warnings"] == ["parse_partial"]
    assert "suggested_fitxa" not in result


@pytest.mark.asyncio
async def test_sense_entrada_sugereix_la_fitxa() -> None:
    client = FakeClient((FIXTURES / "esadir_search.html").read_text(encoding="utf-8"))
    result = await EsadirAdapter(client).consulta("a gust")
    assert result["status"] == "ok"
    assert result["returned"] == 3
    assert result["has_more"] is True
    assert "no_entry_results" in result["warnings"]
    assert result["suggested_fitxa"] == "a gust"
    assert "esadir_fitxa" in result["note"]


@pytest.mark.asyncio
async def test_les_entrades_van_primer() -> None:
    result = await EsadirAdapter(FakeClient(ENTRY_AND_FILM)).consulta("mala fe", limit=1)
    assert result["results"][0]["title"] == "mala fe"
    assert result["results"][0]["url"].endswith("/entrades/fitxa/node/mala_fe")
    assert "no_entry_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_cap_resultat_es_un_zero_verificat() -> None:
    client = FakeClient((FIXTURES / "esadir_zero.html").read_text(encoding="utf-8"))
    result = await EsadirAdapter(client).consulta("hidrosisme")
    assert result["status"] == "no_results"
    assert result["result_count"] == 0
    assert result["results"] == []
    assert result["has_more"] is False
    assert "zero_results" in result["warnings"]
    assert "no_entry_results" in result["warnings"]
    assert "parse_partial" not in result["warnings"]
    assert result["suggested_fitxa"] == "hidrosisme"
    assert "error" not in result


@pytest.mark.asyncio
async def test_seccio_invalida() -> None:
    with pytest.raises(InvalidQueryError, match="secció"):
        await EsadirAdapter(FakeClient("")).consulta("a gust", seccio="inventada")
