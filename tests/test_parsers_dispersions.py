from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.dispersions import parse_cronologia, parse_dialectal, parse_general

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_cronologia() -> None:
    data = parse_cronologia((FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8"))
    assert data["pattern_echo"] == "somriure adj:-"
    assert data["search_total"] == 2136
    assert len(data["periods"]) == 10
    assert data["totals"] == {"hits": 2136, "corpus_units": 126604218}
    assert data["totals_match_search"] is True

    first = data["periods"][0]
    assert first["label"] == "1832-1913"
    assert first["from_year"] == 1832
    assert first["to_year"] == 1913
    assert first["hits"] == 45
    assert first["corpus_units"] == 13001158
    assert first["per_million"] == 3.46

    last = data["periods"][-1]
    assert last["per_million"] == 24.11

    assert data["peak_absolute"] == {"label": "2021-2022", "hits": 307}
    assert data["peak_relative"]["label"] == "2021-2022"
    assert data["peak_relative"]["per_million"] == 24.11


def test_percentatge_del_graf_no_es_fa_servir() -> None:
    data = parse_cronologia((FIXTURES / "dispersio_cron.html").read_text(encoding="utf-8"))
    # La taxa es deriva dels enters, no del percentatge arrodonit del gràfic.
    first = data["periods"][0]
    assert first["per_million"] == round(45 / 13001158 * 1_000_000, 2)


def test_tram_amb_ocurrències_i_denominador_zero_es_error() -> None:
    html = (
        "<script>var chartData = [['Grup cronològic','Proporció'],"
        "['x'],"
        "['1832-1913',0.1,'1832-1913\\nTotal tram a la cerca: 45"
        "\\nTotal tram al corpus: 0\\n0,1%']];</script>"
    )
    with pytest.raises(UnexpectedResponseError, match="zero paraules"):
        parse_cronologia(html)


def test_tram_zero_sobre_zero_no_participa_al_pic_relatiu() -> None:
    html = (
        "<script>var chartData = [['Grup cronològic','Proporció']"
        ",['1832-1913',0,'1832-1913\\nTotal tram a la cerca: 0"
        "\\nTotal tram al corpus: 0\\n0%']"
        ",['1914-1933',0,'1914-1933\\nTotal tram a la cerca: 1"
        "\\nTotal tram al corpus: 1000000\\n0%']];</script>"
    )
    data = parse_cronologia(html)
    assert data["periods"][0]["per_million"] is None
    assert data["periods"][1]["per_million"] == 1.0
    assert data["peak_relative"] == {"label": "1914-1933", "per_million": 1.0}


def test_pic_relatiu_null_si_cap_tram_te_taxa_calculable() -> None:
    html = (
        "<script>var chartData = [['Grup cronològic','Proporció']"
        ",['1832-1913',0,'1832-1913\\nTotal tram a la cerca: 0"
        "\\nTotal tram al corpus: 0\\n0%']];</script>"
    )
    data = parse_cronologia(html)
    assert data["periods"][0]["per_million"] is None
    assert data["peak_relative"] is None


def test_sense_grafic_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_cronologia("<html><body>error intern</body></html>")


def test_tram_sense_numerador_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_cronologia(
            "<script>var chartData = [['x'],['1832-1913',0.1,'sense tooltip']];</script>"
        )


def test_parse_dialectal() -> None:
    data = parse_dialectal((FIXTURES / "dispersio_dialectal.html").read_text(encoding="utf-8"))
    assert data["pattern_echo"] == "somriure adj:-"
    assert data["search_total"] == 2136
    assert data["index"] == 0.869372
    assert len(data["varieties"]) == 6
    assert data["totals"] == {"query_hits": 2136, "corpus_hits": 126604218}
    assert data["totals_match_search"] is True

    central = next(item for item in data["varieties"] if item["label"] == "central")
    assert central["query_hits"] == 1237
    assert central["corpus_hits"] == 91587052
    assert central["per_million"] == round(1237 / 91587052 * 1_000_000, 2)
    assert central["share_of_query"] == round(1237 / 2136 * 100, 2)
    assert central["share_of_corpus"] == round(91587052 / 126604218 * 100, 2)

    algueres = next(item for item in data["varieties"] if item["label"] == "alguerès")
    assert algueres["query_hits"] == 0
    assert algueres["per_million"] == 0.0

    assert data["peak_absolute"] == {"label": "central", "query_hits": 1237}
    assert data["peak_relative"]["label"] == "baleàric"


def test_dialectal_sense_grafic_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_dialectal("<html><body>error intern</body></html>")


def test_dialectal_sense_tooltip_es_error() -> None:
    html = (
        "<script>var chartData = [['Varietat','Proporció'],"
        "['central',0.001,'sense tooltip']];</script>"
    )
    with pytest.raises(UnexpectedResponseError):
        parse_dialectal(html)


def test_parse_general() -> None:
    data = parse_general((FIXTURES / "dispersio_general.html").read_text(encoding="utf-8"))
    assert data["pattern_echo"] == "somriure adj:-"
    assert data["search_total"] == 2136
    assert data["totals"] == {"query_hits": 2136, "corpus_hits": 126604218}
    assert data["totals_match_search"] is True
    assert data["warnings"] == []
    assert set(data["attributes"]) == {
        "any",
        "varietat",
        "traduccio",
        "tipus",
        "genere",
        "classificacio",
    }

    any_axis = data["attributes"]["any"]
    assert any_axis["index"] == 0.875092
    assert len(any_axis["groups"]) == 10
    assert any_axis["groups"][0]["query_hits"] == 45
    assert any_axis["groups"][0]["per_million"] == 3.46
    assert any_axis["peak_absolute"] == {"label": "2021-2022", "query_hits": 307}

    varietat = data["attributes"]["varietat"]
    assert len(varietat["groups"]) == 6
    algueres = next(group for group in varietat["groups"] if group["label"] == "Alguerès")
    assert algueres["query_hits"] == 0
    assert varietat["peak_relative"]["label"] == "Baleàric"

    assert data["attributes"]["genere"]["totals"]["query_hits"] == 1932
    assert data["attributes"]["classificacio"]["totals"]["query_hits"] == 204
    assert data["attributes"]["classificacio"]["index"] == 0.726303


def test_general_sense_grafic_es_error() -> None:
    with pytest.raises(UnexpectedResponseError):
        parse_general("<html><body>error intern</body></html>")


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (
            "['Central', 1237, 'x', llistacolorsVar['central']]",
            "['Central', 1238, 'x', llistacolorsVar['central']]",
        ),
        (
            "['Assaig', 100, 'x', llistacolorsGen['Assaig']]",
            "['Assaig', 101, 'x', llistacolorsGen['Assaig']]",
        ),
        (
            "['Traducció', 237, 'x', llistacolorsTrad['Traducció']]",
            "['Traducció', 238, 'x', llistacolorsTrad['Traducció']]",
        ),
    ],
)
def test_general_eix_desquadrat(original, replacement) -> None:
    html = (FIXTURES / "dispersio_general.html").read_text(encoding="utf-8")
    assert original in html
    data = parse_general(html.replace(original, replacement))
    assert "attribute_totals_mismatch" in data["warnings"]
