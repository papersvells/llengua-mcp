from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.obres import parse_authors, parse_works

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_autors() -> None:
    parsed = parse_authors((FIXTURES / "obres_autors.html").read_text(encoding="utf-8"))
    assert parsed["echo"] == "sagarra"
    assert parsed["explicit_zero"] is False
    assert parsed["warnings"] == []
    assert len(parsed["authors"]) == 5
    assert parsed["authors"][0] == {
        "id": "493",
        "name": "Sagarra i de Castellarnau, Ignasi de",
    }


def test_parse_autors_zero() -> None:
    html = (
        '<html><body><input name="autor" value="zzzz">'
        "<center>No hi ha cap autor que respongui al paràmetre introduït</center>"
        "</body></html>"
    )
    parsed = parse_authors(html)
    assert parsed["authors"] == []
    assert parsed["echo"] == "zzzz"
    assert parsed["explicit_zero"] is True
    assert parsed["warnings"] == []


def test_parse_obres() -> None:
    parsed = parse_works((FIXTURES / "obres_resultats.html").read_text(encoding="utf-8"))
    assert parsed["total"] == 3
    assert parsed["echo"] == "vida"
    assert parsed["explicit_zero"] is False
    assert parsed["warnings"] == []
    assert len(parsed["works"]) == 3

    first = parsed["works"][0]
    assert first["author"].startswith("Blat")
    assert first["title"].startswith("¡Un entropesó")
    assert first["year"] == 1931
    assert first["kind"] == "LIT"
    assert first["genre"] == "T"
    assert first["variety"] == "valencià"
    assert first["translation"] is False

    second = parsed["works"][1]
    assert second["kind"] == "NLIT"
    assert second["genre"] is None
    assert second["classification"].startswith("9.9")

    third = parsed["works"][2]
    assert third["translation"] is True


def test_parse_obres_zero() -> None:
    html = (
        "<html><body>"
        '<table class="tableFORMOUT"><tr><td><b>Títol de l\'obra:</b> zzzz</td></tr></table>'
        "No hi ha cap obra que respongui al paràmetre introduït"
        "</body></html>"
    )
    parsed = parse_works(html)
    assert parsed["total"] == 0
    assert parsed["works"] == []
    assert parsed["echo"] == "zzzz"
    assert parsed["explicit_zero"] is True
    assert parsed["warnings"] == []
