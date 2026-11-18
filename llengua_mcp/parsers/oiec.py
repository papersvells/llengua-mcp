"""Parser de les respostes JSON de l'API de l'OIEC (Ortografia catalana).

L'API és pública i sense autenticació: https://api-oiec.iec.cat
Serveix l'obra «Ortografia catalana» (OIEC) de l'IEC com a JSON.
"""

from __future__ import annotations

from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text, strip_tags

API_URL = "https://api-oiec.iec.cat"
SOURCE_URL = "https://oiec.iec.cat/"

MATCH_TYPES = {
    "exact": "Coincident",
    "coincident": "Coincident",
    "contains": "En qualsevol posició",
    "conte": "En qualsevol posició",
    "en qualsevol posicio": "En qualsevol posició",
}

MAX_HITS = 5
MAX_SNIPPET_CHARS = 700


def _matches_query(text: str, query: str) -> tuple[str, int] | None:
    """Retalla un fragment que contingui la paraula cercada."""

    lowered = text.casefold()
    position = lowered.find(query.casefold())
    if position < 0:
        return None
    start = max(0, position - 260)
    end = min(len(text), position + MAX_SNIPPET_CHARS - 260)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}", position


def parse_search(payload: Any, paraula: str) -> dict[str, Any]:
    """Converteix la resposta de cerca en resultats llegibles.

    Només els textos que tenen `contingut` són apartats llegibles; els altres
    són nodes de títol de la jerarquia.
    """

    if not isinstance(payload, list):
        raise UnexpectedResponseError(
            "La resposta de l'OIEC no té el format esperat.",
            hint="L'API pot haver canviat; cal revisar el parser.",
            source=API_URL,
        )

    hits: list[dict[str, Any]] = []
    nodes_without_content = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        contingut = item.get("contingut")
        if not contingut:
            nodes_without_content += 1
            continue
        plain = strip_tags(contingut)
        snippet = _matches_query(plain, paraula)
        hit: dict[str, Any] = {
            "codi_text": item.get("codiText"),
            "titol": clean_text(item.get("titol") or ""),
            "url": f"{SOURCE_URL}textortografia/{item.get('codiText') or ''}",
        }
        if snippet:
            hit["snippet"] = snippet[0]
        else:
            hit["snippet"] = plain[:MAX_SNIPPET_CHARS].strip() + "…"
        hits.append(hit)
        if len(hits) >= MAX_HITS:
            break

    warnings: list[str] = []
    if len(payload) > MAX_HITS:
        warnings.append("truncated")
    if not hits:
        warnings.append("no_readable_sections")

    return {
        "total_hits": len(payload),
        "returned": len(hits),
        "hits": hits,
        "warnings": warnings,
    }


def parse_text(payload: Any) -> dict[str, Any]:
    """Converteix un text sol (/TextOrtografia/{codi}) en un apartat llegible."""

    if not isinstance(payload, dict):
        raise UnexpectedResponseError(
            "La resposta de l'OIEC no té el format esperat.",
            hint="L'API pot haver canviat; cal revisar el parser.",
            source=API_URL,
        )
    contingut = payload.get("contingut")
    if not contingut:
        raise UnexpectedResponseError(
            "Aquest apartat no té text llegible.",
            hint=(
                "Alguns codis són només títols de la jerarquia. Prova un codi "
                "fulla, per exemple `4.1.2b`, o cerca'l amb `oiec_cerca`."
            ),
            source=API_URL,
        )
    return {
        "codi_text": payload.get("codiText"),
        "titol": clean_text(payload.get("titolText") or payload.get("titol") or ""),
        "content": strip_tags(contingut),
        "prev": payload.get("codiAnterior"),
        "next": payload.get("codiSeguent"),
    }


__all__ = ["API_URL", "MATCH_TYPES", "SOURCE_URL", "parse_search", "parse_text"]
