from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from llengua_mcp.adapters.jane import JaneAdapter
from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"
BOOTSTRAP = (FIXTURES / "jane_bootstrap.html").read_text(encoding="utf-8")
LEMA = json.loads((FIXTURES / "jane_rows_lema.json").read_text(encoding="utf-8"))
GENERAL = json.loads((FIXTURES / "jane_rows_general.json").read_text(encoding="utf-8"))
FUNCIO = json.loads((FIXTURES / "jane_rows_funcio.json").read_text(encoding="utf-8"))
ZERO = json.loads((FIXTURES / "jane_zero.json").read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, payload: dict, *, fail_first: bool = False) -> None:
        self.payload = payload
        self.fail_first = fail_first
        self.gets: list[str] = []
        self.urls: list[str] = []
        self.bodies: list[str] = []

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        self.gets.append(url)
        return HttpResult(text=BOOTSTRAP, status=200, url=url)

    async def post_json(self, url: str, body: str, **kwargs):
        self.urls.append(url)
        self.bodies.append(body)
        if self.fail_first and len(self.bodies) == 1:
            raise UnexpectedResponseError("La resposta no és JSON vàlid.")
        return dict(self.payload), HttpResult(text="{}", status=200, url=url)


def _params(body: str) -> dict[str, list[str]]:
    return parse_qs(body, keep_blank_values=True)


@pytest.mark.asyncio
async def test_cerca_lema_builds_request_and_maps_senses() -> None:
    client = FakeClient(LEMA)
    result = await JaneAdapter(client).cerca("maliciós")

    assert result["status"] == "ok"
    assert result["total"] == 1
    assert result["catalog_total"] == 27547
    assert result["results"][0]["lema"] == "maliciós"
    assert [sense["num"] for sense in result["results"][0]["sentits"]] == [1, 2]
    assert result["license"] == "CC BY-NC-ND 3.0 ES"
    assert "citation" not in result

    assert client.gets[0].startswith("https://sinonims.iec.cat/cerca-comenca/")
    url = client.urls[0]
    assert "action=get_wdtable" in url
    assert "table_id=1" in url
    assert "wdt_var1=malici%C3%B3s" in client.urls[0]

    params = _params(client.bodies[0])
    assert params["wdtNonce"] == ["7425348f4b"]
    assert params["start"] == ["0"]
    assert params["length"] == ["5"]
    assert params["columns[3][data]"] == ["lema"]
    assert params["order[0][column]"] == ["2"]


@pytest.mark.asyncio
async def test_mode_general_uses_its_page_and_variable() -> None:
    client = FakeClient(GENERAL)
    result = await JaneAdapter(client).cerca("mala fe", mode="general")

    assert result["status"] == "ok"
    assert result["total"] == 3
    assert client.gets[0].startswith("https://sinonims.iec.cat/cerca-general/")
    assert "wdt_var2=mala%20fe" in client.urls[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [[], [["només una columna"]]])
async def test_no_ofereix_paginacio_si_no_ha_llegit_cap_fila(data) -> None:
    payload = {**LEMA, "recordsFiltered": 6, "data": data}
    result = await JaneAdapter(FakeClient(payload)).cerca("maliciós", limit=4)

    assert result["status"] == "unexpected_response"
    assert result["has_more"] is False
    assert result["next_offset"] is None


@pytest.mark.asyncio
async def test_paginacio_parcial_avanca_segons_files_consumides() -> None:
    payload = {**LEMA, "recordsFiltered": 6, "data": [["mal formada"], LEMA["data"][0]]}
    result = await JaneAdapter(FakeClient(payload)).cerca("maliciós", limit=4, offset=1)

    assert result["returned"] == 1
    assert result["has_more"] is True
    assert result["next_offset"] == 3
    assert "parse_partial" in result["warnings"]


@pytest.mark.asyncio
async def test_funcio_mode_requires_and_maps_the_function() -> None:
    adapter = JaneAdapter(FakeClient(FUNCIO))

    with pytest.raises(InvalidQueryError):
        await adapter.cerca("casa", mode="funcio")
    with pytest.raises(InvalidQueryError):
        await adapter.cerca("casa", mode="funcio", funcio="inexistent")
    with pytest.raises(InvalidQueryError):
        await adapter.cerca("casa", funcio="nominal")

    client = FakeClient(FUNCIO)
    result = await JaneAdapter(client).cerca("casa", mode="funcio", funcio="nominal")

    assert result["status"] == "ok"
    assert result["query"]["funcio"] == "nominal"
    assert "nominal" in result["funcions"]
    assert "wdt_var4=3" in client.urls[0]
    assert client.gets[0].startswith("https://sinonims.iec.cat/cerca-funcio/")
    params = _params(client.bodies[0])
    assert params["columns[11][data]"] == ["categoria_lex_global"]
    assert result["results"][0]["lema"] == "ajuntament"


@pytest.mark.asyncio
async def test_zero_is_no_results() -> None:
    result = await JaneAdapter(FakeClient(ZERO)).cerca("zzzqqqxyz")

    assert result["status"] == "no_results"
    assert result["total"] == 0
    assert result["results"] == []
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_sense_comptador_no_es_un_zero() -> None:
    result = await JaneAdapter(FakeClient({"recordsTotal": 27547, "data": []})).cerca("maliciós")

    assert result["status"] == "unexpected_response"
    assert result["total"] is None
    assert "records_filtered_missing" in result["warnings"]
    assert "zero_results" not in result["warnings"]
    assert result["error"]["code"] == "unexpected_response"


@pytest.mark.asyncio
async def test_sense_comptador_amb_files_ho_avisa() -> None:
    payload = dict(LEMA)
    payload.pop("recordsFiltered")
    result = await JaneAdapter(FakeClient(payload)).cerca("maliciós")

    assert result["status"] == "ok"
    assert result["total"] == 1
    assert "records_filtered_missing" in result["warnings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("comptador", [False, 0.4, -1])
async def test_comptador_invalid_no_es_un_zero(comptador) -> None:
    payload = {"recordsTotal": 27547, "recordsFiltered": comptador, "data": []}
    result = await JaneAdapter(FakeClient(payload)).cerca("maliciós")

    assert result["status"] == "unexpected_response"
    assert result["total"] is None
    assert "records_filtered_invalid" in result["warnings"]
    assert "zero_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_nonce_is_refreshed_once_on_failure() -> None:
    client = FakeClient(LEMA, fail_first=True)
    result = await JaneAdapter(client).cerca("maliciós")

    assert result["status"] == "ok"
    assert len(client.gets) == 2
    assert len(client.urls) == 2


@pytest.mark.asyncio
async def test_empty_query_is_rejected() -> None:
    with pytest.raises(InvalidQueryError):
        await JaneAdapter(FakeClient(LEMA)).cerca("  ")
    with pytest.raises(InvalidQueryError):
        await JaneAdapter(FakeClient(LEMA)).cerca("a")
