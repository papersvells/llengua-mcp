"""Adaptador de les tres gramàtiques de l'IEC: GBU, GEIEC i GIEC.

Les tres són aplicacions Angular amb APIs JSON equivalents. La GBU i la GEIEC
comparteixen endpoints (`search_text`, `text_by_cody`); la GIEC fa servir el
mateix patró de l'OIEC (`TextGramatica/cercadic/{mode}`, `TextGramatica/{codi}`).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.gramatiques import (
    CRITERIA,
    GRAMATICAS,
    parse_search_hits,
    parse_text,
)

DEFAULT_FONTS = ("gbu", "geiec", "giec")


def _load(text: str, font: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise UnexpectedResponseError(
            f"La resposta de {font.upper()} no és JSON vàlid.",
            hint="L'API pot haver canviat o haver retornat una pàgina d'error.",
            source=GRAMATICAS[font]["api"],
        ) from exc


class GramatiquesAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(
        self,
        paraula: str,
        *,
        font: str = "gbu",
        coincidencia: str = "contains",
    ) -> dict[str, Any]:
        term = " ".join(paraula.split())
        if not term:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu una paraula o un fenomen gramatical (per exemple «perífrasi»).",
            )
        if len(term) > 80:
            raise InvalidQueryError(
                "La consulta és massa llarga.",
                hint="Consulta un mot o un fenomen curt.",
            )
        if font not in GRAMATICAS:
            raise InvalidQueryError(
                f"La font «{font}» no existeix.",
                hint="Fonts disponibles: " + ", ".join(sorted(GRAMATICAS)) + ".",
            )
        mode = CRITERIA.get(coincidencia.strip().lower())
        if mode is None:
            raise InvalidQueryError(
                f"El tipus de coincidència «{coincidencia}» no existeix.",
                hint="Valors: exact (Coincident) o contains (En qualsevol posició).",
            )

        config = GRAMATICAS[font]
        warnings: list[str] = []
        hits: list[dict[str, Any]] = []
        total = 0

        if font == "giec":
            # La GIEC fa servir el patró de l'OIEC: la paraula va codificada
            # dues vegades (el component fa encodeURIComponent i el servei
            # afegeix la query codificada).
            url = f"{config['api']}/TextGramatica/cercadic/{quote(mode)}?paraula={quote(term)}"
            result = await self.client.get_text(url, cache_ttl=86400)
            payload = _load(result.text, font)
            total = len(payload.get("texts") or [])
            hits = parse_search_hits(payload, term, font=font)
            warnings.extend(result.warnings)
        else:
            # La GBU i la GEIEC comparteixen endpoints.
            url = f"{config['api']}/search_text?" + urlencode(
                {"searchWord": term, "criteria": mode, "fonetica": "false"}
            )
            result = await self.client.get_text(url, cache_ttl=86400)
            payload = _load(result.text, font)
            items = payload if isinstance(payload, list) else []
            total = len(items)
            hits = parse_search_hits(items, term, font=font)
            warnings.extend(result.warnings)

        if total > len(hits):
            warnings.append("truncated")

        status = "ok" if hits else "no_results"
        return {
            "status": status,
            "query": {"paraula": term, "font": font, "coincidencia": mode},
            "total_hits": total,
            "returned": len(hits),
            "hits": hits,
            "warnings": list(dict.fromkeys(warnings)),
            "note": (
                f"{config['label']}. Per a un dubte d'ús, la GBU és la consulta "
                "adequada; la GEIEC és la versió en línia; la GIEC, la descripció "
                "exhaustiva. Cita sempre el codi d'apartat i el títol."
            ),
            "source": config["api"],
            "retrieved_at": _now(),
            "citation": _citation(term, config["label"]),
        }

    async def text(self, codi: str, *, font: str = "gbu") -> dict[str, Any]:
        codi = " ".join(codi.split())
        if not codi:
            raise InvalidQueryError(
                "Falta el codi d'apartat.",
                hint="Pren el `codi_text` d'una cerca, per exemple `28.1`.",
            )
        if len(codi) > 20 or not all(part.replace("-", "").isalnum() for part in codi.split(".")):
            raise InvalidQueryError(
                f"El codi «{codi}» no té el format esperat.",
                hint="Els codis són números separats per punts, com `28.1`.",
            )
        if font not in GRAMATICAS:
            raise InvalidQueryError(
                f"La font «{font}» no existeix.",
                hint="Fonts disponibles: " + ", ".join(sorted(GRAMATICAS)) + ".",
            )

        config = GRAMATICAS[font]
        if font == "giec":
            url = f"{config['api']}/TextGramatica/{codi}"
        else:
            url = f"{config['api']}/text_by_cody?codi={quote(codi)}"

        result = await self.client.get_text(url, cache_ttl=86400)
        payload = _load(result.text, font)
        data = parse_text(payload, font=font)
        return {
            "status": "ok",
            "font": font,
            **data,
            "warnings": list(result.warnings),
            "note": (f"{config['label']}. Cita el codi d'apartat i el títol de la secció."),
            "source": config["api"],
            "retrieved_at": _now(),
            "citation": _citation(codi, config["label"]),
        }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _citation(term: str, label: str) -> str:
    return (
        f"{label}, Institut d'Estudis Catalans, consulta feta el "
        + datetime.now(UTC).strftime("%d/%m/%Y")
        + f": {term}"
    )


__all__ = ["DEFAULT_FONTS", "GramatiquesAdapter"]
