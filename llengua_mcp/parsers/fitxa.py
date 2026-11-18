"""Parser de la fitxa de localització d'una ocurrència del CTILC."""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text, strip_tags

_LABEL_RE = re.compile(r"^([^:]{1,40}?)\s*:\s*(.*)$")
_LABELS = (
    "Títol",
    "Autor",
    "Varietat",
    "Any d'edició",
    "Tipus",
    "Classificació",
    "Ocurrències",
    "Lemes",
    "Formes",
    "Lema",
    "Categoria gramatical",
    "Id. obra",
    "Forma",
    "Codi morfològic",
    "Posició dins l'obra",
)
_LABEL_SCAN = re.compile(r"(" + "|".join(re.escape(label) for label in _LABELS) + r")\s*:\s*")


def _scan_labels(text: str) -> dict[str, str]:
    """Llegeix etiquetes encara que no estiguin dins d'un `div.fitxaTD`."""

    fields: dict[str, str] = {}
    matches = list(_LABEL_SCAN.finditer(text))
    for index, match in enumerate(matches):
        label = clean_text(match.group(1)).lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = clean_text(text[match.end() : end])
        if label and value and label not in fields:
            fields[label] = value
    return fields


def _fitxa_fields(doc: HTMLParser) -> dict[str, str]:
    fields: dict[str, str] = {}
    for node in doc.css("div.fitxa div.fitxaTD"):
        text = clean_text(node.text(separator=""))
        match = _LABEL_RE.match(text)
        if not match:
            continue
        label = clean_text(match.group(1)).lower()
        value = clean_text(match.group(2))
        if label and label not in fields:
            fields[label] = value
    # El `Títol` de la fitxa viu fora dels `fitxaTD`; el rescatem del bloc.
    for block in doc.css("div.fitxa"):
        for label, value in _scan_labels(clean_text(block.text(separator=""))).items():
            fields.setdefault(label, value)
    return fields


def _context_node(doc: HTMLParser):
    best = None
    for node in doc.css("table.tableFORMIN td"):
        if node.css_first("span.pclau") is not None:
            return node
        if best is None and clean_text(node.text(separator="")):
            best = node
    return best


def parse_fitxa(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    fields = _fitxa_fields(doc)

    context_node = _context_node(doc)
    context = ""
    left = nucleus = right = ""
    if context_node is not None:
        context = clean_text(context_node.text(separator=""))
        nucleus_node = context_node.css_first("span.pclau")
        if nucleus_node is not None:
            nucleus = clean_text(nucleus_node.text(separator=""))
            full_html = context_node.html or ""
            marker = nucleus_node.html or nucleus
            index = full_html.find(marker)
            if index >= 0:
                left = strip_tags(full_html[:index])
                right = strip_tags(full_html[index + len(marker) :])

    work = {
        "id": fields.get("id. obra"),
        "title": fields.get("títol"),
        "author": fields.get("autor"),
        "year": _year(fields.get("any d'edició")),
        "variety": fields.get("varietat"),
        "kind": fields.get("tipus"),
        "classification": fields.get("classificació"),
    }
    stats = {
        "occurrences": _int(fields.get("ocurrències")),
        "lemmas": _int(fields.get("lemes")),
        "forms": _int(fields.get("formes")),
    }
    occurrence = {
        "lemma": fields.get("lema"),
        "category": fields.get("categoria gramatical"),
        "form": fields.get("forma"),
        "morphology": fields.get("codi morfològic"),
        "position": _int(fields.get("posició dins l'obra")),
    }

    warnings: list[str] = []
    if not work["id"]:
        warnings.append("parse_partial")
    if not context:
        warnings.append("parse_partial")

    return {
        "work": work,
        "stats": stats,
        "occurrence": occurrence,
        "context": context,
        "left": left,
        "nucleus": nucleus,
        "right": right,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group(0)) if match else None
