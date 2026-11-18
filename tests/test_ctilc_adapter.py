from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.adapters.ctilc import CtilcAdapter
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import InvalidQueryError, StaleSearchError
from llengua_mcp.http import HttpResult
from llengua_mcp.models import PatternElement

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.bodies: list[str] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.bodies.append(body)
        return HttpResult(text=self.html, status=200, url=url)

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


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


@pytest.mark.asyncio
async def test_search_creates_cursor_and_keeps_id_as_string(tmp_path) -> None:
    html = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    html = html.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;100"
    )
    client = FakeClient(html)
    store = CursorStore(ttl_seconds=60)
    adapter = CtilcAdapter(client, _settings(tmp_path), store)
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=10,
    )
    assert result["status"] == "ok"
    assert result["echo_verified"] is True
    assert result["total"] == 100
    assert result["returned"] == 3
    assert result["has_more"] is True
    assert result["next_cursor"]
    assert result["occurrences"][0]["occurrence_id"] == "558397"
    assert "00*lema=somriure" in client.bodies[0]
    assert "%2A" not in client.bodies[0]
    payload = store.get(result["next_cursor"])
    assert payload is not None
    assert payload.resultat == "179500525152020580"
    assert isinstance(payload.resultat, str)


@pytest.mark.asyncio
async def test_echo_mismatch_is_not_ok(tmp_path) -> None:
    html = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    html = html.replace("00*lema=somriure&amp;01*cg=adj%3A-", "00*lema=somriure")
    client = FakeClient(html)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ]
    )
    assert result["status"] == "unexpected_response"
    assert result["echo_verified"] is False


@pytest.mark.asyncio
async def test_zero_is_no_matches(tmp_path) -> None:
    client = FakeClient((FIXTURES / "ctilc_zero.html").read_text(encoding="utf-8"))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="forma", value="amb", alternatives=["de"]),
            PatternElement(type="forma", value="mala"),
            PatternElement(type="forma", value="fe"),
        ]
    )
    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_unknown_cursor_is_stale(tmp_path) -> None:
    adapter = CtilcAdapter(FakeClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(StaleSearchError):
        await adapter.continue_search("no-existeix")


class SequenceClient:
    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self.calls = 0

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        page = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        return HttpResult(text=page, status=200, url=url)


@pytest.mark.asyncio
async def test_variants_are_reported_separately(tmp_path) -> None:
    ok_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    ok_page = ok_page.replace(
        "00*lema=somriure&amp;01*cg=adj%3A-",
        "00*forma=somriure&amp;01*forma=maliciós",
    )
    ok_page = ok_page.replace(
        "somriure <span style='color:#0000FF;'>adj:-</span>",
        "somriure maliciós",
    )
    zero_page = (FIXTURES / "ctilc_zero_no_header.html").read_text(encoding="utf-8")
    client = SequenceClient([ok_page, zero_page])
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.search_phrase(
        "somriure maliciós", variants=["somriure de mala fe"], limit=2
    )
    assert result["status"] == "ok"
    assert result["variants"][0]["status"] == "ok"
    assert result["variants"][1]["status"] == "no_matches"
    assert result["total"] is None
    assert result["variants"][0]["total"] == 3
    assert result["variants"][1]["total"] == 0


@pytest.mark.asyncio
async def test_salut_reports_drift_without_failing(tmp_path) -> None:
    page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), CursorStore())
    result = await adapter.salut()
    assert result["status"] == "ok"
    assert result["observed_total"] == 3
    assert "corpus_updated" in result["warnings"]


@pytest.mark.asyncio
async def test_cerca_validation(tmp_path) -> None:
    adapter = CtilcAdapter(FakeClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError):
        await adapter.cerca(lema="somriure", forma="somriure")
    with pytest.raises(InvalidQueryError):
        await adapter.cerca()
    with pytest.raises(InvalidQueryError):
        await adapter.cerca(forma="somriure", categoria="V")


@pytest.mark.asyncio
async def test_continuation_rejects_changed_total(tmp_path) -> None:
    first = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    first = first.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;100"
    )
    changed = first.replace(
        "Freqüència total</b>:&nbsp;&nbsp;100", "Freqüència total</b>:&nbsp;&nbsp;99"
    )
    client = SequenceClient([first, changed])
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    assert start["next_cursor"]
    result = await adapter.continue_search(start["next_cursor"], limit=2)
    assert result["status"] == "stale_search"
    assert result["returned"] == 0
    assert result["occurrences"] == []
    assert "corpus_updated" in result["warnings"]


@pytest.mark.asyncio
async def test_visible_echo_mismatch_is_not_matches(tmp_path) -> None:
    page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    page = page.replace(
        "00*lema=somriure&amp;01*cg=adj%3A-",
        "00*forma=somriure&amp;01*forma=maliciós",
    )
    # Els camps ocults coincideixen amb la consulta, però l'eco visible diu
    # una altra cosa: no es pot acceptar com a resultat.
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="forma", value="somriure"),
            PatternElement(type="forma", value="maliciós"),
        ],
        limit=2,
    )
    assert result["echo_verified"] is False
    assert result["status"] == "unexpected_response"


@pytest.mark.asyncio
async def test_zero_message_without_counter_is_unexpected(tmp_path) -> None:
    page = (
        "<html><body>"
        "<div class='tvermell'>No s'han trobat ocurrències per al patró "
        "seleccionat: somriure</div>"
        "<input type='hidden' id='formdata' value='seccio=CTILC1&amp;00*forma=somriure'>"
        "</body></html>"
    )
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern([PatternElement(type="forma", value="somriure")])
    assert result["status"] == "unexpected_response"
    assert result["total"] is None


@pytest.mark.asyncio
async def test_salut_does_not_create_a_cursor(tmp_path) -> None:
    page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    page = page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;100"
    )
    store = CursorStore()
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), store)
    result = await adapter.salut()
    assert result.get("next_cursor") is None
    assert result.get("search_cursor") is None
    assert len(store._entries) == 0


@pytest.mark.asyncio
async def test_salut_no_esborra_cursors_de_lusuari(tmp_path) -> None:
    page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    page = page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;100"
    )
    store = CursorStore()
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), store)
    user = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    token = user["search_cursor"]
    assert token and store.get(token) is not None

    await adapter.salut()

    # La consulta de control és la mateixa que la de l'usuari: el diagnòstic
    # no ha de tocar el seu cursor.
    assert store.get(token) is not None


@pytest.mark.asyncio
async def test_cerca_sense_persistir_cursor(tmp_path) -> None:
    page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    store = CursorStore()
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), store)
    result = await adapter.search(
        elements=[PatternElement(type="forma", value="somriure")],
        query={"mode": "test"},
        limit=2,
        persist_cursor=False,
    )
    assert result["has_more"] is True
    assert result["search_cursor"] is None
    assert result["next_cursor"] is None
    assert len(store._entries) == 0


@pytest.mark.asyncio
async def test_continue_rejects_zero_limit(tmp_path) -> None:
    adapter = CtilcAdapter(FakeClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError):
        await adapter.continue_search("qualsevol", limit=0)


class DispersioClient:
    def __init__(self, html: str) -> None:
        self.html = html

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


@pytest.mark.asyncio
async def test_dispersio_cronologica_validada(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    dispersio_page = (FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8")

    class SwitchClient:
        def __init__(self) -> None:
            self.calls = 0

        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            self.calls += 1
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=dispersio_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_cronologica(start["next_cursor"])
    assert result["status"] == "ok"
    assert result["data_valid"] is True
    assert result["unvalidated"] is None
    assert result["search_total"] == 2136
    assert result["totals_match_search"] is True
    assert len(result["periods"]) == 10
    assert result["peak_relative"]["label"] == "2021-2022"


DISPERSIO_UNA_PAGINA = (
    "<html><body><center><table>"
    "<tr><td><b>Coocurrències</b>:&nbsp;&nbsp;somriure "
    "<span style='color: 0000FF;'>adj:-</span></td>"
    "<td><b>Freqüència total</b>:&nbsp;&nbsp;3</td>"
    "<td><b>Índex de dispersió</b>:&nbsp;&nbsp;0.8</td></tr></table></center><script>\n"
    "var chartData = [['Grup cronològic','Proporció',{ role: 'tooltip' }]\n\n"
    ",['1832-1913',0.000023,'1832-1913\\nTotal tram a la cerca: 3\\n"
    "Total tram al corpus: 13.001.158\\n0,000023%',"
    "llistacolorsAny['1832-1913']]\n];\n"
    "</script></body></html>"
)


@pytest.mark.asyncio
async def test_dispersio_amb_cursor_duna_sola_pagina(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=DISPERSIO_UNA_PAGINA, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=10,
    )
    # Tots els resultats caben en una pàgina: no hi ha `next_cursor`, però sí
    # un cursor estable per demanar la dispersió.
    assert start["has_more"] is False
    assert start["next_cursor"] is None
    assert start["search_cursor"]

    result = await adapter.dispersio_cronologica(start["search_cursor"])
    assert result["status"] == "ok"
    assert result["data_valid"] is True
    assert result["periods"][0]["hits"] == 3
    assert result["search_total"] == 3


@pytest.mark.asyncio
async def test_dispersio_amb_patro_divergent(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    dispersio_page = (FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8")
    dispersio_page = dispersio_page.replace(
        "Coocurrències</b>:&nbsp;&nbsp;somriure <span style='color: 0000FF;'>adj:-</span>",
        "Coocurrències</b>:&nbsp;&nbsp;somriure <span style='color: 0000FF;'>subst</span>",
    )

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=dispersio_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_cronologica(start["next_cursor"])
    assert result["status"] == "unexpected_response"
    assert result["data_valid"] is False
    assert result["periods"] == []
    assert result["totals"] is None
    assert result["peak_absolute"] is None
    assert len(result["unvalidated"]["periods"]) == 10
    assert result["error"]["code"] == "pattern_echo_unexpected"


@pytest.mark.asyncio
async def test_dispersio_amb_totals_desvats(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;9999"
    )
    dispersio_page = (FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8")

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=dispersio_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_cronologica(start["next_cursor"])
    # La pàgina de dispersió és coherent amb ella mateixa (suma = 2136), però
    # el total del cursor és un altre: és el cursor el que ha quedat desfassat.
    assert result["status"] == "partial"
    assert result["data_valid"] is False
    assert result["periods"] == []
    assert len(result["unvalidated"]["periods"]) == 10
    assert "corpus_updated" in result["warnings"]


@pytest.mark.asyncio
async def test_dispersio_amb_cursor_desconegut(tmp_path) -> None:
    adapter = CtilcAdapter(DispersioClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(StaleSearchError):
        await adapter.dispersio_cronologica("no-existeix")


class CollocacionsClient:
    def __init__(self, html: str) -> None:
        self.html = html
        self.bodies: list[str] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.bodies.append(body)
        return HttpResult(text=self.html, status=200, url=url)

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        return HttpResult(text=self.html, status=200, url=url)


@pytest.mark.asyncio
async def test_collocacions_construeix_el_cos_correcte(tmp_path) -> None:
    html = (FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8")
    client = CollocacionsClient(html)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.collocacions("somriure", radi=2, freq_min=10, limit=2)
    assert result["status"] == "ok"
    assert result["lema"] == "somriure"
    assert result["total"] == 1159
    body = client.bodies[0]
    assert "cadlema=somriure" in body
    assert "radiE=2" in body
    assert "radiD=2" in body
    assert "freqMin=10" in body
    assert "*" not in body.replace("*", "*")  # no hi ha claus NN*
    assert result["query"]["radi"] == 2


@pytest.mark.asyncio
async def test_collocacions_rebutja_lema_amb_espais(tmp_path) -> None:
    adapter = CtilcAdapter(CollocacionsClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError):
        await adapter.collocacions("somriure burleta")


@pytest.mark.asyncio
async def test_collocacions_limita_per_categoria(tmp_path) -> None:
    html = (FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8")
    client = CollocacionsClient(html)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.collocacions("somriure", limit=1)
    for category in result["categories"]:
        assert len(category["items"]) == 1


@pytest.mark.asyncio
async def test_collocacions_limit_8_retorna_8(tmp_path) -> None:
    html = (FIXTURES / "collocacions_moltes.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions("somriure", limit=8)
    verbs = next(category for category in result["categories"] if category["codi"] == "V")
    assert len(verbs["items"]) == 8
    assert verbs["rows"] == 12
    assert result["returned_items"] == 9
    assert "collocations_truncated" in result["warnings"]
    assert result["altres"]["items"] == [{"lema": "joan", "freq": 9}]


@pytest.mark.asyncio
async def test_collocacions_eco_divergent(tmp_path) -> None:
    html = (FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions("riure")
    assert result["status"] == "unexpected_response"
    assert result["lema_echo"] == "somriure"
    assert result["lema_echo_verified"] is False
    assert result["categories"] == []
    assert "lema_echo_unexpected" in result["warnings"]
    assert result["error"]["code"] == "lema_echo_unexpected"


@pytest.mark.asyncio
async def test_collocacions_avisa_de_files_parcials(tmp_path) -> None:
    html = (FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions("somriure")
    assert result["status"] == "ok"
    assert result["lema_echo_verified"] is True
    assert result["total"] == 1159
    assert result["counted_rows"] == 4
    assert result["excluded_rows"] == 1
    assert "partial_rows" in result["warnings"]
    assert "partial_rows" in result["note"]


def test_lema_matches_accepta_sufix_d_homonimia() -> None:
    from llengua_mcp.adapters.ctilc import _lema_matches

    assert _lema_matches("somriure", "Somriure") is True
    assert _lema_matches("altre", "altre_1") is True
    assert _lema_matches("altre", "altra") is False
