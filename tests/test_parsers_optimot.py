from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.optimot import decode_ref, parse_detail, parse_search

FIXTURES = Path(__file__).parent / "fixtures"


def test_search_parsing() -> None:
    parsed = parse_search((FIXTURES / "optimot_search.html").read_text(encoding="utf-8"))
    assert parsed["count"] == 1966
    assert len(parsed["results"]) == 2
    first = parsed["results"][0]
    assert first["title"] == "tindre o tenir?"
    assert first["source"] == "Fitxes de l'Optimot"
    assert "dues formes d'infinitiu" in first["snippet"]
    assert first["detail_available"] is True
    params = decode_ref(first["detail_ref"])
    assert params["idFont"] == "15260"
    assert params["method"] == "detall"
    assert "jsessionid" not in str(params)


def test_detail_parsing() -> None:
    parsed = parse_detail((FIXTURES / "optimot_detail.html").read_text(encoding="utf-8"))
    assert parsed["fitxa_number"] == "6442/3"
    assert parsed["version"] == "17.06.2022"
    assert parsed["title"] == "tindre o tenir?"
    assert parsed["sections"]
    resposta = parsed["sections"][0]
    assert resposta["label"] == "Resposta"
    assert any("registres formals" in item for item in resposta["paragraphs"])
    assert any("tenir que" in item for item in resposta["paragraphs"])
    assert "tenir que" in resposta["text"]
    assert parsed["related"][0]["title"] == "Infinitius amb dues formes"
