from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.dispersions import parse_cronologia

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_cronologia() -> None:
    data = parse_cronologia((FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8"))
    assert data["pattern_echo"] == "somriure adj:-"
    assert data["search_total"] == 2136
    assert len(data["periods"]) == 10
    assert data["totals"] == {"hits": 2136, "corpus_units": 126604218}
    assert data["totals_match_search"] is True

    first = data["periods"][0]
    assert first["label"] == "1832-1913"
    assert first["from_year"] == 1832
    assert first["to_year"] == 1913
    assert first["hits"] == 45
    assert first["corpus_units"] == 13001158
    assert first["per_million"] == 3.46

    last = data["periods"][-1]
    assert last["per_million"] == 24.11

    assert data["peak_absolute"] == {"label": "2021-2022", "hits": 307}
    assert data["peak_relative"]["label"] == "2021-2022"
    assert data["peak_relative"]["per_million"] == 24.11


def test_percentatge_del_graf_no_es_fa_servir() -> None:
    data = parse_cronologia((FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8"))
    # La taxa es deriva dels enters, no del percentatge arrodonit del gràfic.
    first = data["periods"][0]
    assert first["per_million"] == round(45 / 13001158 * 1_000_000, 2)


def test_sense_grafic_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_cronologia("<html><body>error intern</body></html>")


def test_tram_sense_numerador_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_cronologia(
            "<script>var chartData = [['x'],['1832-1913',0.1,'sense tooltip']];</script>"
        )
