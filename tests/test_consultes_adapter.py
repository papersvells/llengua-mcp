from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from llengua_mcp.adapters.consultes import ConsultesAdapter
from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = (FIXTURES / "consultes_page.html").read_text(encoding="utf-8")
ROWS = json.loads((FIXTURES / "consultes_rows.json").read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, payload: dict, *, page: str = PAGE, fail_first: bool = False) -> None:
        self.page = page
        self.payload = payload
        self.fail_first = fail_first
        self.bodies: list[str] = []
        self.urls: list[str] = []
        self.gets = 0

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.gets += 1
        return HttpResult(text=self.page, status=200, url=url)

    async def post_json(self, url: str, body: str, **kwargs):
        self.urls.append(url)
        self.bodies.append(body)
        if self.fail_first and len(self.bodies) == 1:
            raise UnexpectedResponseError("La resposta no és JSON vàlid.")
        return dict(self.payload), HttpResult(text="{}", status=200, url=url)


def _params(body: str) -> dict[str, list[str]]:
    return parse_qs(body, keep_blank_values=True)


@pytest.mark.asyncio
async def test_cerca_construeix_el_cos_i_mapeja() -> None:
    client = FakeClient(ROWS)
    result = await ConsultesAdapter(client).cerca("tenir")

    assert result["status"] == "ok"
    assert result["total"] == 2
    assert result["corpus_total"] == 1176
    assert result["results"][0]["id"] == "5895"
    assert "table_id=7" in client.urls[0]

    params = _params(client.bodies[0])
    assert params["wdtNonce"] == ["abc123def4"]
    assert params["search[value]"] == ["tenir"]
    assert params["columns[3][search][value]"] == [""]
    assert params["columns[4][search][value]"] == [""]
    assert params["start"] == ["0"]
    assert params["length"] == ["5"]
    assert result["available_themes"][0] == "Fonètica"


@pytest.mark.asyncio
async def test_tema_i_camp() -> None:
    client = FakeClient(ROWS)
    adapter = ConsultesAdapter(client)

    await adapter.cerca(tema="Sintaxi")
    params = _params(client.bodies[0])
    assert params["columns[3][search][value]"] == ["Sintaxi"]
    assert params["search[value]"] == [""]

    client.bodies.clear()
    await adapter.cerca("tenir", camp="pregunta")
    params = _params(client.bodies[0])
    assert params["search[value]"] == [""]
    assert params["columns[4][search][value]"] == ["tenir"]


@pytest.mark.asyncio
async def test_paginacio() -> None:
    payload = dict(ROWS)
    payload["recordsFiltered"] = 10
    adapter = ConsultesAdapter(FakeClient(payload))
    result = await adapter.cerca("tenir", limit=2, offset=5)

    params = _params(adapter.client.bodies[0])
    assert params["start"] == ["5"]
    assert params["length"] == ["2"]
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert "truncated" in result["warnings"]


@pytest.mark.asyncio
async def test_zero_resultats() -> None:
    adapter = ConsultesAdapter(FakeClient({"recordsTotal": 1176, "recordsFiltered": 0, "data": []}))
    result = await adapter.cerca("zzzzinexistent")
    assert result["status"] == "no_results"
    assert result["results"] == []
    assert result["has_more"] is False
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_offset_mes_enlla_del_total_no_es_error() -> None:
    payload = {"recordsTotal": 1176, "recordsFiltered": 2, "data": []}
    result = await ConsultesAdapter(FakeClient(payload)).cerca("tenir", offset=5)
    assert result["status"] == "ok"
    assert result["returned"] == 0
    assert result["has_more"] is False
    assert "offset_out_of_range" in result["warnings"]


@pytest.mark.asyncio
async def test_sense_comptador_no_es_un_zero() -> None:
    payload = {"recordsTotal": 1176, "data": []}
    result = await ConsultesAdapter(FakeClient(payload)).cerca("tenir")

    assert result["status"] == "unexpected_response"
    assert result["total"] is None
    assert "records_filtered_missing" in result["warnings"]
    assert "zero_results" not in result["warnings"]
    assert result["error"]["code"] == "unexpected_response"


@pytest.mark.asyncio
async def test_sense_comptador_amb_files_ho_avisa() -> None:
    payload = dict(ROWS)
    payload.pop("recordsFiltered")
    result = await ConsultesAdapter(FakeClient(payload)).cerca("tenir")

    assert result["status"] == "ok"
    assert result["total"] == 2
    assert "records_filtered_missing" in result["warnings"]


@pytest.mark.asyncio
async def test_nonce_caducat_reintenta_un_cop() -> None:
    client = FakeClient(ROWS, fail_first=True)
    result = await ConsultesAdapter(client).cerca("tenir")
    assert result["status"] == "ok"
    assert len(client.bodies) == 2
    assert client.gets == 2


@pytest.mark.asyncio
async def test_sense_nonce_es_error() -> None:
    client = FakeClient(ROWS, page="<html><body>error</body></html>")
    with pytest.raises(UnexpectedResponseError, match="testimoni"):
        await ConsultesAdapter(client).cerca("tenir")


@pytest.mark.asyncio
async def test_validacions() -> None:
    adapter = ConsultesAdapter(FakeClient(ROWS))
    with pytest.raises(InvalidQueryError, match="Falta"):
        await adapter.cerca()
    with pytest.raises(InvalidQueryError, match="tema"):
        await adapter.cerca(tema="Inventat")
    with pytest.raises(InvalidQueryError, match="camp"):
        await adapter.cerca("tenir", camp="resposta")
    with pytest.raises(InvalidQueryError, match="offset"):
        await adapter.cerca("tenir", offset=-1)


@pytest.mark.asyncio
async def test_limit_es_retalla_a_vint() -> None:
    client = FakeClient(ROWS)
    result = await ConsultesAdapter(client).cerca("tenir", limit=100)
    assert result["query"]["limit"] == 20
    assert _params(client.bodies[0])["length"] == ["20"]


@pytest.mark.asyncio
async def test_dues_cerques_comparteixen_el_nonce() -> None:
    client = FakeClient(ROWS)
    adapter = ConsultesAdapter(client)
    await adapter.cerca("tenir")
    await adapter.cerca("ésser")
    assert client.gets == 1
    assert len(client.bodies) == 2


@pytest.mark.asyncio
async def test_cerques_simultànies_carreguen_el_nonce_un_cop() -> None:
    client = FakeClient(ROWS)
    adapter = ConsultesAdapter(client)
    await asyncio.gather(adapter.cerca("tenir"), adapter.cerca("ésser"), adapter.cerca("fer"))
    assert client.gets == 1
