"""Parser de les respostes JSON de les APIs de les gramàtiques de l'IEC.

Les tres gramàtiques (GBU, GEIEC, GIEC) són aplicacions Angular amb la mateixa
arquitectura i APIs JSON equivalents:

- GBU   → https://api-gbu.iec.cat/api     (search_text, text_by_cody)
- GEIEC → https://api-geiec.iec.cat/api   (search_text, text_by_cody)
- GIEC  → https://api-giec.iec.cat        (TextGramatica/cercadic, TextGramatica/{codi})
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
        "portal": "https://giec.iec.cat/textgramatica/",
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


def parse_search_hits(payload: Any, paraula: str, *, font: str) -> list[dict[str, Any]]:
    """Normalitza els resultats de cerca de qualsevol de les tres gramàtiques."""

    if isinstance(payload, dict):
        payload = payload.get("texts") or []
    if not isinstance(payload, list):
        raise UnexpectedResponseError(
            "La resposta de la gramàtica no té el format esperat.",
            hint=f"L'API de {font.upper()} pot haver canviat; cal revisar el parser.",
            source=GRAMATICAS[font]["api"],
        )

    hits: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        contingut = item.get("contingut")
        if not contingut:
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
        if len(hits) >= MAX_HITS:
            break
    return hits


def parse_text(payload: Any, *, font: str) -> dict[str, Any]:
    """Normalitza un text sol de qualsevol de les tres gramàtiques."""

    if not isinstance(payload, dict):
        raise UnexpectedResponseError(
            "La resposta de la gramàtica no té el format esperat.",
            hint=f"L'API de {font.upper()} pot haver canviat; cal revisar el parser.",
            source=GRAMATICAS[font]["api"],
        )
    contingut = payload.get("contingut")
    if not contingut:
        raise UnexpectedResponseError(
            "Aquest apartat no té text llegible.",
            hint=(
                "Alguns codis són només títols de la jerarquia. Prova un codi "
                "fulla o cerca'l amb `gramatica_cerca`."
            ),
            source=GRAMATICAS[font]["api"],
        )
    return {
        "codi_text": payload.get("codiText"),
        "titol": strip_tags(payload.get("titolText") or payload.get("titol") or ""),
        "content": strip_tags(contingut),
        "url": GRAMATICAS[font]["portal"] + str(payload.get("codiText") or ""),
    }


__all__ = ["CRITERIA", "GRAMATICAS", "parse_search_hits", "parse_text"]
