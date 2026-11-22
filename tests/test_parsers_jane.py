from __future__ import annotations

import json
from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.jane import (
    FUNCIO_COLUMNS,
    parse_bootstrap,
    parse_rows,
)

FIXTURES = Path(__file__).parent / "fixtures"
BOOTSTRAP = (FIXTURES / "jane_bootstrap.html").read_text(encoding="utf-8")
LEMA = json.loads((FIXTURES / "jane_rows_lema.json").read_text(encoding="utf-8"))
GENERAL = json.loads((FIXTURES / "jane_rows_general.json").read_text(encoding="utf-8"))
FUNCIO = json.loads((FIXTURES / "jane_rows_funcio.json").read_text(encoding="utf-8"))
ZERO = json.loads((FIXTURES / "jane_zero.json").read_text(encoding="utf-8"))


def test_bootstrap_reads_nonce_and_table() -> None:
    data = parse_bootstrap(BOOTSTRAP)

    assert data == {"nonce": "7425348f4b", "table_id": "1"}


def test_bootstrap_without_nonce_fails() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_bootstrap("<html><body>cap nonce</body></html>")


def test_rows_parse_numbered_senses_and_femenins() -> None:
    data = parse_rows(LEMA)

    assert data["total"] == 1
    assert data["catalog_total"] == 27547
    entry = data["results"][0]
    assert entry["lema"] == "maliciós"
    assert entry["femeni"] == "maliciosa"
    assert entry["categoria"] == "adjectiu i [nom] masculí i femení"
    assert [sense["num"] for sense in entry["sentits"]] == [1, 2]
    assert entry["sentits"][0]["sinonims"] == ["malpensat", "desconfiat", "malfiat"]
    assert entry["sentits"][1]["sinonims"] == ["murri", "trapella", "viu", "caut", "recelós"]
    assert entry["sentits"][1]["femenins"] == ["múrria", "trapella", "viva", "cauta", "recelosa"]


def test_rows_keep_links_to_other_sources() -> None:
    entry = parse_rows(LEMA)["results"][0]

    titles = {link["title"] for link in entry["enllacos"]}
    assert {"DIEC2", "DDLC", "CTILC", "BDlex", "DCVB"} <= titles
    assert all(link["url"].startswith(("http://", "https://")) for link in entry["enllacos"])


def test_general_search_returns_locution_inside_senses() -> None:
    data = parse_rows(GENERAL)

    assert data["total"] == 3
    entries = {entry["lema"]: entry for entry in data["results"]}
    assert "mala fe" in entries["arteria"]["sentits"][0]["sinonims"]
    assert "mala fe" in entries["malícia"]["sentits"][1]["sinonims"]


def test_funcio_rows_use_the_extra_column() -> None:
    data = parse_rows(FUNCIO, columns=FUNCIO_COLUMNS)

    assert data["total"] == 92
    entry = data["results"][0]
    assert entry["lema"] == "ajuntament"
    assert entry["sentits"][0]["num"] == 1
    assert "municipi" in entry["sentits"][1]["sinonims"]
    assert all("femenins" not in sense for sense in entry["sentits"])


def test_zero_is_an_explicit_empty_result() -> None:
    data = parse_rows(ZERO)

    assert data["total"] == 0
    assert data["results"] == []
    assert data["warnings"] == []


def test_malformed_payload_is_rejected() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_rows({"data": "no és una llista"})


def test_short_row_is_reported_as_partial() -> None:
    data = parse_rows({"recordsFiltered": 1, "data": [["només", "dues"]]})

    assert data["results"] == []
    assert "parse_partial" in data["warnings"]


def test_total_sense_comptador_no_es_zero() -> None:
    data = parse_rows({"recordsTotal": 27547, "data": []})

    assert data["total"] is None
    assert data["results"] == []
    assert "records_filtered_missing" in data["warnings"]


def test_total_sense_comptador_amb_files_usa_el_nombre_de_files() -> None:
    payload = dict(LEMA)
    payload.pop("recordsFiltered")
    data = parse_rows(payload)

    assert data["total"] == len(data["results"])
    assert data["total"] > 0
    assert "records_filtered_missing" in data["warnings"]


@pytest.mark.parametrize("comptador", [None, False, 0.4, -1, "1,176", "  "])
def test_comptador_invalid_no_es_un_zero(comptador) -> None:
    data = parse_rows({"recordsTotal": 27547, "recordsFiltered": comptador, "data": []})

    assert data["total"] is None
    assert "records_filtered_invalid" in data["warnings"]


def test_comptador_zero_en_text_es_valid() -> None:
    data = parse_rows({"recordsTotal": 27547, "recordsFiltered": "0", "data": []})

    assert data["total"] == 0
    assert data["warnings"] == []
