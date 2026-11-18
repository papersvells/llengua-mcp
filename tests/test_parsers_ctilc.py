from __future__ import annotations

from pathlib import Path

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
    assert page.zero_message


def test_patterns_equivalent_handles_display_variants() -> None:
    from llengua_mcp.parsers.ctilc import patterns_equivalent

    assert patterns_equivalent("somriure (amb | de) mala fe", "somriure amb|de mala fe")
    assert patterns_equivalent("somriure []? mala fe", "somriure (qualsevol) mala fe")
    assert patterns_equivalent("somriure <> (amb | de)", "somriure <>amb|de")
    assert patterns_equivalent("somriure subst", "somriure@subst")
    assert not patterns_equivalent("cantar", "somriure mala fe")
