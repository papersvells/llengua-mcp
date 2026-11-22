from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.collocacions import parse_collocacions

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_collocacions() -> None:
    data = parse_collocacions((FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8"))
    assert data["echo"] == "somriure"
    assert data["layout"] == "lema"
    assert data["status"] == "ok"
    assert data["total"] == 1159
    assert data["counted_rows"] == 4
    assert data["excluded_rows"] == 1

    by_category = {cat["codi"]: cat for cat in data["categories"]}
    assert set(by_category) == {"V", "S"}
    assert by_category["V"]["categoria"] == "verb"
    assert by_category["V"]["rows"] == 2
    assert by_category["V"]["items"] == [
        {"lema": "va", "pos": "VA", "freq": 2192},
        {"lema": "fer", "pos": "V", "freq": 760},
    ]
    assert by_category["S"]["categoria"] == "nom"
    assert by_category["S"]["items"][0] == {"lema": "llavi", "pos": "M", "freq": 235}

    # La puntuació d'ALT no és cap col·locació.
    assert data["altres"] == {"rows": 0, "items": []}


def test_parse_collocacions_no_trunca_i_separa_altres() -> None:
    data = parse_collocacions((FIXTURES / "collocacions_moltes.html").read_text(encoding="utf-8"))
    by_category = {cat["codi"]: cat for cat in data["categories"]}
    assert by_category["V"]["rows"] == 12
    assert len(by_category["V"]["items"]) == 12
    assert data["altres"]["rows"] == 1
    assert data["altres"]["items"] == [{"lema": "joan", "freq": 9}]
    assert data["counted_rows"] == 13
    assert data["excluded_rows"] == 1


def test_sense_seccions_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_collocacions("<html><body>error intern</body></html>")


def test_parse_collocacions_forma() -> None:
    data = parse_collocacions(
        (FIXTURES / "collocacions_forma_somriures.html").read_text(encoding="utf-8")
    )
    assert data["status"] == "ok"
    assert data["layout"] == "forma"
    assert data["echo"] == "somriures"
    assert data["total"] == 80
    assert data["excluded_rows"] == 2

    by_category = {cat["codi"]: cat for cat in data["categories"]}
    assert "S" in by_category
    first = by_category["S"]["items"][0]
    assert first["lema"] == "reverència"
    assert first["pos"] == "F"
    assert first["freq"] == 6
    assert first["info_mutua"] == 11.3028
    assert first["distancia"] == -0.25 or isinstance(first["distancia"], float)
    assert first["freq_lema"] > 0
    assert set(first) >= {"info_mutua", "freq", "distancia", "varianca", "freq_lema"}


@pytest.mark.parametrize(
    "fixture",
    ["collocacions_moltes.html", "collocacions_forma_somriures.html"],
)
def test_limit_conserva_recomptes_i_nomes_materialitza_elements_retornats(
    fixture: str, monkeypatch
) -> None:
    import llengua_mcp.parsers.collocacions as parser

    html = (FIXTURES / fixture).read_text(encoding="utf-8")
    full = parse_collocacions(html)
    original = parser._item
    calls = 0

    def counted_item(term, cells):
        nonlocal calls
        calls += 1
        return original(term, cells)

    monkeypatch.setattr(parser, "_item", counted_item)
    limited = parse_collocacions(html, limit=1)
    assert limited == {
        **full,
        "categories": [
            {**category, "items": category["items"][:1]} for category in full["categories"]
        ],
        "altres": {**full["altres"], "items": full["altres"]["items"][:1]},
    }
    assert calls == sum(len(category["items"]) for category in limited["categories"]) + len(
        limited["altres"]["items"]
    )


def test_detecta_format_despres_del_limit() -> None:
    html = """<div id="V">Coincident amb <i>mot</i> + <b>verb</b></div>
    <a class="lnkU">primer V</a></td><td>1</td>
    <a class="lnkU">segon V</a></td><td>1</td><td>2</td>
    <a class="lnkU">,</a></td><td>3</td>"""
    data = parse_collocacions(html, limit=1)
    assert data["layout"] == "forma"
    assert data["categories"][0]["rows"] == 2
    assert data["excluded_rows"] == 1


def test_parse_collocacions_sense_resultats_es_buit() -> None:
    data = parse_collocacions(
        (FIXTURES / "collocacions_forma_zero.html").read_text(encoding="utf-8")
    )
    assert data["status"] == "empty"
    assert data["echo"] is None
    assert data["total"] is None
    assert data["categories"] == []
