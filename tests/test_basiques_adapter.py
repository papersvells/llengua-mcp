from __future__ import annotations

import re
from pathlib import Path

import pytest

from llengua_mcp.adapters.ctilc import (
    FORMES2_URL,
    FORMESLEMA2_URL,
    CtilcAdapter,
)
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"

ZERO = (
    "<html><body>Forma : Coincident amb zzzz Freqüència total : 0 "
    "No hi ha cap forma que compleixi aquestes condicions"
    '<form name="fConc">'
    '<input type="hidden" name="cadforma" value="zzzz">'
    '<input type="hidden" name="cadformacond" value="0">'
    '<input type="hidden" name="cg" value="">'
    "</form></body></html>"
)

SUFFIX_ZERO = (
    "<html><body>Forma : Coincident amb somriures Freqüència total : 0 "
    "No hi ha cap forma que compleixi aquestes condicions"
    '<form name="fConc">'
    '<input type="hidden" name="cadforma" value="somriures">'
    '<input type="hidden" name="cadformacond" value="0">'
    '<input type="hidden" name="cg" value="">'
    "</form></body></html>"
)


class FakeClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.calls.append((url, body))
        return HttpResult(text=self.responses[url], status=200, url=url)


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


def _adapter(client, tmp_path) -> CtilcAdapter:
    return CtilcAdapter(client, _settings(tmp_path), CursorStore())


def _forma() -> str:
    return (FIXTURES / "basiques_forma.html").read_text(encoding="utf-8")


def _lema() -> str:
    return (FIXTURES / "basiques_lema.html").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_cerca_forma(tmp_path) -> None:
    client = FakeClient({FORMES2_URL: _forma()})
    result = await _adapter(client, tmp_path).cerca_forma("somriu", limit=2)
    assert result["status"] == "ok"
    assert result["total"] == 2019
    assert result["returned"] == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 2
    assert result["echo_verified"] is True
    assert result["forms"][0]["count"] == 13
    assert result["occurrences"][0]["occurrence_id"] == "110080"
    assert client.calls[0] == (
        FORMES2_URL,
        "cadforma=somriu&cadformacond=0&cg=&seccio=CTILC1&iStart=1&iOffset=2",
    )


@pytest.mark.asyncio
async def test_cerca_lema(tmp_path) -> None:
    client = FakeClient({FORMESLEMA2_URL: _lema()})
    result = await _adapter(client, tmp_path).cerca_lema("somriure", limit=2)
    assert result["status"] == "ok"
    assert result["total"] == 14290
    assert len(result["forms"]) == 4
    assert result["forms"][2]["form"] == "somreia"
    assert result["echo_verified"] is True
    assert client.calls[0] == (
        FORMESLEMA2_URL,
        "cadlema=somriure&cadlemacond=0&cg=&seccio=CTILC1&iStart=1&iOffset=2",
    )


@pytest.mark.asyncio
async def test_mode_i_offset(tmp_path) -> None:
    client = FakeClient({FORMES2_URL: _forma()})
    await _adapter(client, tmp_path).cerca_forma("somriu", mode="comença per", limit=10, offset=20)
    body = client.calls[0][1]
    assert "cadformacond=1" in body
    assert body.endswith("iStart=21&iOffset=10")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["forma", "lema"])
@pytest.mark.parametrize("mode", ["no comença per", "no acaba en", "no conté", "que no contingui"])
async def test_mode_negatiu_requereix_categoria(tmp_path, kind, mode) -> None:
    client = FakeClient({})
    search = getattr(_adapter(client, tmp_path), f"cerca_{kind}")
    with pytest.raises(InvalidQueryError, match="requereix el filtre `cg`") as exc:
        await search("somriu", mode=mode)
    assert "cg=I" in exc.value.hint
    assert client.calls == []


@pytest.mark.asyncio
async def test_mode_desconegut_rebutjat(tmp_path) -> None:
    client = FakeClient({})
    with pytest.raises(InvalidQueryError, match="no és vàlid"):
        await _adapter(client, tmp_path).cerca_lema("ah", mode="aproximat", cg="I")
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "condition", "forma_label", "lema_label"),
    [
        ("no comença per", "4", "No començada per", "No començat per"),
        ("no acaba en", "5", "No acabada en", "No acabat en"),
        ("no conté", "6", "Que no contingui", "Que no contingui"),
        ("que no contingui", "6", "Que no contingui", "Que no contingui"),
    ],
)
@pytest.mark.parametrize(("kind", "url"), [("forma", FORMES2_URL), ("lema", FORMESLEMA2_URL)])
async def test_mode_negatiu_verificat(
    tmp_path, kind, url, mode, condition, forma_label, lema_label
):
    page = (FIXTURES / "basiques_negatiu.html").read_text(encoding="utf-8")
    label = forma_label if kind == "forma" else lema_label
    page = page.replace("No començada per", label).replace('value="4"', f'value="{condition}"')
    if kind == "lema":
        page = page.replace("Forma :", "Lemes :").replace("cadforma", "cadlema")
    client = FakeClient({url: page})
    search = getattr(_adapter(client, tmp_path), f"cerca_{kind}")
    result = await search("ah", mode=mode, cg="I", limit=2)
    assert client.calls == [
        (url, f"cad{kind}=ah&cad{kind}cond={condition}&cg=I&seccio=CTILC1&iStart=1&iOffset=2")
    ]
    assert result["status"] == "ok"
    assert result["echo_verified"] is True
    assert result["total"] == 83380
    assert result["occurrences"][0]["nucleus"] == "Hola"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("No començada per", "Començada per"),
        ("<i>ah</i>", "<i>aha</i>"),
        ('name="cadformacond" value="4"', 'name="cadformacond" value="1"'),
        ('name="cadforma" value="ah"', 'name="cadforma" value="aha"'),
        ('name="cg" value="I"', 'name="cg" value=""'),
        ('name="cg"', 'name="cg_alt"'),
    ],
)
async def test_mode_negatiu_amb_eco_divergent(tmp_path, original, replacement) -> None:
    page = (FIXTURES / "basiques_negatiu.html").read_text(encoding="utf-8")
    client = FakeClient({FORMES2_URL: page.replace(original, replacement)})
    result = await _adapter(client, tmp_path).cerca_forma("ah", mode="no comença per", cg="I")
    assert result["status"] == "unexpected_response"
    assert result["echo_verified"] is False
    assert result["total"] is None
    assert result["occurrences"] == []
    assert "echo_unexpected" in result["warnings"]


@pytest.mark.asyncio
async def test_zero(tmp_path) -> None:
    client = FakeClient({FORMES2_URL: ZERO})
    result = await _adapter(client, tmp_path).cerca_forma("zzzz")
    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert result["occurrences"] == []
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page",
    [
        ZERO.replace("Freqüència total : 0", ""),
        ZERO.replace("No hi ha cap forma que compleixi aquestes condicions", ""),
        ZERO.replace("Coincident amb zzzz", "Coincident amb yyyy"),
        ZERO.replace("Freqüència total : 0", "Freqüència total : 10"),
    ],
)
async def test_zero_no_verificat(tmp_path, page) -> None:
    result = await _adapter(FakeClient({FORMES2_URL: page}), tmp_path).cerca_forma("zzzz")
    assert result["status"] == "unexpected_response"
    assert result["total"] is None
    assert "zero_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_eco_divergent(tmp_path) -> None:
    page = _forma().replace("Coincident amb somriu", "Coincident amb cantava")
    client = FakeClient({FORMES2_URL: page})
    result = await _adapter(client, tmp_path).cerca_forma("somriu")
    assert result["echo_verified"] is False
    assert "echo_unexpected" in result["warnings"]


@pytest.mark.asyncio
async def test_eco_d_una_altra_forma_no_valida_el_zero(tmp_path) -> None:
    client = FakeClient({FORMES2_URL: SUFFIX_ZERO})
    result = await _adapter(client, tmp_path).cerca_forma("somriure")
    assert result["status"] == "unexpected_response"
    assert result["echo_verified"] is False
    assert result["total"] is None
    assert "echo_unexpected" in result["warnings"]
    assert "zero_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_eco_amb_accent_diferent_no_es_cola(tmp_path) -> None:
    page = (
        "<html><body>Forma : Coincident amb més Freqüència total : 0 "
        "No hi ha cap forma que compleixi aquestes condicions"
        '<form name="fConc">'
        '<input type="hidden" name="cadforma" value="més">'
        '<input type="hidden" name="cadformacond" value="0">'
        '<input type="hidden" name="cg" value="">'
        "</form></body></html>"
    )
    client = FakeClient({FORMES2_URL: page})
    result = await _adapter(client, tmp_path).cerca_forma("mes")
    assert result["status"] == "unexpected_response"
    assert result["echo_verified"] is False
    assert "zero_results" not in result["warnings"]


@pytest.mark.asyncio
async def test_mode_divergent_en_eco_positiu(tmp_path) -> None:
    page = (
        _forma()
        .replace("Coincident amb somriu", "Començada per somriu")
        .replace('name="cadformacond" value="0"', 'name="cadformacond" value="1"')
    )
    client = FakeClient({FORMES2_URL: page})
    result = await _adapter(client, tmp_path).cerca_forma("somriu")
    assert result["status"] == "ok"
    assert result["total"] == 2019
    assert result["echo_verified"] is False
    assert "echo_unexpected" in result["warnings"]


@pytest.mark.asyncio
async def test_eco_sense_camps_ocults_no_es_verificat(tmp_path) -> None:
    page = re.sub(r'<form name="fConc">.*?</form>', "", _forma(), flags=re.DOTALL)
    client = FakeClient({FORMES2_URL: page})
    result = await _adapter(client, tmp_path).cerca_forma("somriu")
    assert result["status"] == "ok"
    assert result["echo_verified"] is False
    assert "echo_unexpected" in result["warnings"]
