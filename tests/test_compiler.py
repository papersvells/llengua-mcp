from __future__ import annotations

import pytest

from llengua_mcp.compiler import (
    build_body,
    compile_pattern,
    phrase_elements,
)
from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.models import FormSpec, PatternElement


def test_control_body_has_literal_star() -> None:
    pattern = compile_pattern(
        [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj"),
        ]
    )
    body = pattern.body(start=1, offset=5)
    assert body == "seccio=CTILC1&00*lema=somriure&01*cg=adj%3A-&iStart=1&iOffset=5"
    assert "%2A" not in body
    assert "00*lema=" in body


def test_values_are_encoded_once() -> None:
    pattern = compile_pattern([PatternElement(type="forma", value="50%")])
    body = pattern.body(start=1, offset=10)
    assert "00*forma=50%25" in body


def test_filters_are_appended_once() -> None:
    pattern = compile_pattern([PatternElement(type="lema", value="somriure")])
    body = pattern.body(
        start=1,
        offset=5,
        filters={
            "varSelec": "@nord-occidental",
            "anySelec": "@1960, @1961",
        },
    )
    assert "varSelec=%40nord-occidental" in body
    assert "anySelec=%401960%2C%20%401961" in body
    assert body.index("00*lema") < body.index("varSelec") < body.index("iStart")
    assert "%2525" not in body


def test_cg_without_morphology_becomes_dash() -> None:
    pattern = compile_pattern([PatternElement(type="cg", category="V")])
    assert pattern.fields[0][1] == "V:-"


def test_cg_qualsevol() -> None:
    pattern = compile_pattern([PatternElement(type="qualsevol")])
    assert pattern.fields[0] == ("00*cg", "qualsevol")


def test_negated_and_optional_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match="negated"):
        compile_pattern([PatternElement(type="forma", value="amb", negated=True, optional=True)])


def test_forma_with_spaces_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match="espais"):
        compile_pattern([PatternElement(type="forma", value="somriure mofeta")])


def test_phrase_is_split_per_word() -> None:
    elements = phrase_elements("somriure mofeta")
    assert [element.value for element in elements] == ["somriure", "mofeta"]
    assert all(element.type == "forma" for element in elements)


def test_phrase_too_long_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match="màxim"):
        phrase_elements(" ".join(["mot"] * 11))


def test_negated_alternatives_use_ui_syntax() -> None:
    pattern = compile_pattern(
        [
            PatternElement(
                type="forma",
                value="amb",
                alternatives=["de"],
                negated=True,
            )
        ]
    )
    assert pattern.fields[0][1] == "<>amb|de"


def test_optional_alternatives() -> None:
    pattern = compile_pattern(
        [
            PatternElement(
                type="forma",
                value="amb",
                alternatives=["de"],
                optional=True,
            )
        ]
    )
    assert pattern.fields[0][1] == "(amb|de)"


def test_formalema_grammar() -> None:
    pattern = compile_pattern(
        [
            PatternElement(
                type="formalema",
                value="somriure",
                category="V",
                forms=[
                    FormSpec(form="somriure", cg="IF"),
                    FormSpec(form="somreia", cg="3II"),
                ],
            )
        ]
    )
    assert pattern.fields[0][1] == "somriure:V¬somriure:IF|somreia:3II"
    body = pattern.body(start=1, offset=5)
    assert "%C2%AC" in body
    assert "%7C" in body


def test_lema_with_colon_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match=":"):
        compile_pattern([PatternElement(type="lema", value="somriure:V")])


def test_lema_with_category() -> None:
    pattern = compile_pattern([PatternElement(type="lema", value="somriure", category="subst")])
    assert pattern.fields[0][1] == "somriure@subst"


def test_start_must_be_one_based() -> None:
    with pytest.raises(InvalidQueryError, match="iStart"):
        build_body([("00*forma", "mala")], start=0, offset=10)


def test_too_many_elements() -> None:
    elements = [PatternElement(type="forma", value=f"mot{i}") for i in range(11)]
    with pytest.raises(InvalidQueryError, match="màxim"):
        compile_pattern(elements)


def test_phrase_with_punctuation_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match="puntuació"):
        phrase_elements("Tinc que anar a casa.")


def test_forma_with_punctuation_is_rejected() -> None:
    with pytest.raises(InvalidQueryError, match="puntuació"):
        compile_pattern([PatternElement(type="forma", value="casa.")])
