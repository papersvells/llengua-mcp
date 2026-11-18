from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.collocacions import parse_collocacions

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_collocacions() -> None:
    data = parse_collocacions((FIXTURES / "collocacions_somriure.html").read_text(encoding="utf-8"))
    assert data["lema"] == "somriure"
    assert data["total"] == 1159
    assert data["counted_rows"] == 4

    by_category = {cat["codi"]: cat for cat in data["categories"]}
    assert set(by_category) == {"V", "S"}
    assert by_category["V"]["categoria"] == "verb"
    assert by_category["V"]["items"] == [
        {"lema": "va", "pos": "VA", "freq": 2192},
        {"lema": "fer", "pos": "V", "freq": 760},
    ]
    assert by_category["S"]["categoria"] == "nom"
    assert by_category["S"]["items"][0] == {"lema": "llavi", "pos": "M", "freq": 235}


def test_sense_seccions_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_collocacions("<html><body>error intern</body></html>")
