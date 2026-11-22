"""Normalització de text provinent d'HTML."""

from __future__ import annotations

import html
import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)
_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str:
    """Neteja entitats, espais d'amplada zero i espais repetits."""

    if not value:
        return ""
    text = html.unescape(value)
    text = text.translate(_ZERO_WIDTH)
    text = text.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")
    text = unicodedata.normalize("NFC", text)
    text = _WHITESPACE.sub(" ", text)
    # Els tags en línia de l'HTML poden deixar espais artificials.
    text = re.sub(r"(?<=\w)\s*['’]\s*(?=\w)", "'", text)
    text = re.sub(r"\s+:", ":", text)
    return text.strip()


def strip_tags(value: str) -> str:
    return clean_text(_TAGS.sub(" ", value))


def clean_lines(value: str | None) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [line.strip() for line in re.split(r"\s{2,}|\n", text) if line.strip()]


def normalize_key(value: str) -> str:
    """Clau de comparació: minúscules, sense accents, sense puntuació externa."""

    text = unicodedata.normalize("NFD", clean_text(value).casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)
    return _WHITESPACE.sub(" ", text)


def normalize_exact_key(value: str) -> str:
    """Clau de comparació que conserva els accents: minúscules i espais."""

    return _WHITESPACE.sub(" ", clean_text(value).casefold()).strip()


def contains_words(haystack: str, needle: str) -> bool:
    """Comprova si una paraula o una frase apareix com a paraules senceres."""

    hay = normalize_key(haystack)
    needle_key = normalize_key(needle)
    if not hay or not needle_key:
        return False
    return re.search(rf"(?<!\w){re.escape(needle_key)}(?!\w)", hay) is not None


def split_alternatives(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]
