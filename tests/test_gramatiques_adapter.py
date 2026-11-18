from __future__ import annotations

import pytest

from llengua_mcp.adapters.gramatiques import GramatiquesAdapter
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult

GBU_SEARCH = (
    '[{"idtext": 1, "codiText": "28.1", "titol": "Les perífrasis verbals: '
    'constituents", "contingut": "<p>Una <em>perífrasi</em> verbal és una forma '
    'complexa constituïda per dos verbs.</p>"}]'
)
GIEC_SEARCH = (
    '{"texts": [{"idText": 2, "titol": "La posició dels pronoms febles", '
    '"codiText": "8.3.3", "contingut": "<p>Els <em>pronoms</em> febles poden '
    'anar abans o després del verb.</p>"}]}'
)
TEXT_BY_CODY = (
    '{"codiText": "28.1", "titolText": "Les perífrasis verbals", '
    '"contingut": "<p>Una <em>perífrasi</em> verbal és una forma complexa '
    'constituïda per dos verbs, enllaçats per una preposició.</p>"}'
)


class FakeClient:
    def __init__(self, body: str) -> None:
        self.body = body
        self.urls: list[str] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.urls.append(url)
        return HttpResult(text=self.body, status=200, url=url)


@pytest.mark.asyncio
async def test_cerca_gbu() -> None:
    client = FakeClient(GBU_SEARCH)
    adapter = GramatiquesAdapter(client)
    result = await adapter.cerca("perífrasi", font="gbu")
    assert result["status"] == "ok"
    assert result["total_hits"] == 1
    assert result["hits"][0]["codi_text"] == "28.1"
    assert "<em>" not in result["hits"][0]["snippet"]
    assert "/search_text?" in client.urls[0]
    assert "En+qualsevol+posi" in client.urls[0]


@pytest.mark.asyncio
async def test_cerca_giec_uses_the_oiec_pattern() -> None:
    client = FakeClient(GIEC_SEARCH)
    adapter = GramatiquesAdapter(client)
    result = await adapter.cerca("pronoms", font="giec")
    assert result["status"] == "ok"
    assert result["hits"][0]["codi_text"] == "8.3.3"
    assert "/TextGramatica/cercadic/" in client.urls[0]
    assert "paraula=pronoms" in client.urls[0]


@pytest.mark.asyncio
async def test_cerca_geiec() -> None:
    client = FakeClient(GBU_SEARCH)
    adapter = GramatiquesAdapter(client)
    result = await adapter.cerca("perífrasi", font="geiec")
    assert result["status"] == "ok"
    assert "api-geiec.iec.cat" in client.urls[0]


@pytest.mark.asyncio
async def test_cerca_no_results() -> None:
    client = FakeClient("[]")
    adapter = GramatiquesAdapter(client)
    result = await adapter.cerca("zzzzinexistent")
    assert result["status"] == "no_results"
    assert result["hits"] == []


@pytest.mark.asyncio
async def test_cerca_validations() -> None:
    adapter = GramatiquesAdapter(FakeClient("[]"))
    with pytest.raises(InvalidQueryError, match="font"):
        await adapter.cerca("perífrasi", font="wtf")
    with pytest.raises(InvalidQueryError, match="coincidència"):
        await adapter.cerca("perífrasi", coincidencia="wtf")
    with pytest.raises(InvalidQueryError, match="buida"):
        await adapter.cerca("   ")


@pytest.mark.asyncio
async def test_text_gbu() -> None:
    client = FakeClient(TEXT_BY_CODY)
    adapter = GramatiquesAdapter(client)
    result = await adapter.text("28.1", font="gbu")
    assert result["status"] == "ok"
    assert result["codi_text"] == "28.1"
    assert "<em>" not in result["content"]
    assert "text_by_cody" in client.urls[0]


@pytest.mark.asyncio
async def test_text_giec_uses_the_plain_endpoint() -> None:
    client = FakeClient(TEXT_BY_CODY)
    adapter = GramatiquesAdapter(client)
    result = await adapter.text("8.3.3", font="giec")
    assert result["status"] == "ok"
    assert "/TextGramatica/8.3.3" in client.urls[0]
    assert "text_by_cody" not in client.urls[0]


@pytest.mark.asyncio
async def test_text_rejects_bad_codes() -> None:
    adapter = GramatiquesAdapter(FakeClient("{}"))
    with pytest.raises(InvalidQueryError):
        await adapter.text("")
    with pytest.raises(InvalidQueryError):
        await adapter.text("1/2; DROP")
