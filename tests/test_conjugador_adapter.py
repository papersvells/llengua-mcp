from __future__ import annotations

import pytest

from llengua_mcp.adapters.conjugador import ConjugadorAdapter
from llengua_mcp.errors import InvalidQueryError, UpstreamError
from llengua_mcp.http import HttpResult


class FakeClient:
    def __init__(self, html: str = "", *, error: Exception | None = None) -> None:
        self.html = html
        self.error = error
        self.urls: list[str] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.urls.append(url)
        if self.error:
            raise self.error
        return HttpResult(text=self.html, status=200, url=url)


SAMPLE = """<main><div class="diccionari-resultat" id="conjugador-verb-caixa">
<h3>cantar</h3>
<div id="indicatiu" class="result-conjugador"><h4>Mode indicatiu</h4>
<div class="panel"><div class="panel-heading">Present</div><table>
<tr><td>canto<span class="variant"> (cent.)</span>,
cante<span class="variant"> (val.)</span>,
cant<span class="variant"> (bal.)</span></td></tr>
<tr><td>vas (vares)</td></tr><tr><td>canta</td></tr><tr><td>cantem</td></tr>
<tr><td>canteu</td></tr><tr><td>canten</td></tr></table></div></div>
<div id="imperatiu" class="result-conjugador"><h4>Mode imperatiu</h4>
<div class="panel"><div class="panel-heading">Present</div><table>
<tr><td>&nbsp;</td></tr><tr><td>canta</td></tr><tr><td>canti</td></tr>
<tr><td>cantem</td></tr><tr><td>canteu</td></tr><tr><td>cantin</td></tr>
</table></div></div>
<div id="nopersonals" class="result-conjugador"><h4>Formes no personals</h4>
<table><tr><th>Infinitiu</th><td>cantar</td></tr>
<tr><th>Gerundi</th><td>cantant</td></tr></table></div>
</div></main>"""


@pytest.mark.asyncio
async def test_consulta_reté_variants_i_filtra_persona() -> None:
    client = FakeClient(SAMPLE)
    result = await ConjugadorAdapter(client).consulta(
        "cantar", mode="indicatiu", temps="present", persona="jo"
    )
    assert result["status"] == "ok"
    assert result["sections"][0]["rows"][0]["persons"] == [
        {
            "key": "singular1",
            "subject": "jo",
            "status": "available",
            "forms": [
                {"form": "canto", "variety": "cent."},
                {"form": "cante", "variety": "val."},
                {"form": "cant", "variety": "bal."},
            ],
        }
    ]
    assert client.urls[0].endswith("/verb/cantar/")


@pytest.mark.asyncio
async def test_irregular_imperatiu_no_aplicable_i_formes_no_personals() -> None:
    result = await ConjugadorAdapter(FakeClient(SAMPLE)).consulta(
        "cantar", mode="imperatiu", persona="1sg"
    )
    person = result["sections"][0]["rows"][0]["persons"][0]
    assert person["status"] == "not_applicable"
    assert person["forms"] == []
    non_personals = await ConjugadorAdapter(FakeClient(SAMPLE)).consulta(
        "cantar", mode="formes no personals"
    )
    assert [row["tense"] for row in non_personals["sections"][0]["rows"]] == [
        "Infinitiu",
        "Gerundi",
    ]
    tu_form = await ConjugadorAdapter(FakeClient(SAMPLE)).consulta(
        "cantar", mode="indicatiu", temps="Present", persona="tu"
    )
    assert tu_form["sections"][0]["rows"][0]["persons"][0]["forms"] == [
        {"form": "vas (vares)", "variety": ""}
    ]


@pytest.mark.asyncio
async def test_pronominal_es_resol_a_la_fitxa_base() -> None:
    client = FakeClient(SAMPLE.replace("<h3>cantar</h3>", "<h3>cantar-se</h3>"))
    result = await ConjugadorAdapter(client).consulta("cantar-se")
    assert result["status"] == "ok"
    assert client.urls[0].endswith("/verb/cantar/")


@pytest.mark.asyncio
async def test_no_trobat_i_resposta_inesperada_no_es_confonen() -> None:
    missing = await ConjugadorAdapter(
        FakeClient("<main><h1>No s'ha trobat la pàgina</h1></main>")
    ).consulta("inventar")
    assert missing["status"] == "no_results"
    unexpected = await ConjugadorAdapter(FakeClient("<html><body>Error</body></html>")).consulta(
        "inventar"
    )
    assert unexpected["status"] == "unexpected_response"


@pytest.mark.asyncio
async def test_http_404_es_un_verb_no_trobat_pero_altres_errors_pugen() -> None:
    missing = await ConjugadorAdapter(
        FakeClient(error=UpstreamError("El recurs no existeix (HTTP 404)."))
    ).consulta("inventar")
    assert missing["status"] == "no_results"
    with pytest.raises(UpstreamError):
        await ConjugadorAdapter(
            FakeClient(error=UpstreamError("El servei ha retornat HTTP 503."))
        ).consulta("inventar")


@pytest.mark.asyncio
async def test_filtre_invalid() -> None:
    with pytest.raises(InvalidQueryError):
        await ConjugadorAdapter(FakeClient(SAMPLE)).consulta("cantar", mode="futur")
