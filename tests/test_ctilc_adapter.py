from __future__ import annotations

import re
from pathlib import Path

import pytest

from llengua_mcp.adapters.ctilc import CtilcAdapter
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import InvalidQueryError, StaleSearchError, UpstreamError
from llengua_mcp.http import HttpResult
from llengua_mcp.models import CtilcFilters, PatternElement

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


def _filtered_page(
    *,
    filtered: int = 1237,
    unfiltered: int = 2136,
    echo_var: str = "@central",
    with_rows: bool = True,
) -> str:
    html = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    html = html.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3",
        f"Freqüència total</b>:&nbsp;&nbsp;{unfiltered}",
    )
    filter_table = (
        '<center><table class="tableFILTREStop"><tr><td width="75%">'
        "<b>Filtre per varietat</b>: central</td>"
        f"<td><b>Quantitat filtrada</b>:&nbsp;&nbsp;{filtered}</td>"
        "</tr></table></center>"
    )
    html = html.replace(
        '</div>\n<div id="cHTML2">',
        filter_table + '</div>\n<div id="cHTML2">',
    )
    html = html.replace(
        "</body>",
        f'<input type="hidden" name="varSelec" value="{echo_var}" /></body>',
    )
    if not with_rows:
        html = re.sub(r'<div id="cHTML2">.*?</div>', "", html, flags=re.DOTALL)
    return html


class FilterListClient(FakeClient):
    def __init__(self, search_html: str, list_html: str) -> None:
        super().__init__(search_html)
        self.list_html = list_html

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.bodies.append(body)
        text = self.list_html if "FiltObra_filtres" in url else self.html
        return HttpResult(text=text, status=200, url=url)


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
        self.urls: list[str] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.bodies.append(body)
        self.urls.append(url)
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


class TooLargeClient:
    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        raise UpstreamError(
            "La resposta supera el límit de mida configurat.",
            hint="Redueix el nombre de files o augmenta LLENGUA_MAX_BYTES.",
            source=url,
        )

    async def get_text(self, url: str, **kwargs) -> HttpResult:
        raise AssertionError("no s'hauria de cridar")


@pytest.mark.asyncio
async def test_collocacions_massa_gran_es_accioable(tmp_path) -> None:
    adapter = CtilcAdapter(TooLargeClient(), _settings(tmp_path), CursorStore())
    with pytest.raises(UpstreamError, match="massa gran") as info:
        await adapter.collocacions("altre", freq_min=5)
    assert "freq_min" in info.value.hint
    assert "altre" in info.value.message


@pytest.mark.asyncio
async def test_collocacions_forma_construeix_el_cos_i_retorna_metriques(tmp_path) -> None:
    html = (FIXTURES / "collocacions_forma_somriures.html").read_text(encoding="utf-8")
    client = CollocacionsClient(html)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.collocacions_forma("somriures", radi=2, freq_min=10, limit=2)
    assert result["status"] == "ok"
    assert result["forma"] == "somriures"
    assert result["forma_echo"] == "somriures"
    assert result["forma_echo_verified"] is True
    assert result["total"] == 80
    assert result["query"]["radi"] == 2
    body = client.bodies[0]
    assert "cadforma=somriures" in body
    assert "cadforma" in body
    assert "cadlema" not in body
    assert client.urls[0].endswith("CTILCQCol_FormesAgrup2.asp")
    category = next(cat for cat in result["categories"] if cat["codi"] == "S")
    item = category["items"][0]
    assert {"info_mutua", "freq", "distancia", "varianca", "freq_lema"} <= set(item)
    assert item["info_mutua"] > 0


@pytest.mark.asyncio
async def test_collocacions_forma_limita_per_categoria(tmp_path) -> None:
    html = (FIXTURES / "collocacions_forma_somriures.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions_forma("somriures", limit=1)
    for category in result["categories"]:
        assert len(category["items"]) == 1
    assert "collocations_truncated" in result["warnings"]


@pytest.mark.asyncio
async def test_collocacions_forma_eco_divergent(tmp_path) -> None:
    html = (FIXTURES / "collocacions_forma_somriures.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions_forma("somrigué")
    assert result["status"] == "unexpected_response"
    assert result["forma_echo"] == "somriures"
    assert result["forma_echo_verified"] is False
    assert result["categories"] == []
    assert "forma_echo_unexpected" in result["warnings"]
    assert result["error"]["code"] == "forma_echo_unexpected"


@pytest.mark.asyncio
async def test_collocacions_forma_sense_comptador(tmp_path) -> None:
    html = (FIXTURES / "collocacions_forma_zero.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(CollocacionsClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.collocacions_forma("zzzz")
    assert result["status"] == "unexpected_response"
    assert result["forma_echo_verified"] is False
    assert "zero_without_counter" in result["warnings"]
    assert result["error"]["code"] == "zero_without_counter"


@pytest.mark.asyncio
async def test_collocacions_forma_rebutja_forma_amb_espais(tmp_path) -> None:
    adapter = CtilcAdapter(CollocacionsClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError):
        await adapter.collocacions_forma("somriure burleta")


@pytest.mark.asyncio
async def test_filtres_construeix_el_cos_i_usa_total_filtrat(tmp_path) -> None:
    client = FakeClient(_filtered_page())
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        filters=CtilcFilters(varietat=["central"]),
    )
    assert result["status"] == "ok"
    assert result["total"] == 1237
    assert result["total_unfiltered"] == 2136
    assert result["filters_verified"] is True
    assert result["filters_summary"] == ["varietat: central"]
    assert result["query"]["filters"] == {"varietat": ["central"]}
    assert "varSelec=%40central" in client.bodies[0]


@pytest.mark.asyncio
async def test_filtres_eco_divergent(tmp_path) -> None:
    client = FakeClient(_filtered_page(echo_var="@valencià"))
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        filters=CtilcFilters(varietat=["central"]),
    )
    assert result["status"] == "unexpected_response"
    assert result["filters_verified"] is False
    assert "filters_echo_unexpected" in result["warnings"]


@pytest.mark.asyncio
async def test_filtres_no_aplicats(tmp_path) -> None:
    html = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    html = html.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    adapter = CtilcAdapter(FakeClient(html), _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        filters=CtilcFilters(varietat=["central"]),
    )
    assert result["status"] == "unexpected_response"
    assert result["filters_verified"] is False
    assert "filters_not_applied" in result["warnings"]


@pytest.mark.asyncio
async def test_filtres_sense_files_no_es_absencia(tmp_path) -> None:
    adapter = CtilcAdapter(
        FakeClient(_filtered_page(filtered=1, with_rows=False)),
        _settings(tmp_path),
        CursorStore(),
    )
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        filters=CtilcFilters(varietat=["central"]),
    )
    assert result["status"] == "unexpected_response"
    assert result["returned"] == 0
    assert "filtered_empty_unverified" in result["warnings"]


@pytest.mark.asyncio
async def test_filtres_amb_query_buida_es_zero_valid(tmp_path) -> None:
    page = (FIXTURES / "ctilc_zero.html").read_text(encoding="utf-8")
    adapter = CtilcAdapter(FakeClient(page), _settings(tmp_path), CursorStore())
    result = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="forma", value="amb", alternatives=["de"]),
            PatternElement(type="forma", value="mala"),
            PatternElement(type="forma", value="fe"),
        ],
        filters=CtilcFilters(varietat=["central"]),
    )
    assert result["status"] == "no_matches"
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_cursor_guarda_i_reenvia_els_filtres(tmp_path) -> None:
    client = FakeClient(_filtered_page())
    store = CursorStore()
    adapter = CtilcAdapter(client, _settings(tmp_path), store)
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
        filters=CtilcFilters(varietat=["central"]),
    )
    token = start["search_cursor"]
    payload = store.get(token)
    assert payload is not None
    assert payload.filters == {"varSelec": "@central"}

    await adapter.continue_search(token, limit=2)
    assert "varSelec=%40central" in client.bodies[-1]


@pytest.mark.asyncio
async def test_filtres_invalids(tmp_path) -> None:
    adapter = CtilcAdapter(FakeClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError, match="rang d'anys"):
        await adapter.cerca(lema="somriure", filters=CtilcFilters(any_min=2000, any_max=1990))
    with pytest.raises(InvalidQueryError, match="gènere"):
        await adapter.cerca(lema="somriure", filters=CtilcFilters(genere=["inventat"]))
    with pytest.raises(InvalidQueryError, match="varietat"):
        await adapter.cerca(lema="somriure", filters=CtilcFilters(varietat=["inventada"]))


@pytest.mark.asyncio
async def test_filtres_disponibles(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    list_page = (FIXTURES / "ctilc_filtres_autors.html").read_text(encoding="utf-8")
    client = FilterListClient(search_page, list_page)
    adapter = CtilcAdapter(client, _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.filtres_disponibles(start["search_cursor"], tipus="autors", limit=2)
    assert result["status"] == "ok"
    assert result["total"] == 3
    assert result["returned"] == 2
    assert result["has_more"] is True
    assert result["values"][0] == {
        "value": "Abelló, Montserrat",
        "label": "Abelló, Montserrat",
        "count": 2,
    }
    assert "filt=authors" in client.bodies[-1]

    second = await adapter.filtres_disponibles(
        start["search_cursor"], tipus="autors", limit=2, offset=2
    )
    assert second["values"][0]["value"] == "Arbó, Sebastià"
    assert second["has_more"] is False


@pytest.mark.asyncio
async def test_filtres_disponibles_tipus_invalid(tmp_path) -> None:
    adapter = CtilcAdapter(FakeClient(""), _settings(tmp_path), CursorStore())
    with pytest.raises(InvalidQueryError, match="tipus de filtre"):
        await adapter.filtres_disponibles("qualsevol", tipus="anys")


@pytest.mark.asyncio
async def test_dispersio_amb_filtres_avisa(tmp_path) -> None:
    search_page = _filtered_page()
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
        filters=CtilcFilters(varietat=["central"]),
    )
    result = await adapter.dispersio_cronologica(start["search_cursor"])
    assert "filters_not_applied" in result["warnings"]
    assert result["status"] == "partial"


@pytest.mark.asyncio
async def test_dispersio_dialectal_validada(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    dial_page = (FIXTURES / "dispersio_dialectal.html").read_text(encoding="utf-8")

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=dial_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_dialectal(start["next_cursor"])
    assert result["status"] == "ok"
    assert result["data_valid"] is True
    assert result["unvalidated"] is None
    assert result["search_total"] == 2136
    assert result["totals_match_search"] is True
    assert len(result["varieties"]) == 6
    assert result["totals"]["query_hits"] == 2136
    assert result["totals"]["corpus_hits"] == 126604218
    assert result["peak_relative"]["label"] == "baleàric"


@pytest.mark.asyncio
async def test_dispersio_dialectal_total_divergent(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    dial_page = (FIXTURES / "dispersio_dialectal.html").read_text(encoding="utf-8")
    dial_page = dial_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;2136",
        "Freqüència total</b>:&nbsp;&nbsp;9999",
    )

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=dial_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_dialectal(start["next_cursor"])
    assert result["status"] == "partial"
    assert result["data_valid"] is False
    assert result["varieties"] == []
    assert result["unvalidated"] is not None
    assert "corpus_updated" in result["warnings"]
    assert "totals_mismatch" in result["warnings"]


@pytest.mark.asyncio
async def test_dispersio_general_validada(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    general_page = (FIXTURES / "dispersio_general.html").read_text(encoding="utf-8")

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=general_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_general(start["next_cursor"])
    assert result["status"] == "ok"
    assert result["data_valid"] is True
    assert result["unvalidated"] is None
    assert result["search_total"] == 2136
    assert result["totals"] == {"query_hits": 2136, "corpus_hits": 126604218}
    assert set(result["attributes"]) == {
        "any",
        "varietat",
        "traduccio",
        "tipus",
        "genere",
        "classificacio",
    }
    assert len(result["attributes"]["any"]["groups"]) == 10
    assert result["attributes"]["varietat"]["peak_relative"]["label"] == "Baleàric"


@pytest.mark.asyncio
async def test_dispersio_general_total_divergent(tmp_path) -> None:
    search_page = (FIXTURES / "ctilc_two_rows.html").read_text(encoding="utf-8")
    search_page = search_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    general_page = (FIXTURES / "dispersio_general.html").read_text(encoding="utf-8")
    general_page = general_page.replace(
        "Freqüència total</b>:&nbsp;&nbsp;2136",
        "Freqüència total</b>:&nbsp;&nbsp;9999",
    )

    class SwitchClient:
        async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
            return HttpResult(text=search_page, status=200, url=url)

        async def get_text(self, url: str, **kwargs) -> HttpResult:
            return HttpResult(text=general_page, status=200, url=url)

    adapter = CtilcAdapter(SwitchClient(), _settings(tmp_path), CursorStore())
    start = await adapter.search_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ],
        limit=2,
    )
    result = await adapter.dispersio_general(start["next_cursor"])
    assert result["status"] == "partial"
    assert result["data_valid"] is False
    assert result["attributes"] == {}
    assert result["unvalidated"] is not None
    assert "corpus_updated" in result["warnings"]
