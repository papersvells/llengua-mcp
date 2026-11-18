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
async def test_sense_entrada_sugereix_la_fitxa() -> None:
    client = FakeClient((FIXTURES / "esadir_search.html").read_text(encoding="utf-8"))
    result = await EsadirAdapter(client).consulta("a gust")
    assert result["status"] == "ok"
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
async def test_seccio_invalida() -> None:
    with pytest.raises(InvalidQueryError, match="secció"):
        await EsadirAdapter(FakeClient("")).consulta("a gust", seccio="inventada")
