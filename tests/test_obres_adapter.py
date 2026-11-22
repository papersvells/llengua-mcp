from __future__ import annotations

import re
from pathlib import Path

import pytest

from llengua_mcp.adapters.ctilc import (
    OBRES_AUT2_URL,
    OBRES_AUT_URL,
    OBRES_TITOL_URL,
    CtilcAdapter,
)
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import InvalidQueryError, UpstreamError
from llengua_mcp.http import HttpResult

FIXTURES = Path(__file__).parent / "fixtures"

ZERO_TITOL = (
    "<html><body>"
    '<table class="tableFORMOUT"><tr><td><b>Títol de l\'obra:</b> zzzz</td></tr></table>'
    "No hi ha cap obra que respongui al paràmetre introduït"
    "</body></html>"
)


class FakeClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        self.calls.append((url, body))
        return HttpResult(text=self.responses[url], status=200, url=url)


class HugeClient:
    async def post_text(self, url: str, body: str, **kwargs) -> HttpResult:
        raise UpstreamError("La resposta supera el límit de mida configurat.", source=url)


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


def _autors() -> str:
    return (FIXTURES / "obres_autors.html").read_text(encoding="utf-8")


def _resultats() -> str:
    return (FIXTURES / "obres_resultats.html").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_obres_autor_ambigu(tmp_path) -> None:
    client = FakeClient({OBRES_AUT_URL: _autors()})
    result = await _adapter(client, tmp_path).obres(autor="sagarra")
    assert result["status"] == "ambiguous_author"
    assert result["total"] is None
    assert len(result["authors"]) == 5
    assert result["works"] == []
    assert result["has_more"] is False
    assert "author_candidates" in result["warnings"]
    assert result["echo_verified"] is True
    assert client.calls == [(OBRES_AUT_URL, "autor=sagarra")]


@pytest.mark.asyncio
async def test_obres_autor_exacte_tria_l_autor(tmp_path) -> None:
    client = FakeClient({OBRES_AUT_URL: _autors(), OBRES_AUT2_URL: _resultats()})
    result = await _adapter(client, tmp_path).obres(autor="Sagarra, Xavier")
    assert result["status"] == "ok"
    assert result["total"] == 3
    assert client.calls[-1] == (OBRES_AUT2_URL, "autorL=3673")


@pytest.mark.asyncio
async def test_obres_autor_id(tmp_path) -> None:
    client = FakeClient({OBRES_AUT2_URL: _resultats()})
    result = await _adapter(client, tmp_path).obres(autor_id="493")
    assert result["status"] == "ok"
    assert result["total"] == 3
    assert result["works"][0]["author"].startswith("Blat")
    assert client.calls == [(OBRES_AUT2_URL, "autorL=493")]


@pytest.mark.asyncio
async def test_obres_titol_i_paginacio(tmp_path) -> None:
    client = FakeClient({OBRES_TITOL_URL: _resultats()})
    result = await _adapter(client, tmp_path).obres(titol="vida", limit=2)
    assert result["status"] == "ok"
    assert result["total"] == 3
    assert result["returned"] == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 2
    assert result["echo_verified"] is True
    assert client.calls == [(OBRES_TITOL_URL, "obra=vida")]


@pytest.mark.asyncio
async def test_obres_incompletes_no_entren_en_bucle(tmp_path) -> None:
    html = _resultats()
    # Conserva la primera obra però elimina les altres dues files.
    html = re.sub(r"\s*<tr>\s*<td>Puig i Alfonso, Francesc</td>.*?</tr>", "", html, flags=re.DOTALL)
    html = re.sub(r"\s*<tr>\s*<td>Desclot, Miquel</td>.*?</tr>", "", html, flags=re.DOTALL)
    adapter = _adapter(FakeClient({OBRES_TITOL_URL: html}), tmp_path)

    first = await adapter.obres(titol="vida", limit=1)
    assert first["status"] == "partial"
    assert first["total"] == 3
    assert first["returned"] == 1
    assert "rows_mismatch" in first["warnings"]
    assert first["has_more"] is False
    assert first["next_offset"] is None

    beyond = await adapter.obres(titol="vida", limit=1, offset=1)
    assert beyond["status"] == "partial"
    assert beyond["returned"] == 0
    assert beyond["has_more"] is False
    assert beyond["next_offset"] is None


@pytest.mark.asyncio
async def test_obres_offset_mes_enlla_de_les_files(tmp_path) -> None:
    adapter = _adapter(FakeClient({OBRES_TITOL_URL: _resultats()}), tmp_path)
    result = await adapter.obres(titol="vida", limit=1, offset=3)
    assert result["has_more"] is False
    assert result["next_offset"] is None


@pytest.mark.asyncio
async def test_obres_titol_zero(tmp_path) -> None:
    client = FakeClient({OBRES_TITOL_URL: ZERO_TITOL})
    result = await _adapter(client, tmp_path).obres(titol="zzzz")
    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert result["works"] == []
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_obres_cal_un_criteri(tmp_path) -> None:
    adapter = _adapter(FakeClient({}), tmp_path)
    with pytest.raises(InvalidQueryError):
        await adapter.obres()
    with pytest.raises(InvalidQueryError, match="cerques diferents"):
        await adapter.obres(autor="Sagarra", titol="vida")


@pytest.mark.asyncio
async def test_obres_massa_gran(tmp_path) -> None:
    result = await _adapter(HugeClient(), tmp_path).obres(titol="a")
    assert result["status"] == "too_many_results"
    assert "response_too_large" in result["warnings"]
    assert result["error"]["code"] == "too_many_results"
