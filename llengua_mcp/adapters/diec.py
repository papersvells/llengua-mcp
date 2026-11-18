"""Adaptador del DIEC (Institut d'Estudis Catalans)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from llengua_mcp.errors import InvalidQueryError, LlenguaError, UnexpectedResponseError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.diec import parse_accepcio, parse_search
from llengua_mcp.text import clean_text

SEARCH_URL = "https://dlc.iec.cat/Results"
ACCEPCIO_URL = "https://dlc.iec.cat/Results/Accepcio"

SEARCH_PARAMS = {
    "AllInfoMorf": "False",
    "OperEntrada": "0",
    "OperDef": "0",
    "OperEx": "0",
    "OperSubEntrada": "0",
    "OperAreaTematica": "0",
    "InfoMorfType": "0",
    "OperCatGram": "False",
    "AccentSen": "False",
    "CurrentPage": "0",
    "refineSearch": "0",
    "Actualitzacions": "False",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class DiecAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def consulta(self, paraula: str, *, limit: int = 3) -> dict[str, Any]:
        paraula = clean_text(paraula)
        if not paraula:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu la paraula que vols comprovar al DIEC.",
            )
        if len(paraula) > 80:
            raise InvalidQueryError(
                "La consulta és massa llarga per al DIEC.",
                hint="Consulta un mot o una locució curta.",
            )
        limit = max(1, min(limit, 5))

        params = {"DecEntradaText": paraula, **SEARCH_PARAMS}
        result = await self.client.get_text(SEARCH_URL, params=params, cache_ttl=86400)
        parsed = parse_search(result.text)

        entries = parsed["entries"][:limit]
        if parsed["count"] == 0:
            return {
                "status": "no_results",
                "query": {"paraula": paraula},
                "matched_entry": parsed["matched_entry"],
                "count": parsed["count"],
                "entries": [],
                "warnings": list(dict.fromkeys(result.warnings + parsed["warnings"])),
                "note": (
                    "No s'ha trobat cap entrada amb aquesta cerca. Això no converteix "
                    "la forma en incorrecta: pot ser una locució dins d'un altre article, "
                    "una variant o un mot no recollit."
                ),
                "source": str(result.url),
                "retrieved_at": _now(),
                "citation": (
                    "DIEC2 (IEC), consulta feta el "
                    + datetime.now(UTC).strftime("%d/%m/%Y")
                    + f": {paraula}"
                ),
            }

        if not entries:
            raise UnexpectedResponseError(
                "La pàgina del DIEC no conté cap entrada llegible.",
                hint=(
                    "El portal pot haver canviat de format o haver retornat una "
                    "pàgina d'error. No es pot interpretar com un zero."
                ),
                source=str(result.url),
            )

        warnings = list(result.warnings + parsed["warnings"])
        detailed = []
        for entry in entries:
            entry_id = entry.get("id")
            payload: dict[str, Any] = {
                "id": entry_id,
                "entry": entry["entry"],
            }
            if not entry_id:
                payload["warnings"] = ["parse_partial"]
                detailed.append(payload)
                continue
            try:
                body = f"id={quote(entry_id, safe='')}&searchParam=null"
                content, response = await self.client.post_json(
                    ACCEPCIO_URL,
                    body,
                    headers={"Referer": str(result.url)},
                    cache_ttl=86400,
                )
                parsed_entry = parse_accepcio(str(content.get("content", "")))
                payload.update(
                    {
                        "title": parsed_entry["title"] or entry["entry"],
                        "senses": parsed_entry["senses"],
                        "warnings": parsed_entry["warnings"] + response.warnings,
                    }
                )
            except LlenguaError as exc:
                payload["warnings"] = ["parse_partial"]
                payload["error"] = {"message": exc.message, "hint": exc.hint}
            detailed.append(payload)

        if any(item.get("warnings") for item in detailed):
            warnings.append("parse_partial")

        return {
            "status": "ok" if all(item.get("senses") for item in detailed) else "partial",
            "query": {"paraula": paraula},
            "matched_entry": parsed["matched_entry"],
            "count": parsed["count"],
            "entries": detailed,
            "warnings": list(dict.fromkeys(warnings)),
            "note": (
                "El DIEC és la referència normativa del lèxic. Cal citar l'entrada "
                "i l'accepció que justifiquen la resposta; una locució pot aparèixer "
                "dins de l'article d'un dels mots."
            ),
            "source": str(result.url),
            "retrieved_at": _now(),
            "citation": (
                "DIEC2 (IEC), consulta feta el "
                + datetime.now(UTC).strftime("%d/%m/%Y")
                + f": {paraula}"
            ),
        }


__all__ = ["DiecAdapter"]
