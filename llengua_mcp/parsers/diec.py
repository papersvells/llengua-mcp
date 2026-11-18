"""Parsers de la consulta i de les accepcions del DIEC."""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text, strip_tags


def parse_search(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    text = clean_text(doc.body.text(separator="") if doc.body else "")

    entries = []
    for link in doc.css("a.resultAnchor"):
        entry_id = (link.attributes.get("id") or "").strip()
        title = clean_text(link.text())
        if title:
            entries.append({"id": entry_id or None, "entry": title})

    match = re.search(r"Entrada coincident\s*:\s*([^.]+)\.", text)
    matched_entry = clean_text(match.group(1)) if match else None
    count_match = re.search(r"([\d.]+)\s+registres?", text)
    count = int(re.sub(r"[^\d]", "", count_match.group(1))) if count_match else None

    no_results = bool(
        re.search(
            r"No s'ha trobat|No hi ha cap entrada|cap resultat|No hi ha resultats",
            text,
            re.IGNORECASE,
        )
    )
    if no_results and count is None:
        count = 0

    warnings: list[str] = []
    if count is None:
        warnings.append("parse_partial")
    if count and not entries:
        warnings.append("parse_partial")

    return {
        "matched_entry": matched_entry,
        "count": count,
        "entries": entries,
        "warnings": list(dict.fromkeys(warnings)),
    }


def parse_accepcio(content_html: str) -> dict[str, Any]:
    doc = HTMLParser(content_html)
    title_parts = [clean_text(node.text()) for node in doc.css("h2 span.title")]
    title = " ".join(part for part in title_parts if part).strip()

    senses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    position = ""

    for node in doc.css("h2, span.tagline, span.body"):
        tag = node.tag
        if tag == "h2":
            continue
        if tag == "span" and "tagline" in (node.attributes.get("class") or ""):
            position = clean_text(node.text())
            if current is not None and not current.get("pos"):
                current["pos"] = position
            continue

        classes = node.attributes.get("class") or ""
        if "body" not in classes:
            continue

        number_node = node.css_first("b")
        if number_node is not None:
            number = clean_text(number_node.text())
            current = {
                "number": number or str(len(senses) + 1),
                "pos": position,
                "definition": "",
                "examples": [],
                "labels": [],
            }
            senses.append(current)
            remainder = strip_tags((node.html or "").replace(number_node.html or "", "", 1))
            if remainder:
                current["definition"] = remainder
            continue

        if current is None:
            current = {
                "number": "1",
                "pos": position,
                "definition": "",
                "examples": [],
                "labels": [],
            }
            senses.append(current)

        tip_labels = [clean_text(tip.text()) for tip in node.css("span.tip")]
        text = clean_text(node.text(separator=""))
        for label in tip_labels:
            if label:
                current["labels"].append(label)
                text = text.replace(label, "").strip()
        if not text:
            continue

        italic = node.css_first("span.italic")
        if italic is not None:
            example = clean_text(italic.text())
            if example:
                current["examples"].append(example)
            continue

        if current["definition"]:
            current["definition"] = f"{current['definition']} {text}".strip()
        else:
            current["definition"] = text

    warnings: list[str] = []
    if not senses:
        warnings.append("parse_partial")
    if not title:
        warnings.append("parse_partial")

    return {
        "title": title,
        "senses": senses,
        "warnings": list(dict.fromkeys(warnings)),
    }
