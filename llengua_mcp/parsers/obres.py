"""Parsers de les consultes d'obres del CTILC (autor, títol i resultats)."""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text, normalize_key

_ZERO_AUTHOR = "no hi ha cap autor que respongui"
_ZERO_WORK = "no hi ha cap obra que respongui"


def _header_field(header: str) -> str | None:
    if "autor" in header:
        return "author"
    if "titol" in header:
        return "title"
    if "any" in header:
        return "year"
    if "lit" in header and "/" in header:
        return "kind"
    if "genere" in header:
        return "genre"
    if "class" in header:
        return "classification"
    if "traduccio" in header:
        return "translation"
    if "varietat" in header:
        return "variety"
    return None


def parse_authors(html: str) -> dict[str, Any]:
    """Llista d'autors de ``CTILCCorpus_Aut1.asp``."""

    doc = HTMLParser(html)
    body_text = clean_text(doc.body.text(separator=" ") if doc.body else "")
    echo_node = doc.css_first('input[name="autor"]')
    echo = clean_text(echo_node.attributes.get("value")) if echo_node else ""
    explicit_zero = _ZERO_AUTHOR in normalize_key(body_text)

    select = doc.css_first("select#autorL") or doc.css_first('select[name="autorL"]')
    authors: list[dict[str, str]] = []
    if select is not None:
        for option in select.css("option"):
            author_id = clean_text(option.attributes.get("value"))
            name = clean_text(option.text())
            if author_id and name:
                authors.append({"id": author_id, "name": name})

    warnings: list[str] = []
    if not authors and not explicit_zero:
        warnings.append("parse_partial")
    return {
        "authors": authors,
        "echo": echo,
        "explicit_zero": explicit_zero,
        "warnings": warnings,
    }


def parse_works(html: str) -> dict[str, Any]:
    """Taula d'obres de ``CTILCCorpus_Obr2.asp`` o ``CTILCCorpus_Aut2.asp``."""

    doc = HTMLParser(html)
    body_text = clean_text(doc.body.text(separator=" ") if doc.body else "")
    explicit_zero = _ZERO_WORK in normalize_key(body_text)

    count_match = re.search(r"Resultat:\s*([\d.]+)\s+obres?", body_text, re.IGNORECASE)
    total = int(re.sub(r"[^\d]", "", count_match.group(1))) if count_match else None
    if explicit_zero:
        total = 0

    table = None
    for candidate in doc.css("table"):
        rows = candidate.css("tr")
        if not rows:
            continue
        headers = [normalize_key(cell.text()) for cell in rows[0].css("td")]
        if (
            len(headers) >= 6
            and any("titol" in header for header in headers)
            and any("any" in header for header in headers)
        ):
            table = candidate
            break

    works: list[dict[str, Any]] = []
    warnings: list[str] = []
    if table is not None:
        rows = table.css("tr")
        header_cells = [normalize_key(cell.text()) for cell in rows[0].css("td")]
        fields = {index: _header_field(header) for index, header in enumerate(header_cells)}
        for row in rows[1:]:
            cells = row.css("td")
            if len(cells) < len(header_cells):
                warnings.append("parse_partial")
                continue
            work: dict[str, Any] = {
                "id": None,
                "title": None,
                "author": None,
                "year": None,
                "variety": None,
                "kind": None,
                "classification": None,
                "translation": False,
            }
            for index, field in fields.items():
                if field is None:
                    continue
                value = clean_text(cells[index].text(separator=" "))
                if field == "year":
                    work["year"] = int(value) if value.isdigit() else None
                elif field == "translation":
                    work["translation"] = bool(re.search(r"\[t\]", value, re.IGNORECASE))
                else:
                    work[field] = value or None
            works.append(work)

    if total is None and not explicit_zero:
        warnings.append("parse_partial")
    if total is not None and total > 0 and not works:
        warnings.append("parse_partial")
    if total is not None and works and total != len(works):
        warnings.append("rows_mismatch")

    echo = ""
    form_out = doc.css_first("#cHTML1 table.tableFORMOUT") or doc.css_first("table.tableFORMOUT")
    if form_out is not None:
        form_text = clean_text(form_out.text(separator=" "))
        match = re.search(r"Títol de l'obra:\s*(.*)$", form_text, re.IGNORECASE)
        if match:
            echo = clean_text(match.group(1))

    return {
        "total": total,
        "works": works,
        "echo": echo,
        "explicit_zero": explicit_zero,
        "warnings": list(dict.fromkeys(warnings)),
    }


__all__ = ["parse_authors", "parse_works"]
