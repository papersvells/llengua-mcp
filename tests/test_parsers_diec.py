from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.diec import parse_accepcio, parse_search

FIXTURES = Path(__file__).parent / "fixtures"


def test_diec_search() -> None:
    parsed = parse_search((FIXTURES / "diec_search.html").read_text(encoding="utf-8"))
    assert parsed["count"] == 1
    assert parsed["matched_entry"] == "maliciós"
    assert parsed["entries"] == [{"id": "0021272", "entry": "maliciós"}]


def test_diec_accepcio() -> None:
    parsed = parse_accepcio((FIXTURES / "diec_accepcio.html").read_text(encoding="utf-8"))
    assert parsed["title"] == "maliciós -osa"
    assert len(parsed["senses"]) == 3
    first, second, third = parsed["senses"]
    assert first["number"] == "1"
    assert first["pos"] == "adj."
    assert first["definition"] == "Inclinat a pensar mal."
    assert first["labels"] == ["[LC]"]
    assert second["definition"].startswith("Fet amb malícia")
    assert third["examples"] == ["Un somriure maliciós."]
