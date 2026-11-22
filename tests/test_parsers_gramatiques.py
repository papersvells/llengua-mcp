from __future__ import annotations

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.gramatiques import parse_search_hits, parse_text

FONT = "giec"


def test_parse_search_hits_accepts_a_list() -> None:
    data = parse_search_hits(
        [{"codiText": "28.1", "titol": "T", "contingut": "<p>perífrasi verbal</p>"}],
        "perífrasi",
        font="gbu",
    )
    assert data["total"] == 1
    assert data["hits"][0]["codi_text"] == "28.1"
    assert data["warnings"] == []


def test_parse_search_hits_accepts_texts() -> None:
    data = parse_search_hits(
        {"texts": [{"codiText": "8.3.3", "titol": "T", "contingut": "<p>pronoms</p>"}]},
        "pronoms",
        font=FONT,
    )
    assert data["total"] == 1
    assert data["hits"][0]["codi_text"] == "8.3.3"


def test_parse_search_hits_amb_texts_null_es_buit() -> None:
    data = parse_search_hits({"texts": None}, "res", font=FONT)
    assert data == {"total": 0, "hits": [], "warnings": []}


def test_parse_search_hits_sense_texts_es_error() -> None:
    with pytest.raises(UnexpectedResponseError, match="texts"):
        parse_search_hits({"lemma": {"lemma": "res"}}, "res", font=FONT)


def test_parse_search_hits_texts_no_es_llista_es_error() -> None:
    with pytest.raises(UnexpectedResponseError, match="llista"):
        parse_search_hits({"texts": "res"}, "res", font=FONT)


def test_parse_search_hits_format_desconegut_es_error() -> None:
    with pytest.raises(UnexpectedResponseError, match="format"):
        parse_search_hits("res", "res", font=FONT)


def test_parse_search_hits_nomes_titols_avisa() -> None:
    data = parse_search_hits(
        {"texts": [{"codiText": "8.3", "titol": "Títol", "contingut": None}]},
        "res",
        font=FONT,
    )
    assert data["total"] == 1
    assert data["hits"] == []
    assert "no_readable_sections" in data["warnings"]


def test_parse_search_hits_trunca_a_cinc() -> None:
    items = [
        {"codiText": str(index), "titol": "T", "contingut": "<p>paraula</p>"} for index in range(7)
    ]
    data = parse_search_hits({"texts": items}, "paraula", font=FONT)
    assert data["total"] == 7
    assert len(data["hits"]) == 5
    assert "truncated" in data["warnings"]


def test_parse_text_valida_el_codi() -> None:
    with pytest.raises(UnexpectedResponseError, match="8.3.3"):
        parse_text(
            {"codiText": "28.1", "titol": "T", "contingut": "<p>text</p>"},
            font=FONT,
            expected="8.3.3",
        )


def test_parse_text_accepta_el_codi_esperat() -> None:
    data = parse_text(
        {"codiText": "8.3.3", "titolText": "T", "contingut": "<p>text</p>"},
        font=FONT,
        expected="8.3.3",
    )
    assert data["codi_text"] == "8.3.3"
    assert data["url"] == "https://giec.iec.cat/textgramatica/codi/8.3.3"


@pytest.mark.parametrize("codi", [None, "", "  "])
def test_parse_text_sense_codi_no_es_pot_verificar(codi) -> None:
    with pytest.raises(UnexpectedResponseError, match="no identifica"):
        parse_text(
            {"codiText": codi, "titol": "T", "contingut": "<p>text</p>"},
            font=FONT,
            expected="8.3.3",
        )
