"""Adaptador de l'Ortografia catalana (OIEC, IEC) via la seva API pública."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.oiec import API_URL, MATCH_TYPES, parse_search, parse_text


class OiecAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(
        self,
        paraula: str,
        *,
        coincidencia: str = "contains",
    ) -> dict[str, Any]:
        term = " ".join(paraula.split())
        if not term:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu una paraula o un fenomen ortogràfic (per exemple «apòstrof»).",
            )
        if len(term) > 80:
            raise InvalidQueryError(
                "La consulta és massa llarga.",
                hint="Consulta un mot o un fenomen curt.",
            )
        mode = MATCH_TYPES.get(coincidencia.strip().lower())
        if mode is None:
            raise InvalidQueryError(
                f"El tipus de coincidència «{coincidencia}» no existeix.",
                hint="Valors: exact (Coincident) o contains (En qualsevol posició).",
            )

        path = f"/TextOrtografia/cerca/{mode}"
        params = {"paraula": term}
        result = await self.client.get_text(API_URL + path, params=params, cache_ttl=86400)
        data = parse_search(_loads(result.text), term)

        status = "ok" if data["hits"] else "no_results"
        return {
            "status": status,
            "query": {"paraula": term, "coincidencia": mode},
            "total_hits": data["total_hits"],
            "returned": data["returned"],
            "hits": data["hits"],
            "warnings": data["warnings"],
            "note": (
                "L'Ortografia catalana (OIEC) és la referència normativa de "
                "l'ortografia. Cita sempre el codi d'apartat i el títol. "
                "Cada resultat inclou un fragment breu i l'enllaç a la secció."
            ),
            "source": API_URL,
            "retrieved_at": _now(),
            "citation": _citation(term),
        }

    async def text(self, codi: str) -> dict[str, Any]:
        codi = " ".join(codi.split())
        if not codi:
            raise InvalidQueryError(
                "Falta el codi d'apartat.",
                hint="Pren el `codi_text` d'una cerca, per exemple `4.1.2b`.",
            )
        if len(codi) > 20 or not all(part.replace("-", "").isalnum() for part in codi.split(".")):
            raise InvalidQueryError(
                f"El codi «{codi}» no té el format esperat.",
                hint="Els codis són números separats per punts, com `4.1.2b`.",
            )

        result = await self.client.get_text(f"{API_URL}/TextOrtografia/{codi}", cache_ttl=86400)
        data = parse_text(_loads(result.text))
        return {
            "status": "ok",
            **data,
            "warnings": list(result.warnings),
            "note": (
                "L'OIEC és la referència normativa de l'ortografia. Cita el codi "
                "d'apartat i el títol de la secció."
            ),
            "source": API_URL,
            "retrieved_at": _now(),
            "citation": _citation(codi),
        }


def _loads(text: str) -> Any:
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        from llengua_mcp.errors import UnexpectedResponseError

        raise UnexpectedResponseError(
            "La resposta de l'OIEC no és JSON vàlid.",
            hint="L'API pot haver canviat o haver retornat una pàgina d'error.",
            source=API_URL,
        ) from exc


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _citation(term: str) -> str:
    return (
        "Ortografia catalana (OIEC), Institut d'Estudis Catalans, consulta feta el "
        + datetime.now(UTC).strftime("%d/%m/%Y")
        + f": {term}"
    )


__all__ = ["OiecAdapter"]
