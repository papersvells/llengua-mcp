from __future__ import annotations

import pytest

from llengua_mcp.errors import DataUnavailableError
from llengua_mcp.sinonims import SinonimsIndex


def test_lookup_and_annotations(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adj: maliciós, mordaç, sorneguer (col·loquial), burleta (antònim)\n-n: mofeta, burleta\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    result = index.lookup("maliciós")
    assert result["status"] == "ok"
    group = result["groups"][0]
    assert group["pos"] == "adj"
    forms = [item["form"] for item in group["synonyms"]]
    assert "mordaç" in forms
    assert "sorneguer" in forms
    assert group["synonyms"][1]["note"] == "col·loquial"
    assert group["antonyms"][0]["form"] == "burleta"


def test_expression_is_not_split_into_components(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text("-n: fe, creença\n", encoding="utf-8")
    index = SinonimsIndex(tmp_path)
    result = index.lookup("de mala fe")
    assert result["status"] == "no_results"
    assert result["groups"] == []
    assert "No se n'han buscat els components" in result["note"]


def test_missing_data_is_actionable(tmp_path) -> None:
    index = SinonimsIndex(tmp_path)
    with pytest.raises(DataUnavailableError) as excinfo:
        index.lookup("maliciós")
    assert "fetch_sinonims" in excinfo.value.hint


def test_antonym_is_not_offered_as_synonym(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adj (cel): ras, serè, clar, ennuvolat (antònim)\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    antonym = index.lookup("ennuvolat")
    group = antonym["groups"][0]
    assert group["relation"] == "antonym"
    assert group["synonyms"] == []
    assert {item["form"] for item in group["antonyms"]} == {"ras", "serè", "clar"}

    synonym = index.lookup("serè")
    group = synonym["groups"][0]
    assert group["relation"] == "synonym"
    assert {item["form"] for item in group["synonyms"]} == {"ras", "clar"}
    assert [item["form"] for item in group["antonyms"]] == ["ennuvolat"]
