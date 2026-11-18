from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from llengua_mcp.parsers.bdlex import parse_entries, parse_ids

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ids() -> None:
    ids = parse_ids((FIXTURES / "bdlex_ids.xml").read_text(encoding="utf-8"))
    assert ids == ["DCVBE057199", "DIEeE025487"]


def test_parse_entries() -> None:
    entries = parse_entries((FIXTURES / "bdlex_entries.xml").read_text(encoding="utf-8"))
    assert len(entries) == 2

    dcvb = entries[0]
    assert dcvb["dictionary"] == "DCVB"
    assert dcvb["headword"] == "engrunar"
    assert dcvb["pos"] == "v. tr."
    assert len(dcvb["senses"]) == 1
    sense = dcvb["senses"][0]
    assert sense["number"] == "1."
    assert sense["definition"].startswith("Esclafar; deformar")
    assert sense["translations"] == ["cast. chafar, aplastar."]
    assert len(sense["examples"]) == 2
    assert "Quar. 1413" in sense["examples"][1]
    assert "Maestrat" in sense["regions"]
    assert dcvb["etymology"] == "de enrunar"
    assert dcvb["phonetics"][0]["afi"] == "əŋgɾuná"
    assert dcvb["synonyms"] == ["esclafar;", "esmicolar."]

    diec = entries[1]
    assert diec["dictionary"] == "DIEe"
    assert diec["senses"][0]["number"] == "1.1"
    assert diec["senses"][0]["definition"].startswith("Fer engrunes")


def test_xml_with_unexpected_root_is_rejected() -> None:
    with pytest.raises(ET.ParseError):
        parse_ids("<error>servei no disponible</error>")


def test_senses_truncated_only_when_more_senses_exist() -> None:
    entries = parse_entries(
        (FIXTURES / "bdlex_entries.xml").read_text(encoding="utf-8"),
        max_senses=1,
    )
    assert entries[0]["senses_truncated"] is False


def test_result_with_error_child_is_rejected() -> None:
    with pytest.raises(ET.ParseError):
        parse_ids("<result><error>servei no disponible</error></result>")
