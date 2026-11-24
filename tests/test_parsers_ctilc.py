from __future__ import annotations

from pathlib import Path

import pytest

from llengua_mcp.parsers.ctilc import parse_ctilc_page

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_two_rows_and_echo() -> None:
    expected = {"00*lema": "somriure", "01*cg": "adj:-"}
    page = parse_ctilc_page(_html("ctilc_two_rows.html"), expected=expected)
    assert page.total == 3
    assert page.pattern_echo == "somriure adj:-"
    assert page.echo_verified is True
    assert len(page.occurrences) == 3
    assert "parse_partial" in page.warnings
    assert page.server_fields["resultat"] == "179500525152020580"
    assert page.server_fields["Qlocali"] == "3"


@pytest.mark.parametrize("counter", ["2136", "2.136", "1.234.567"])
def test_comptador_accepta_enters_amb_i_sense_separadors(counter: str) -> None:
    html = _html("ctilc_two_rows.html").replace(
        "total</b>:&nbsp;&nbsp;3", f"total</b>:&nbsp;&nbsp;{counter}"
    )
    page = parse_ctilc_page(html)
    assert page.total == int(counter.replace(".", ""))
    assert "counter_invalid" not in page.warnings


@pytest.mark.parametrize("counter", ["0,5", "0.000", "0.", "1.23", "0 5", "0 pendent", "-0"])
def test_comptador_invalid_no_accepta_un_prefix_valid(counter: str) -> None:
    html = _html("ctilc_zero.html").replace(
        "total</b>:&nbsp;&nbsp;0", f"total</b>:&nbsp;&nbsp;{counter}"
    )
    page = parse_ctilc_page(html)
    assert page.total is None
    assert page.explicit_zero is False
    assert "counter_invalid" in page.warnings
    assert page.pattern_echo == "somriure (amb | de) mala fe"


def test_nucleus_cleanup_and_ids() -> None:
    page = parse_ctilc_page(
        _html("ctilc_two_rows.html"),
        expected={"00*lema": "somriure", "01*cg": "adj:-"},
    )
    first = page.occurrences[0]
    assert first.nucleus == "somreia afalagada"
    assert first.occurrence_id == "558397"
    assert first.obra_param == "6"
    assert first.seccio == "CTILC1"
    assert first.nucleus_tokens == ["somreia", "afalagada"]

    second = page.occurrences[1]
    assert "\u200b" not in second.nucleus
    assert second.nucleus == "somreia agraïda"
    assert "\xa0" not in page.occurrences[2].nucleus


def test_echo_mismatch_is_detected() -> None:
    page = parse_ctilc_page(
        _html("ctilc_two_rows.html"),
        expected={"00*lema": "somriure", "02*cg": "adj:-"},
    )
    assert page.echo_verified is False
    assert "pattern_echo_unexpected" in page.warnings


def test_zero_page() -> None:
    expected = {
        "00*lema": "somriure",
        "01*forma": "amb|de",
        "02*forma": "mala",
        "03*forma": "fe",
    }
    page = parse_ctilc_page(_html("ctilc_zero.html"), expected=expected)
    assert page.total == 0
    assert page.occurrences == []
    assert page.zero_message
    assert "No s'han trobat" in page.zero_message
    assert page.echo_verified is True
    assert page.has_results_container is False


def test_missing_formdata_is_not_verified() -> None:
    page = parse_ctilc_page(
        "<html><body><div id='cHTML1'>res</div></body></html>",
        expected={"00*forma": "x"},
    )
    assert page.echo_verified is False
    assert "pattern_echo_unexpected" in page.warnings


def test_zero_page_without_chtml1_container() -> None:
    expected = {
        "00*forma": "somriure",
        "01*forma": "de",
        "02*forma": "mala",
        "03*forma": "fe",
    }
    page = parse_ctilc_page(_html("ctilc_zero_no_header.html"), expected=expected)
    assert page.total == 0
    assert page.pattern_echo == "somriure de mala fe"
    assert page.echo_verified is True
    assert page.explicit_zero is True
    assert page.zero_message


def test_zero_page_with_an_unrecognized_warning_is_not_verified() -> None:
    html = _html("ctilc_zero.html")
    html = html.replace(
        "No s'han trobat ocurrències per al patró seleccionat: somriure (amb | de) mala fe",
        "Servei temporalment indisponible",
    )
    expected = {
        "00*lema": "somriure",
        "01*forma": "amb|de",
        "02*forma": "mala",
        "03*forma": "fe",
    }
    page = parse_ctilc_page(html, expected=expected)

    assert page.total == 0
    assert page.explicit_zero is False
    assert page.zero_message == "Servei temporalment indisponible"
    assert "zero_unverified" in page.warnings


def test_filtered_page_uses_filtered_total_and_echo() -> None:
    html = _html("ctilc_two_rows.html")
    html = html.replace(
        "Freqüència total</b>:&nbsp;&nbsp;3", "Freqüència total</b>:&nbsp;&nbsp;2136"
    )
    filter_table = (
        '<center><table class="tableFILTREStop"><tr><td width="75%">'
        "<b>Filtre per varietat</b>: central</td>"
        "<td><b>Quantitat filtrada</b>:&nbsp;&nbsp;1237</td></tr></table></center>"
    )
    html = html.replace('</div>\n<div id="cHTML2">', filter_table + '</div>\n<div id="cHTML2">')
    html = html.replace(
        "</body>", '<input type="hidden" name="varSelec" value="@central" /></body>'
    )

    page = parse_ctilc_page(
        html,
        expected={"00*lema": "somriure", "01*cg": "adj:-"},
    )
    assert page.total == 1237
    assert page.total_unfiltered == 2136
    assert page.filtered_total == 1237
    assert page.filters_echo == {"varSelec": "@central"}
    assert page.filters_summary == ["varietat: central"]


def test_patterns_equivalent_handles_display_variants() -> None:
    from llengua_mcp.parsers.ctilc import patterns_equivalent

    assert patterns_equivalent("somriure (amb | de) mala fe", "somriure amb|de mala fe")
    assert patterns_equivalent("somriure []? mala fe", "somriure (qualsevol) mala fe")
    assert patterns_equivalent("somriure <> (amb | de)", "somriure <>amb|de")
    assert patterns_equivalent("somriure subst", "somriure@subst")
    assert not patterns_equivalent("cantar", "somriure mala fe")
