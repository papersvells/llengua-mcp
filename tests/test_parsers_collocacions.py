from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.collocacions import parse_collocacions

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_collocacions() -> None:
    data = parse_collocacions((FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8"))
    assert data["lema_echo"] == "somriure"
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
