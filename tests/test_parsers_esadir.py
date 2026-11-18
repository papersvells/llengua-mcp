from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.esadir import parse_fitxa, parse_search

FIXTURES = Path(__file__).parent / "fixtures"


def test_esadir_search() -> None:
    parsed = parse_search((FIXTURES / "esadir_search.html").read_text(encoding="utf-8"))
    assert parsed["count"] == 6
    assert len(parsed["results"]) == 3
    first = parsed["results"][0]
    assert first["title"] == "El gust de la mort"
    assert first["section"] == "Filmoteca"
    assert first["url"] == "https://www.esadir.cat/filmoteca/fitxa/node/El_gust_de_la_mort"
    rest = parsed["results"][-1]
    assert rest["match"] == "rest"
    assert rest["url"].startswith("https://www.3cat.cat/")


def test_esadir_fitxa() -> None:
    parsed = parse_fitxa((FIXTURES / "esadir_fitxa.html").read_text(encoding="utf-8"))
    assert parsed["found"] is True
    assert parsed["title"] == "hidrosisme"
    assert parsed["labels"] == ["ús general", "no recollit al DIEC"]
    assert parsed["pronunciation"] == [
        {"variety": "or.", "afi": "iðɾusízmə"},
        {"variety": "occ.", "afi": "iðɾosízme"},
    ]
    assert parsed["definitions"]
    assert "Fenomen sísmic" in parsed["definitions"][-1]
    assert all(url.startswith("https://www.esadir.cat/back/") for url in parsed["audio_urls"])
    assert len(parsed["audio_urls"]) == 2
