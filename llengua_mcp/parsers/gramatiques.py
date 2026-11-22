"""Parser de les respostes JSON de les APIs de les gramàtiques de l'IEC.

Les tres gramàtiques (GBU, GEIEC, GIEC) són aplicacions Angular amb la mateixa
arquitectura i APIs JSON equivalents:

- GBU   → https://api-gbu.iec.cat/api     (search_text, text_by_cody)
- GEIEC → https://api-geiec.iec.cat/api   (search_text, text_by_cody)
- GIEC  → https://api-giec.iec.cat        (TextGramatica/cercadic, TextGramatica/{codi})

La GBU retorna una llista; la GIEC, un objecte amb `texts`. Un objecte sense
`texts` no és una cerca sense resultats: és una resposta que no s'ha pogut
interpretar i s'ha de presentar com a error, no com a absència.
"""

from __future__ import annotations

from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import strip_tags

MAX_HITS = 5
MAX_SNIPPET_CHARS = 700

GRAMATICAS = {
    "gbu": {
        "label": "Gramàtica bàsica i d'ús (GBU)",
        "api": "https://api-gbu.iec.cat/api",
        "portal": "https://gbu.iec.cat/text/",
    },
    "geiec": {
        "label": "Gramàtica essencial (GEIEC)",
        "api": "https://api-geiec.iec.cat/api",
        "portal": "https://geiec.iec.cat/text/",
    },
    "giec": {
        "label": "Gramàtica de la llengua catalana (GIEC)",
        "api": "https://api-giec.iec.cat",
        "portal": "https://giec.iec.cat/textgramatica/codi/",
    },
}

CRITERIA = {
    "contains": "En qualsevol posició",
    "conte": "En qualsevol posició",
    "en qualsevol posicio": "En qualsevol posició",
    "exact": "Coincident",
    "coincident": "Coincident",
}


def _snippet(text: str, query: str) -> str:
    """Fragment net que envolta la primera ocurrència de la cerca."""

    plain = strip_tags(text)
    position = plain.casefold().find(query.casefold())
    if position < 0:
        return plain[:MAX_SNIPPET_CHARS].strip() + "…"
    start = max(0, position - 260)
    end = min(len(plain), position + MAX_SNIPPET_CHARS - 260)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(plain) else ""
    return f"{prefix}{plain[start:end].strip()}{suffix}"


def _unexpected(message: str, *, font: str, hint: str) -> UnexpectedResponseError:
    return UnexpectedResponseError(message, hint=hint, source=GRAMATICAS[font]["api"])


def _search_items(payload: Any, *, font: str) -> list[Any]:
    """Extreu la llista de textos, distingint-la d'una resposta trencada."""

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "texts" not in payload:
            raise _unexpected(
                "La resposta de la gramàtica no conté el camp «texts».",
                font=font,
                hint=(
                    "No és el mateix que una cerca sense resultats. L'API pot "
                    "haver canviat de format; cal revisar el parser."
                ),
            )
        items = payload.get("texts")
        if items is None:
            return []
        if not isinstance(items, list):
            raise _unexpected(
                "El camp «texts» de la resposta no és una llista.",
                font=font,
                hint="L'API pot haver canviat de format; cal revisar el parser.",
            )
        return items
    raise _unexpected(
        "La resposta de la gramàtica no té el format esperat.",
        font=font,
        hint=f"L'API de {font.upper()} pot haver canviat; cal revisar el parser.",
    )


def parse_search_hits(payload: Any, paraula: str, *, font: str) -> dict[str, Any]:
    """Normalitza els resultats de cerca de qualsevol de les tres gramàtiques.

    Retorna `total` (nodes retornats per l'API), els `hits` llegibles i els
    avisos. Un total positiu sense cap apartat llegible és `partial`, no una
    absència.
    """

    items = _search_items(payload, font=font)

    hits: list[dict[str, Any]] = []
    readable = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        contingut = item.get("contingut")
        if not contingut:
            continue
        readable += 1
        if len(hits) >= MAX_HITS:
            continue
        titol = strip_tags(item.get("titol") or item.get("titolText") or "")
        hits.append(
            {
                "codi_text": item.get("codiText"),
                "titol": titol,
                "snippet": _snippet(contingut, paraula),
                "url": GRAMATICAS[font]["portal"] + str(item.get("codiText") or ""),
            }
        )

    warnings: list[str] = []
    if readable > len(hits):
        warnings.append("truncated")
    if items and not hits:
        warnings.append("no_readable_sections")

    return {
        "total": len(items),
        "hits": hits,
        "warnings": warnings,
    }


def parse_text(payload: Any, *, font: str, expected: str | None = None) -> dict[str, Any]:
    """Normalitza un text sol de qualsevol de les tres gramàtiques."""

    if not isinstance(payload, dict):
        raise _unexpected(
            "La resposta de la gramàtica no té el format esperat.",
            font=font,
            hint=f"L'API de {font.upper()} pot haver canviat; cal revisar el parser.",
        )

    codi_text = payload.get("codiText")
    codi_rebut = str(codi_text or "").strip()
    if expected and codi_rebut != expected:
        if not codi_rebut:
            raise _unexpected(
                f"La resposta no identifica cap codi; s'ha demanat «{expected}».",
                font=font,
                hint=(
                    "El codi pot no existir o l'API pot haver canviat. "
                    "Comprova'l amb la cerca abans de citar-lo."
                ),
            )
        raise _unexpected(
            f"El codi retornat («{codi_text}») no correspon al sol·licitat («{expected}»).",
            font=font,
            hint=(
                "L'API pot haver canviat o haver retornat un altre apartat. "
                "No es presenta com el text demanat."
            ),
        )

    contingut = payload.get("contingut")
    if not contingut:
        raise _unexpected(
            "Aquest apartat no té text llegible.",
            font=font,
            hint=(
                "Alguns codis són només títols de la jerarquia. Prova un codi "
                "fulla o cerca'l amb `gramatica_cerca`."
            ),
        )
    return {
        "codi_text": codi_text,
        "titol": strip_tags(payload.get("titolText") or payload.get("titol") or ""),
        "content": strip_tags(contingut),
        "url": GRAMATICAS[font]["portal"] + str(codi_text or ""),
    }


__all__ = ["CRITERIA", "GRAMATICAS", "parse_search_hits", "parse_text"]
