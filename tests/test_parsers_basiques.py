from __future__ import annotations

from pathlib import Path

from llengua_mcp.parsers.basiques import parse_basiques

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_forma() -> None:
    data = parse_basiques(
        (FIXTURES / "basiques_forma.html").read_text(encoding="utf-8"), kind="forma"
    )
    assert data["echo"] == "Coincident amb somriu"
    assert data["total"] == 2019
    assert data["page"] == 1
    assert data["pages"] == 41
    assert data["explicit_zero"] is False
    assert data["warnings"] == []

    assert len(data["forms"]) == 3
    assert data["forms"][0] == {
        "lemma": "somriu",
        "category": "M",
        "form": "somriu",
        "morphology": "M:S",
        "count": 13,
    }
    assert data["forms"][1]["lemma"] == "somriure"
    assert data["forms"][1]["category"] == "V"
    assert data["forms"][1]["count"] == 1955

    assert len(data["occurrences"]) == 2
    first = data["occurrences"][0]
    assert first["left"].startswith("Noro")
    assert first["nucleus"] == "somriu"
    assert first["nucleus_tokens"] == ["somriu"]
    assert first["occurrence_id"] == "110080"
    assert first["obra_param"] == "1"


def test_parse_lema() -> None:
    data = parse_basiques(
        (FIXTURES / "basiques_lema.html").read_text(encoding="utf-8"), kind="lema"
    )
    assert data["echo"] == "Coincident amb somriure"
    assert data["total"] == 14290
    assert data["page"] == 1
    assert data["pages"] == 286
    assert len(data["forms"]) == 4
    assert data["forms"][2] == {
        "lemma": "somriure",
        "category": "V",
        "form": "somreia",
        "morphology": "3II",
        "count": 1029,
    }
    assert len(data["occurrences"]) == 2
    assert data["occurrences"][0]["occurrence_id"] == "222222"
    assert data["occurrences"][0]["obra_param"] == "2"


def test_zero_explicit() -> None:
    html = (
        "<html><body>Forma : Coincident amb zzzz Freqüència total : 0 "
        "No hi ha cap forma que compleixi aquestes condicions</body></html>"
    )
    data = parse_basiques(html, kind="forma")
    assert data["total"] == 0
    assert data["explicit_zero"] is True
    assert data["forms"] == []
    assert data["occurrences"] == []
    assert data["warnings"] == []
