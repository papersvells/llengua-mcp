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


def test_parse_collocacions_sense_resultats_es_buit() -> None:
    data = parse_collocacions(
        (FIXTURES / "collocacions_forma_zero.html").read_text(encoding="utf-8")
    )
    assert data["status"] == "empty"
    assert data["echo"] is None
    assert data["total"] is None
    assert data["categories"] == []
