"""Parsers de les cerques bàsiques del CTILC (`Formes2` i `FormesLema2`).

Aquestes pàgines no tenen «Patró seleccionat»: mostren un encapçalament
(`Forma : Coincident amb …` o `Lema : …`), un panell de formes amb recompte i
una taula de concordances amb tres cel·les (esquerra, paraula clau, dreta).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text

_HEADER_RE = re.compile(
    r"(?P<label>Forma|Lema|Lemes)\s*:\s*(?P<echo>.*?)\s*Freqüència total\s*:\s*(?P<total>[\d.]+)",
    re.DOTALL,
)
_PAGE_RE = re.compile(r"Pàgina\s+(\d+)\s+\(de\s+(\d+)\)")
_ZERO_FORMA = "no hi ha cap forma que compleixi"
_ZERO_LEMA = "no hi ha cap lema que compleixi"
_COUNT_RE = re.compile(r"([\d.]+)\s*oc\.")
_PARAM_RE = re.compile(r"[?&](?P<key>id|obra)=(?P<value>\d+)")


def _int(value: str) -> int:
    return int(re.sub(r"[^\d]", "", value))


def _query_params(value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for match in _PARAM_RE.finditer(unquote(value)):
        params.setdefault(match.group("key"), match.group("value"))
    return params


def _forms(doc: HTMLParser, *, kind: str) -> tuple[list[dict[str, Any]], list[str]]:
    forms: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()

    for row in doc.css("tr"):
        node = row.css_first('input[name="formesSelec"]')
        if node is None:
            continue
        raw = clean_text(node.attributes.get("value") or "").strip("@")
        parts = raw.split("|")
        if len(parts) != 3:
            warnings.append("parse_partial")
            continue
        if kind == "forma":
            form, lemma_cat, morphology = (clean_text(part) for part in parts)
        else:
            lemma_cat, form, morphology = (clean_text(part) for part in parts)
        lemma, _, category = lemma_cat.rpartition(" ")
        if not lemma:
            lemma, category = lemma_cat, ""
        if not form:
            warnings.append("parse_partial")
            continue
        count_match = _COUNT_RE.search(clean_text(row.text(separator=" ")))
        count = _int(count_match.group(1)) if count_match else None
        key = (lemma, category, form, morphology)
        if key in seen:
            continue
        seen.add(key)
        forms.append(
            {
                "lemma": lemma,
                "category": category,
                "form": form,
                "morphology": morphology,
                "count": count,
            }
        )
    return forms, warnings


def _occurrences(doc: HTMLParser) -> tuple[list[dict[str, Any]], list[str]]:
    occurrences: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()

    container = doc.css_first("#cHTML2") or doc
    for row in container.css("tr"):
        cells = row.css("td")
        if len(cells) != 3:
            continue
        link = cells[1].css_first("a.pclau")
        if link is None:
            continue
        params = _query_params(link.attributes.get("onclick") or "")
        if not params:
            params = _query_params(link.attributes.get("href") or "")
        occurrence_id = params.get("id")
        if occurrence_id:
            if occurrence_id in seen:
                continue
            seen.add(occurrence_id)
        nucleus = clean_text(cells[1].text(separator=""))
        occurrences.append(
            {
                "left": clean_text(cells[0].text(separator="")),
                "nucleus": nucleus,
                "nucleus_tokens": nucleus.split(),
                "right": clean_text(cells[2].text(separator="")),
                "occurrence_id": occurrence_id,
                "obra_param": params.get("obra"),
                "seccio": "CTILC1",
            }
        )
    if not occurrences:
        warnings.append("parse_partial")
    return occurrences, warnings


def parse_basiques(html: str, *, kind: str) -> dict[str, Any]:
    """Parseja una pàgina de ``Formes2.asp`` o ``FormesLema2.asp``."""

    doc = HTMLParser(html)
    body_text = clean_text(doc.body.text(separator=" ") if doc.body else "")
    zero_text = _ZERO_FORMA if kind == "forma" else _ZERO_LEMA
    explicit_zero = zero_text in body_text.casefold()

    match = _HEADER_RE.search(body_text)
    echo = ""
    total: int | None = None
    if match:
        echo = clean_text(match.group("echo"))
        total = _int(match.group("total"))
    if explicit_zero:
        total = 0

    page = pages = None
    page_match = _PAGE_RE.search(body_text)
    if page_match:
        page = int(page_match.group(1))
        pages = int(page_match.group(2))

    forms, form_warnings = _forms(doc, kind=kind)
    occurrences, occurrence_warnings = _occurrences(doc)
    warnings = form_warnings + occurrence_warnings
    if explicit_zero:
        warnings = [warning for warning in warnings if warning != "parse_partial"]
    if total is None and not explicit_zero:
        warnings.append("parse_partial")

    return {
        "kind": kind,
        "echo": echo,
        "total": total,
        "page": page,
        "pages": pages,
        "forms": forms,
        "occurrences": occurrences,
        "explicit_zero": explicit_zero,
        "warnings": list(dict.fromkeys(warnings)),
    }


__all__ = ["parse_basiques"]
