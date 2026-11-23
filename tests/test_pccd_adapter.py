from __future__ import annotations

import pytest

from llengua_mcp.adapters.pccd import PccdAdapter
from llengua_mcp.http import HttpResult
from llengua_mcp.parsers.pccd import parse_fitxa


class FakeClient:
    def __init__(self, html: str, status: int = 200) -> None:
        self.html = html
        self.status = status
        self.calls: list[tuple[str, dict]] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.calls.append((url, kwargs))
        return HttpResult(text=self.html, status=self.status, url=url)


@pytest.mark.asyncio
async def test_cerca_i_zero_verificat() -> None:
    client = FakeClient(
        "<main><h1>Cerca «fera»</h1><p>S'ha trobat 1 paremiotipus per a la cerca fera</p>"
        '<ol><li><a href="/p/Cuca_fera">Cuca fera</a></li></ol></main>'
    )
    result = await PccdAdapter(client).cerca("fera", inclou_variants=True)
    assert result["status"] == "ok"
    assert result["result_count"] == 1
    assert result["results"][0]["url"] == "https://pccd.dites.cat/p/Cuca_fera"
    assert client.calls[0][1]["params"]["variant"] == ""
    zero = FakeClient(
        "<main><h1>Cerca «invent»</h1>"
        "<p>No s'ha trobat cap resultat coincident amb invent.</p></main>"
    )
    result = await PccdAdapter(zero).cerca("invent")
    assert result["status"] == "no_results"
    assert result["result_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "html",
    [
        (
            "<main><h1>Cerca «ferament»</h1>"
            "<p>No s’ha trobat cap resultat coincident amb ferament.</p></main>"
        ),
        (
            "<main><h1>Cerca «fera»</h1>"
            "<p>No s’ha trobat cap resultat coincident amb ferament.</p></main>"
        ),
        "<main><h1>Cerca «fera»</h1><p>No s’ha trobat cap resultat coincident amb fera.</p>"
        '<ol><li><a href="/p/Cuca_fera">Cuca fera</a></li></ol></main>',
        "<main><h1>Cerca «fera»</h1><p>No s’ha trobat cap resultat coincident amb fera.</p>"
        "<p>S’ha trobat 1 paremiotipus per a la cerca fera.</p></main>",
    ],
)
async def test_cerca_no_certifica_zero_amb_eco_o_resultats_contradictoris(html: str) -> None:
    result = await PccdAdapter(FakeClient(html)).cerca("fera")
    assert result["status"] == "unexpected_response"
    assert result["result_count"] is None
    assert "zero_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_cerca_html_inesperat_no_es_zero() -> None:
    result = await PccdAdapter(FakeClient("<html><body>error</body></html>")).cerca("fera")
    assert result["status"] == "unexpected_response"
    assert result["result_count"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "separator",
    ["", " ", "\n", "<!-- comentari -->", "\n<!-- comentari -->\n"],
)
async def test_fitxa_extreu_variants_i_citacions(separator: str) -> None:
    html = (
        "<main><h1>Parèmia de prova</h1>"
        '<div class="description">3 recurrències en 2 variants. Primera citació: 1815.</div>'
        "<h2>Variant de prova</h2>"
        f"{separator}"
        "<details><summary>2 fonts, 1926.</summary>"
        '<div class="entry"><div class="footer">Autor (1926): Obra, p. 3.</div></div>'
        "</details></main>"
    )
    result = await PccdAdapter(FakeClient(html)).fitxa("Parèmia de prova")
    assert result["status"] == "ok"
    assert result["recurrence_count"] == 3
    assert result["variant_count"] == 2
    assert result["earliest_year"] == 1815
    assert result["variants"] == [
        {
            "variant": "Variant de prova",
            "source_count": 2,
            "earliest_year": 1926,
            "citations": ["Autor (1926): Obra, p. 3."],
        }
    ]


def test_fitxa_no_associa_details_amb_una_altra_variant() -> None:
    html = """<main>
      <h1>Parèmia de prova</h1>
      <div class="description">3 recurrències en 2 variants.</div>
      <h2>Primera variant</h2>
      <p>Contingut intermedi</p>
      <details><summary>2 fonts, 1926.</summary>
        <div class="entry"><div class="footer">Autor (1926): Obra, p. 3.</div></div>
      </details>
      <h2>Segona variant</h2>
      <!-- només s'associen els detalls adjacents a aquesta variant -->
      <details><summary>1 font, 1950.</summary>
        <div class="entry"><div class="footer">Autora (1950): Obra, p. 4.</div></div>
      </details>
    </main>"""
    result = parse_fitxa(html)
    assert result["variants"] == [
        {
            "variant": "Primera variant",
            "source_count": None,
            "earliest_year": None,
            "citations": [],
        },
        {
            "variant": "Segona variant",
            "source_count": 1,
            "earliest_year": 1950,
            "citations": ["Autora (1950): Obra, p. 4."],
        },
    ]


@pytest.mark.asyncio
async def test_fitxa_accepta_url_de_la_pccd() -> None:
    client = FakeClient('<main><h1>Prova</h1><div class="description">1 recurrència.</div></main>')
    result = await PccdAdapter(client).fitxa("https://pccd.dites.cat/p/Prova")
    assert result["status"] == "ok"
    assert client.calls[0][0] == "https://pccd.dites.cat/p/Prova"
    assert result["variants"][0]["source_count"] is None
