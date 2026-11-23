"""Parser de les fitxes HTML del conjugador de Softcatalà."""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text

PERSONS = (
    ("singular1", "jo"),
    ("singular2", "tu"),
    ("singular3", "ell, ella, vostè"),
    ("plural1", "nosaltres"),
    ("plural2", "vosaltres, vós"),
    ("plural3", "ells, elles, vostès"),
)
_MARKER = "\u241f"


def _split_forms(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    marked = False
    for char in value:
        if char == _MARKER:
            marked = not marked
            current.append(char)
        elif char in {",", "/"} and not marked:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _forms(cell: Any) -> list[dict[str, str]]:
    raw = cell.text(separator=_MARKER)
    if raw.count(_MARKER) % 2:
        raw += _MARKER
    output: list[dict[str, str]] = []
    for item in _split_forms(raw):
        # A variant marker follows the form in a dedicated span in the source.
        match = re.match(r"^(.*?)\s*" + _MARKER + r"\s*(.*?)\s*" + _MARKER + r"\s*$", item)
        if match:
            form = clean_text(match.group(1))
            variety = clean_text(match.group(2)).strip("() ")
        else:
            form, variety = clean_text(item.replace(_MARKER, " ")), ""
        if form:
            output.append({"form": form, "variety": variety})
    return output


def parse_conjugation(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    container = doc.css_first("#conjugador-verb-caixa")
    if container is None:
        text = clean_text(doc.body.text(separator=" ") if doc.body else "")
        not_found = (
            "No hem trobat la forma verbal" in text
            or "No s'ha trobat la pàgina" in text
            or "No s’ha trobat la pàgina" in text
        )
        return {
            "found": False,
            "not_found_message": not_found,
            "warnings": [] if not_found else ["parse_partial"],
        }

    heading = container.css_first("h3")
    infinitive = clean_text(heading.text()) if heading else ""
    if not infinitive:
        return {"found": False, "not_found_message": False, "warnings": ["parse_partial"]}

    note_node = container.css_first(".note")
    note = clean_text(note_node.text()) if note_node else ""
    sections: list[dict[str, Any]] = []
    for section in container.css(".result-conjugador"):
        mode_node = section.css_first("h4")
        mode = clean_text(mode_node.text()) if mode_node else ""
        rows: list[dict[str, Any]] = []
        panels = section.css(".panel") if mode != "Formes no personals" else []
        for panel in panels:
            tense_node = panel.css_first(".panel-heading")
            table = panel.css_first("table")
            if tense_node is None or table is None:
                continue
            tense = clean_text(tense_node.text())
            cells = table.css("tr td")
            persons: list[dict[str, Any]] = []
            for index, (key, subject) in enumerate(PERSONS):
                cell = cells[index] if index < len(cells) else None
                forms = _forms(cell) if cell is not None else []
                unavailable = not forms
                status = (
                    "not_applicable"
                    if mode == "Mode imperatiu" and key == "singular1"
                    else "not_provided"
                    if unavailable
                    else "available"
                )
                persons.append({"key": key, "subject": subject, "status": status, "forms": forms})
            rows.append({"tense": tense, "persons": persons})
        if mode == "Formes no personals":
            for row in section.css("table tr"):
                label = clean_text(row.css_first("th").text()) if row.css_first("th") else ""
                cell = row.css_first("td")
                if label and cell is not None:
                    rows.append(
                        {
                            "tense": label,
                            "persons": [
                                {
                                    "key": "non_personal",
                                    "subject": "",
                                    "status": "available" if _forms(cell) else "not_provided",
                                    "forms": _forms(cell),
                                }
                            ],
                        }
                    )
        sections.append({"mode": mode.removeprefix("Mode "), "rows": rows})

    warnings = [] if sections else ["parse_partial"]
    return {
        "found": True,
        "infinitive": infinitive,
        "note": note or None,
        "sections": sections,
        "warnings": warnings,
    }
