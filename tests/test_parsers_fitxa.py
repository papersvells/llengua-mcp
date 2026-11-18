from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.fitxa import parse_fitxa

FIXTURES = Path(__file__).parent / "fixtures"


def test_fitxa_metadata_title_and_context() -> None:
    parsed = parse_fitxa((FIXTURES / "ctilc_fitxa.html").read_text(encoding="utf-8"))
    assert parsed["work"]["title"] == "Narracions del Delta"
    assert parsed["work"]["author"] == "Juan Arbó, Sebastià"
    assert parsed["work"]["year"] == 1965
    assert parsed["work"]["id"] == "8"
    assert parsed["stats"] == {"occurrences": 60491, "lemmas": 4100, "forms": 6828}
    assert parsed["occurrence"]["lemma"] == "somriure"
    assert parsed["occurrence"]["morphology"] == "3II"
    assert parsed["occurrence"]["position"] == 143446
    assert parsed["nucleus"] == "somreia"
    assert parsed["left"].startswith("Ella, la tavernera")
    assert parsed["right"].startswith("afalagada")
    assert parsed["warnings"] == []
