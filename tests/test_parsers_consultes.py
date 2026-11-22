from __future__ import annotations

import json
from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.consultes import parse_bootstrap, parse_rows

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_bootstrap() -> None:
    data = parse_bootstrap((FIXTURES / "consultes_page.html").read_text(encoding="utf-8"))
    assert data["nonce"] == "abc123def4"
    assert data["table_id"] == "7"
    assert data["themes"] == [
        "Fonètica",
        "Lèxic",
        "Morfologia",
        "Onomàstica",
        "Ortografia",
        "Sintaxi",
        "Altres",
    ]


def test_parse_bootstrap_sense_nonce_es_error() -> None:
    with pytest.raises(UnexpectedResponseError, match="testimoni"):
        parse_bootstrap("<html><body><p>error intern</p></body></html>")


def test_parse_rows() -> None:
    payload = json.loads((FIXTURES / "consultes_rows.json").read_text(encoding="utf-8"))
    data = parse_rows(payload)
    assert data["total"] == 2
    assert data["corpus_total"] == 1176
    assert data["warnings"] == []

    first, second = data["results"]
    assert first["id"] == "5895"
    assert first["tema"] == "Sintaxi"
    assert first["pregunta"] == "Com es diu tenir que anar a casa?"
    assert "<p>" not in first["resposta"]
    assert first["categories"] == ["Sintaxi"]
    assert [ref["title"] for ref in first["references"]] == ["GIEC", "Optimot"]
    assert first["references"][0]["url"] == "https://giec.iec.cat/textgramatica/codi/28.1"
    assert second["tema"] == "Lèxic"
    assert second["origen"] == "Dubte del dia"
    assert second["references"][0]["url"].startswith("https://dlc.iec.cat/")


def test_parse_rows_format_desconegut_es_error() -> None:
    with pytest.raises(UnexpectedResponseError, match="format"):
        parse_rows({"recordsTotal": 1, "recordsFiltered": 1})


def test_parse_rows_fila_mal_formada_avisa() -> None:
    payload = {
        "recordsTotal": 2,
        "recordsFiltered": 2,
        "data": [["5895"], ["5894", "s"]],
    }
    data = parse_rows(payload)
    assert data["results"] == []
    assert "parse_partial" in data["warnings"]


def test_total_sense_comptador_no_es_zero() -> None:
    data = parse_rows({"recordsTotal": 1176, "data": []})
    assert data["total"] is None
    assert data["results"] == []
    assert "records_filtered_missing" in data["warnings"]


def test_total_sense_comptador_amb_files_usa_el_nombre_de_files() -> None:
    payload = json.loads((FIXTURES / "consultes_rows.json").read_text(encoding="utf-8"))
    payload.pop("recordsFiltered")
    data = parse_rows(payload)
    assert data["total"] == 2
    assert "records_filtered_missing" in data["warnings"]
