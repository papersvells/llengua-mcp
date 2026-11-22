from __future__ import annotations

import pytest

from llengua_mcp.adapters.oiec import OiecAdapter
from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpResult

SEARCH_PAYLOAD = (
    "["
    '{"idText": 1, "codiText": "4.2.1", "titol": "Formació de contraccions",'
    ' "contingut": "<p>Les preposicions <em>a</em> i <em>de</em> formen les '
    'contraccions <em>al</em> i <em>del</em>.</p>"},'
    '{"idText": 2, "codiText": "4.1.2b", "titol": "Casos particulars",'
    ' "contingut": "<p>No s’apostrofa davant i o u.</p>"}'
    "]"
)

TEXT_PAYLOAD = """{
  "codiText": "4.1.2b", "titolText": "Casos particulars en l’ús de l’apòstrof",
  "contingut": "<p>No s’apostrofa <em>davant</em> i o u amb valor semivocàlic.</p>",
  "codiAnterior": "4.1.2a", "codiSeguent": "4.1.3"
}"""


class FakeClient:
    def __init__(self, body: str) -> None:
        self.body = body
        self.urls: list[str] = []

    async def get_text(self, url: str, *, params=None, **kwargs) -> HttpResult:
        import httpx

        if params:
            request = httpx.Request("GET", url, params=params)
            url = str(request.url)
        self.urls.append(url)
        return HttpResult(text=self.body, status=200, url=url)


@pytest.mark.asyncio
async def test_cerca_builds_the_right_request() -> None:
    client = FakeClient(SEARCH_PAYLOAD)
    adapter = OiecAdapter(client)
    result = await adapter.cerca("apostrofa")
    assert result["status"] == "ok"
    assert result["returned"] == 2
    url = client.urls[0]
    assert "/TextOrtografia/cerca/" in url
    assert "En%20qualsevol%20posici%C3%B3" in url
    assert "paraula=apostrofa" in url


@pytest.mark.asyncio
async def test_cerca_exact_uses_the_other_mode() -> None:
    client = FakeClient(SEARCH_PAYLOAD)
    adapter = OiecAdapter(client)
    await adapter.cerca("apòstrof", coincidencia="exact")
    assert "Coincident" in client.urls[0]


@pytest.mark.asyncio
async def test_cerca_empty_results() -> None:
    client = FakeClient("[]")
    adapter = OiecAdapter(client)
    result = await adapter.cerca("zzzzinexistent")
    assert result["status"] == "no_results"
    assert "no_readable_sections" in result["warnings"] or result["returned"] == 0


@pytest.mark.asyncio
async def test_cerca_nomes_amb_titols_es_partial() -> None:
    client = FakeClient('[{"codiText": "4", "titol": "L’apòstrof", "contingut": null}]')
    adapter = OiecAdapter(client)
    result = await adapter.cerca("apòstrof")

    assert result["status"] == "partial"
    assert result["total_hits"] == 1
    assert result["hits"] == []
    assert "no_readable_sections" in result["warnings"]


@pytest.mark.asyncio
async def test_cerca_rejects_bad_mode_and_empty_query() -> None:
    adapter = OiecAdapter(FakeClient("[]"))
    with pytest.raises(InvalidQueryError, match="coincidència"):
        await adapter.cerca("apòstrof", coincidencia="wtf")
    with pytest.raises(InvalidQueryError, match="buida"):
        await adapter.cerca("   ")


@pytest.mark.asyncio
async def test_text_returns_clean_content() -> None:
    client = FakeClient(TEXT_PAYLOAD)
    adapter = OiecAdapter(client)
    result = await adapter.text("4.1.2b")
    assert result["status"] == "ok"
    assert result["codi_text"] == "4.1.2b"
    assert "<em>" not in result["content"]
    assert result["prev"] == "4.1.2a"
    assert "/TextOrtografia/4.1.2b" in client.urls[0]


@pytest.mark.asyncio
async def test_text_rejects_bad_codes() -> None:
    adapter = OiecAdapter(FakeClient("{}"))
    with pytest.raises(InvalidQueryError):
        await adapter.text("")
    with pytest.raises(InvalidQueryError):
        await adapter.text("4/1; DROP TABLE")


@pytest.mark.asyncio
async def test_text_rebutja_un_altre_codi() -> None:
    adapter = OiecAdapter(FakeClient(TEXT_PAYLOAD))
    with pytest.raises(UnexpectedResponseError, match="no correspon"):
        await adapter.text("4.1.2a")
