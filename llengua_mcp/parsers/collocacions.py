"""Parser de les col·locacions d'un lema del CTILC.

La pàgina (CTILCQCol_LemesAgrup2.asp) agrupa les col·locacions per categoria
gramatical, amb seccions d'aquesta forma:

    <div id="V">Coincident amb <i>somriure</i> + <b>verb</b></div>
    ...
    <a class="lnkU" ...>...js...>va VA</a></td> <td>2192</td>

El nombre total de col·locacions és a `getElementById("freq").innerHTML = N`.
La pàgina conté totes les files; no cal retallar-les aquí.

L'apartat ALTRES barreja noms propis (sense categoria) i files de puntuació
(',' , '.', '—'...). Les files de puntuació no són col·locacions i es compten
a `excluded_rows`; els noms propis es retornen a part, a `altres`.
"""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text

COLLOCACIONS_URL = "https://ctilc.iec.cat/scripts/CTILCQCol_LemesAgrup2.asp"

_SECTION_RE = re.compile(
    r'<div id="(\w+)">Coincident amb <i>([^<]+)</i> \+(?: <b>)?([^<]+?)(?:</b>)?</div>'
)
_ROW_RE = re.compile(r'<a class="lnkU"[^>]*>([\s\S]*?)</a></td>\s*<td[^>]*>\s*(\d+)\s*</td>')
_TOTAL_RE = re.compile(r'getElementById\("freq"\)\.innerHTML\s*=\s*(\d+)')
_TERM_RE = re.compile(r">([A-Za-zÀ-ÿ_·\d][^<>]*)\s*$")
_TERM_CONTENT_RE = re.compile(r"^[A-Za-zÀ-ÿ_·\\d]")

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


def _item(term: str, freq: str) -> dict[str, Any]:
    lemma, _, pos = term.rpartition(" ")
    if not lemma:
        # Terme sense POS (noms propis de l'apartat ALTRES, p. ex.).
        lemma, pos = term, None
    item: dict[str, Any] = {"lema": lemma, "freq": int(freq)}
    if pos:
        item["pos"] = pos
    return item


def parse_collocacions(html: str) -> dict[str, Any]:
    """Retorna les col·locacions agrupades per categoria gramatical."""

    sections = {}
    for match in _SECTION_RE.finditer(html):
        sections[match.group(1)] = {
            "position": match.start(),
            "lema": clean_text(match.group(2)),
            "categoria": clean_text(match.group(3)),
        }
    if not sections:
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
    for code, info in sections.items():
        starts = [s["position"] for s in sections.values() if s["position"] > info["position"]]
        end = min(starts) if starts else len(html)
        segment = html[info["position"] : end]
        items = []
        for inner, freq in _ROW_RE.findall(segment):
            term = _visible_term(inner)
            if not term or not _TERM_CONTENT_RE.match(term):
                # L'apartat ALTRES inclou puntuació (',', '.', '—'...):
                # no són col·locacions útils i es descarten.
                excluded_rows += 1
                continue
            if code == ALT_SECTION:
                altres.append(_item(term, freq))
            else:
                items.append(_item(term, freq))
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
        "lema_echo": next(iter(sections.values()))["lema"],
        "total": total,
        "counted_rows": counted_rows,
        "excluded_rows": excluded_rows,
        "categories": categories,
        "altres": {"rows": len(altres), "items": altres},
        "source": COLLOCACIONS_URL,
    }


__all__ = ["ALT_SECTION", "COLLOCACIONS_URL", "parse_collocacions"]
