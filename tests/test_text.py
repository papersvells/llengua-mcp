from __future__ import annotations

from llengua_mcp.text import clean_text, contains_words, normalize_key


def test_clean_text_repairs_inline_tag_spacing() -> None:
    assert clean_text("Perífrasi d ' obligació : haig de") == "Perífrasi d'obligació: haig de"
    assert clean_text("l' home") == "l'home"


def test_clean_text_removes_zero_width_and_nbsp() -> None:
    assert clean_text("somreia\u200b\u00a0agraïda") == "somreia agraïda"


def test_normalize_key() -> None:
    assert normalize_key("  Maliciós ") == "malicios"


def test_contains_words() -> None:
    assert contains_words("El cel és clar", "cel")
    assert not contains_words("Un excel·lent vestit", "cel")
    assert contains_words("No és acceptable tenir que + infinitiu", "tenir que")
    assert not contains_words("important", "tant")
