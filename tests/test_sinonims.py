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


def test_context_prioritza_l_etiqueta_de_sentit(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adj (cel): ras, serè, clar\n-adj (color): alegre, viu, clar\n-adj: net, clar\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    result = index.lookup("clar", context="El cel és clar")
    assert result["status"] == "ok"
    assert result["context_ranked"] is True
    assert result["context_matches"] == 1
    first = result["groups"][0]
    assert first["context"] == "cel"
    assert first["context_score"] == 2
    assert first["context_match"] == ["etiqueta"]
    assert "context_no_match" not in result["warnings"]


def test_context_sense_coincidencia_ho_avisa(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adj (cel): ras, serè, clar\n-adj (color): alegre, viu, clar\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    result = index.lookup("clar", context="Una cosa qualsevol")
    assert result["context_matches"] == 0
    assert "context_no_match" in result["warnings"]
    assert all(group["context_score"] == 0 for group in result["groups"])


def test_context_pot_coincidir_amb_una_forma(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-v: anar darrere, esperar\n-v: desitjar, esperar\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    result = index.lookup("esperar", context="Va anar darrere d'ell")
    first = result["groups"][0]
    assert first["context_score"] == 2
    assert first["context_match"] == ["forma"]
    assert {item["form"] for item in first["synonyms"]} == {"anar darrere"}


def test_context_no_confon_una_etiqueta_amb_un_tros_de_mot(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adj (cel): ras, clar\n-adj (color): viu, clar\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)
    result = index.lookup("clar", context="Un excel·lent vestit")
    assert result["context_matches"] == 0
    assert "context_no_match" in result["warnings"]


def test_mes_i_mes_no_comparteixen_grups(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-conj: però, mes, emperò\n"
        "-n: mes, mesada\n"
        "-adv: més, pus\n"
        "-adv: cada vegada més, més i més\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)

    mes = index.lookup("mes", limit=10)
    assert mes["match"] == "exact"
    assert "accent_insensitive_match" not in mes["warnings"]
    assert {group["pos"] for group in mes["groups"]} == {"conj", "n"}

    mes_accent = index.lookup("més", limit=10)
    assert mes_accent["match"] == "exact"
    assert {group["pos"] for group in mes_accent["groups"]} == {"adv"}


def test_dona_i_dona_queden_separats(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-n: dona, senyora\n-v: dóna, obsequia\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)

    dona = index.lookup("dona")
    assert dona["match"] == "exact"
    assert {group["pos"] for group in dona["groups"]} == {"n"}

    dona_verb = index.lookup("dóna")
    assert dona_verb["match"] == "exact"
    assert {group["pos"] for group in dona_verb["groups"]} == {"v"}


def test_cerca_sense_accents_avisa_de_la_coincidencia_aproximada(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text("-n: opinió, parer\n", encoding="utf-8")
    index = SinonimsIndex(tmp_path)
    result = index.lookup("opinio")
    assert result["status"] == "ok"
    assert result["match"] == "accent_insensitive"
    assert "accent_insensitive_match" in result["warnings"]
    assert {item["form"] for item in result["groups"][0]["synonyms"]} == {"parer"}


def test_cerca_amb_accent_inesistent_no_cau_a_la_variant_sense_accent(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text("-n: mes, mesada\n", encoding="utf-8")
    index = SinonimsIndex(tmp_path)
    result = index.lookup("més")
    assert result["status"] == "no_results"
    assert result["match"] is None


def test_comes_escapades_formen_un_sol_terme(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-adv: cada vegada més, com més va\\, més, més i més, cada volta més\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)

    result = index.lookup("cada vegada més", limit=10)
    forms = [item["form"] for item in result["groups"][0]["synonyms"]]
    assert "com més va, més" in forms
    assert "més i més" in forms
    assert "més" not in forms
    assert all("\\" not in form for form in forms)


def test_dos_punts_escapats_formen_part_del_terme(tmp_path) -> None:
    (tmp_path / "sinonims.txt").write_text(
        "-loc: li diu el mort al degollat\\: qui t'ha fet eixe forat?, "
        "cap geperut no es veu la gepa\n",
        encoding="utf-8",
    )
    index = SinonimsIndex(tmp_path)

    result = index.lookup("li diu el mort al degollat: qui t'ha fet eixe forat?", limit=10)
    forms = [item["form"] for item in result["groups"][0]["synonyms"]]
    assert "cap geperut no es veu la gepa" in forms
    assert all("\\" not in form for form in forms)
