from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.oiec import parse_search, parse_text

FIXTURES = Path(__file__).parent / "fixtures"


def _payload() -> list[dict]:
    return [
        {
            "idText": 1,
            "codiText": "4.1",
            "titol": "L’apòstrof",
            "contingut": None,
        },
        {
            "idText": 2,
            "codiText": "4.2.1",
            "titol": "Formació de contraccions",
            "contingut": (
                "<p>Les preposicions <em>a</em>, <em>de</em> i <em>per</em>, quan van "
                "seguides de les formes masculines de l’article definit <em>el</em> i "
                "<em>els</em>, formen les contraccions <em>al</em> i <em>als</em>.</p>"
            ),
        },
        {
            "idText": 3,
            "codiText": "4.1.2b",
            "titol": "Casos particulars en l’ús de l’apòstrof",
            "contingut": "<p>No s’apostrofa davant i o u amb valor semivocàlic.</p>",
        },
    ]


def test_parse_search_prefers_hits_with_content() -> None:
    data = parse_search(_payload(), "apostrofa")
    assert data["total_hits"] == 3
    assert data["returned"] == 2
    codis = [hit["codi_text"] for hit in data["hits"]]
    assert "4.1" not in codis
    assert "4.2.1" in codis
    first = data["hits"][0]
    assert first["titol"] == "Formació de contraccions"
    assert "<em>" not in first["snippet"]
    assert first["url"].startswith("https://oiec.iec.cat/textortografia/")


def test_parse_search_snippet_highlights_the_query() -> None:
    payload = [
        {
            "codiText": "2.4.3",
            "titol": "L’elisió de la ròtica final",
            "contingut": (
                "<p>Text llarg de prova on no apareix la paraula demanada en el cos, "
                "però volem veure que el fragment es retalla pel començament.</p>"
            ),
        }
    ]
    data = parse_search(payload, "rottica-inexistent")
    assert data["hits"][0]["snippet"].endswith("…")


def test_parse_search_rejects_unknown_payload() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_search({"error": "hi ha hagut un problema"}, "paraula")


def test_parse_text() -> None:
    payload = {
        "codiText": "4.1.2b",
        "titolText": "Casos particulars en l’ús de l’apòstrof",
        "contingut": "<p>No s’apostrofa <em>davant</em> i o u.</p>",
        "codiAnterior": "4.1.2a",
        "codiSeguent": "4.1.3",
    }
    data = parse_text(payload)
    assert data["codi_text"] == "4.1.2b"
    assert data["titol"].startswith("Casos particulars")
    assert "<em>" not in data["content"]
    assert data["prev"] == "4.1.2a"
    assert data["next"] == "4.1.3"


def test_parse_text_without_content_is_actionable() -> None:
    with pytest.raises(UnexpectedResponseError, match="llegible"):
        parse_text({"codiText": "4", "titol": "La grafia dels mots", "contingut": None})


def test_hit_url_is_a_working_deep_link() -> None:
    data = parse_search(_payload(), "apostrofa")
    first = data["hits"][0]
    assert first["url"] == "https://oiec.iec.cat/textortografia/4.2.1"
