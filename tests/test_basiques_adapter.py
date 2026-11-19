from __future__ import annotations

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
    "No hi ha cap forma que compleixi aquestes condicions</body></html>"
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
async def test_mode_negatiu_rebutjat(tmp_path) -> None:
    adapter = _adapter(FakeClient({}), tmp_path)
    with pytest.raises(InvalidQueryError, match="mode"):
        await adapter.cerca_forma("somriu", mode="no comença per")


@pytest.mark.asyncio
async def test_zero(tmp_path) -> None:
    client = FakeClient({FORMES2_URL: ZERO})
    result = await _adapter(client, tmp_path).cerca_forma("zzzz")
    assert result["status"] == "no_matches"
    assert result["total"] == 0
    assert result["occurrences"] == []
    assert "zero_results" in result["warnings"]


@pytest.mark.asyncio
async def test_eco_divergent(tmp_path) -> None:
    page = _forma().replace("Coincident amb somriu", "Coincident amb cantava")
    client = FakeClient({FORMES2_URL: page})
    result = await _adapter(client, tmp_path).cerca_forma("somriu")
    assert result["echo_verified"] is False
    assert "echo_unexpected" in result["warnings"]
