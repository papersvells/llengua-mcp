"""Parser de les col·locacions d'un lema o d'una forma del CTILC.

La pàgina de lemes (CTILCQCol_LemesAgrup2.asp) i la de formes
(CTILCQCol_FormesAgrup2.asp) comparteixen l'estructura de seccions:

    <div id="V">Coincident amb <i>somriure</i> + <b>verb</b></div>

però no la de files. La pàgina de lemes dona només el terme i la freqüència:

    <a class="lnkU" ...>va VA</a></td> <td>2192</td>

mentre que la de formes afegeix quatre columnes d'associació:

    <a class="lnkU" ...>reverència F</a></td> <td>11,3028</td> <td>6</td>
    <td>-0,167</td> <td>4,81</td> <td>497</td>

L'ordre és: informació mútua, freqüència de coaparició, distància mitjana,
variància i freqüència del lema. Els decimals fan servir coma.

El nombre total de col·locacions és a `getElementById("freq").innerHTML = N`.
La pàgina conté totes les files; no cal retallar-les aquí.

L'apartat ALTRES barreja noms propis (sense categoria) i files de puntuació
(',' , '.', '—'...). Les files de puntuació no són col·locacions i es compten
a `excluded_rows`; els noms propis es retornen a part, a `altres`.

Quan no hi ha cap resultat, el portal no dona comptador: només un missatge
(«No hi ha cap lema/forma que compleixi aquestes condicions»). El parser ho
retorna com a `status: "empty"` perquè l'adaptador ho pugui distingir d'un
error de format, sense presentar-ho com una absència verificada.
"""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text

COLLOCACIONS_URL = "https://ctilc.iec.cat/scripts/CTILCQCol_LemesAgrup2.asp"
COLLOCACIONS_FORMA_URL = "https://ctilc.iec.cat/scripts/CTILCQCol_FormesAgrup2.asp"

_SECTION_RE = re.compile(
    r'<div id="(\w+)">Coincident amb <i>([^<]+)</i> \+(?: <b>)?([^<]+?)(?:</b>)?</div>'
)
_ROW_RE = re.compile(r'<a class="lnkU"[^>]*>([\s\S]*?)</a></td>((?:\s*<td[^>]*>[\s\S]*?</td>)+)')
_CELL_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>")
_TOTAL_RE = re.compile(r'getElementById\("freq"\)\.innerHTML\s*=\s*(\d+)')
_TERM_RE = re.compile(r">([A-Za-zÀ-ÿ_·\d][^<>]*)\s*$")
_TERM_CONTENT_RE = re.compile(r"^[A-Za-zÀ-ÿ_·\d]")
_EMPTY_RE = re.compile(r"No hi ha cap (?:lema|forma) que compleixi aquestes condicions")

ALT_SECTION = "ALT"


def _visible_term(inner: str) -> str | None:
    """Extreu el terme visible del final de l'HTML brut de l'enllaç.

    Retorna None si el terme no comença amb una lletra: les files de
    puntuació de l'apartat ALTRES (',' , '.', '—'...) no són col·locacions.
    """

    collapsed = re.sub(r"\s+", " ", inner).strip()
    match = _TERM_RE.search(collapsed)
    if match is None and _TERM_CONTENT_RE.match(collapsed):
        # Els enllaos sintètics poden tenir només el terme, sense JavaScript.
        match = re.match(r"([A-Za-zÀ-ÿ_·\d][^<>]*)\s*$", collapsed)
    if match:
        return clean_text(match.group(1))
    return None


def _number(text: str) -> int | float | None:
    """Converteix un número del portal, que pot fer servir coma decimal."""

    value = clean_text(text).replace(".", "").replace(",", ".")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def _item(term: str, cells: list[str]) -> dict[str, Any]:
    lemma, _, pos = term.rpartition(" ")
    if not lemma:
        # Terme sense POS (noms propis de l'apartat ALTRES, p. ex.).
        lemma, pos = term, None
    item: dict[str, Any] = {"lema": lemma}
    if pos:
        item["pos"] = pos
    if len(cells) == 1:
        freq = _number(cells[0])
        item["freq"] = freq
        return item
    mi, freq, distancia, varianca, freq_lema = cells[:5]
    item["info_mutua"] = _number(mi)
    item["freq"] = _number(freq)
    item["distancia"] = _number(distancia)
    item["varianca"] = _number(varianca)
    item["freq_lema"] = _number(freq_lema)
    return item


def parse_collocacions(html: str) -> dict[str, Any]:
    """Retorna les col·locacions agrupades per categoria gramatical.

    `status` és `ok`, o `empty` quan el portal diu explícitament que no hi ha
    cap lema o forma que compleixi les condicions, sense comptador.
    """

    sections = {}
    for match in _SECTION_RE.finditer(html):
        sections[match.group(1)] = {
            "position": match.start(),
            "lema": clean_text(match.group(2)),
            "categoria": clean_text(match.group(3)),
        }
    if not sections:
        if _EMPTY_RE.search(html):
            return {
                "status": "empty",
                "layout": None,
                "echo": None,
                "total": None,
                "counted_rows": 0,
                "excluded_rows": 0,
                "categories": [],
                "altres": {"rows": 0, "items": []},
            }
        raise UnexpectedResponseError(
            "La pàgina de col·locacions no té el format esperat.",
            hint="El CTILC pot haver canviat de format; cal revisar el parser.",
            source=COLLOCACIONS_URL,
        )

    total_match = _TOTAL_RE.search(html)
    total = int(total_match.group(1)) if total_match else None

    categories: list[dict[str, Any]] = []
    altres: list[dict[str, Any]] = []
    excluded_rows = 0
    layout = "lema"
    for code, info in sections.items():
        starts = [s["position"] for s in sections.values() if s["position"] > info["position"]]
        end = min(starts) if starts else len(html)
        segment = html[info["position"] : end]
        items = []
        for inner, cells_html in _ROW_RE.findall(segment):
            term = _visible_term(inner)
            if not term or not _TERM_CONTENT_RE.match(term):
                # L'apartat ALTRES inclou puntuació (',', '.', '—'...):
                # no són col·locacions útils i es descarten.
                excluded_rows += 1
                continue
            cells = _CELL_RE.findall(cells_html)
            if len(cells) > 1:
                layout = "forma"
            if code == ALT_SECTION:
                altres.append(_item(term, cells))
            else:
                items.append(_item(term, cells))
        if items:
            categories.append(
                {
                    "codi": code,
                    "categoria": info["categoria"],
                    "rows": len(items),
                    "items": items,
                }
            )

    counted_rows = sum(category["rows"] for category in categories) + len(altres)
    return {
        "status": "ok",
        "layout": layout,
        "echo": next(iter(sections.values()))["lema"],
        "total": total,
        "counted_rows": counted_rows,
        "excluded_rows": excluded_rows,
        "categories": categories,
        "altres": {"rows": len(altres), "items": altres},
    }


__all__ = [
    "ALT_SECTION",
    "COLLOCACIONS_FORMA_URL",
    "COLLOCACIONS_URL",
    "parse_collocacions",
]
