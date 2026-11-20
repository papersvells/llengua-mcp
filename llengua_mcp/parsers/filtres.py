"""Parser de les llistes de filtres del CTILC (autors, títols i temes).

Les llistes es carreguen amb `CTILCQConcFiltObra_filtres.asp` i depenen del
resultat actual (`resultat`). Cada valor és una casella amb `VALUE="@…"` i una
etiqueta amb el recompte, per exemple `Abelló, Montserrat [2]`. El panell
`filt=lang` porta la classificació temàtica NLIT (`classtemSelecBox`), amb el
codi decimal i la descripció dins d'un `tooltiptext`.
"""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text

FILTRES_URL = "https://ctilc.iec.cat/scripts/CTILCQConcFiltObra_filtres.asp"

BOXES = {"autors": "autSelecBox", "titols": "titSelecBox"}
KINDS = {"autors": "authors", "titols": "titles", "temes": "lang"}
EXTRA_PARAMS = {
    "autors": "autSelec=&AutTria=0",
    "titols": "titSelec=&TitTria=0",
    "temes": "tipusSelec=&genSelec=&classtemSelec=&classtemGSelec=",
}

_THEME_RE = re.compile(
    r"NAME=['\"]classtemSelecBox['\"][^>]*VALUE=['\"](@\d+(?:\.\d)?)['\"][^>]*>"
    r"\s*(?:&nbsp;|\s)*<span class=\"tooltip\">\s*[^<\[]*\[(\d+)\]\s*"
    r"<span class=\"tooltiptext\">([^<]*)</span>",
    re.IGNORECASE,
)


def _parse_themes(html: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _THEME_RE.finditer(html):
        code = clean_text(match.group(1)).lstrip("@")
        count = int(match.group(2))
        label = clean_text(match.group(3))
        label = re.sub(rf"^{re.escape(code)}\s*-\s*", "", label) or label
        if not code or code in seen:
            continue
        seen.add(code)
        values.append({"value": code, "label": label, "count": count})
    return values


def parse_filter_values(html: str, *, tipus: str) -> list[dict[str, Any]]:
    """Retorna els valors de la llista amb etiqueta i recompte."""

    if tipus == "temes":
        values = _parse_themes(html)
        if not values:
            raise UnexpectedResponseError(
                "La llista de temes no té el format esperat.",
                hint="El CTILC pot haver canviat; cal revisar el parser.",
                source=FILTRES_URL,
            )
        return values

    box = BOXES.get(tipus)
    if box is None:
        raise UnexpectedResponseError(
            f"La llista de filtres «{tipus}» no existeix.",
            hint="Valors disponibles: " + ", ".join(sorted(KINDS)) + ".",
            source=FILTRES_URL,
        )

    pattern = re.compile(
        rf'NAME="{box}"[^>]*VALUE="(@[^"]+)"[\s\S]{{0,400}}?</td>\s*'
        rf"(?:<td[^>]*>\s*([^<]*)</td>)?",
        re.IGNORECASE,
    )
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in pattern.finditer(html):
        value = clean_text(match.group(1)).lstrip("@")
        label = clean_text(match.group(2) or "")
        count_match = re.search(r"\[(\d+)\]", label)
        count = int(count_match.group(1)) if count_match else None
        name = re.sub(r"\s*\[\d+\]\s*$", "", label).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append({"value": value, "label": name or value, "count": count})

    if not values:
        raise UnexpectedResponseError(
            "La llista de filtres no té el format esperat.",
            hint="El CTILC pot haver canviat; cal revisar el parser.",
            source=FILTRES_URL,
        )
    return values


__all__ = [
    "BOXES",
    "EXTRA_PARAMS",
    "FILTRES_URL",
    "KINDS",
    "parse_filter_values",
]
