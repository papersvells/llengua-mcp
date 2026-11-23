"""Adaptador de la Paremiologia catalana comparada digital."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

from llengua_mcp.errors import InvalidQueryError, UpstreamError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.pccd import BASE_URL, parse_fitxa, parse_search
from llengua_mcp.text import clean_text

SEARCH_URL = f"{BASE_URL}/"
CONDITIONS = {"conté": "", "coincident": "coincident"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PccdAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(
        self,
        consulta: str,
        *,
        inclou_variants: bool = False,
        condicio: str = "conté",
        limit: int = 10,
    ) -> dict[str, Any]:
        consulta = clean_text(consulta)
        if not consulta:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu un refrany o un fragment.",
            )
        if len(consulta) > 160:
            raise InvalidQueryError(
                "La consulta és massa llarga.",
                hint="Consulta un fragment més curt.",
            )
        if condicio not in CONDITIONS:
            raise InvalidQueryError("Condició no admesa.", hint="Tria «conté» o «coincident».")

        params = {
            "cerca": consulta,
            "mode": CONDITIONS[condicio],
            "mostra": str(max(1, min(limit, 50))),
        }
        if inclou_variants:
            params["variant"] = ""
        result = await self.client.get_text(SEARCH_URL, params=params, cache_ttl=86400)
        parsed = parse_search(result.text, consulta)
        warnings = list(dict.fromkeys(result.warnings + parsed["warnings"]))
        verified_zero = (
            parsed["count"] == 0
            and parsed["no_results_message"]
            and parsed["query_echo_verified"]
            and parsed["no_results_query_verified"]
            and not parsed["results"]
        )
        status = "ok"
        if verified_zero:
            status = "no_results"
            warnings.append("zero_results")
        elif (
            not parsed["query_echo_verified"]
            or parsed["count"] is None
            or parsed["no_results_message"]
            or (parsed["count"] > 0 and parsed["no_results_query_verified"])
            or parsed["count"] == 0
        ):
            status = "unexpected_response"
            warnings.append(
                "query_echo_unverified"
                if not parsed["query_echo_verified"]
                else "zero_unverified"
                if parsed["no_results_message"] or parsed["count"] == 0
                or parsed["no_results_query_verified"]
                else "count_unverified"
            )

        count = parsed["count"] if status in {"ok", "no_results"} else None
        if count is not None and count > len(parsed["results"]):
            warnings.append("truncated")
        return {
            "status": status,
            "query": {
                "consulta": consulta,
                "inclou_variants": inclou_variants,
                "condicio": condicio,
            },
            "result_count": count,
            "returned": len(parsed["results"]),
            "results": parsed["results"][: max(1, min(limit, 50))],
            "warnings": warnings,
            "source": SEARCH_URL,
            "retrieved_at": _now(),
            "citation": f"PCCD, cerca feta el {_now()}.",
        }

    async def fitxa(self, entrada: str, *, limit: int = 20) -> dict[str, Any]:
        entrada = clean_text(entrada)
        if not entrada:
            raise InvalidQueryError(
                "La fitxa és buida.",
                hint="Passa el títol d’un resultat o l’URL /p/… retornat per la cerca.",
            )
        if entrada.startswith(("https://", "http://")):
            parsed_url = urlsplit(entrada)
            if parsed_url.netloc != urlsplit(BASE_URL).netloc or not parsed_url.path.startswith(
                "/p/"
            ):
                raise InvalidQueryError(
                    "L’URL no és una fitxa de la PCCD.",
                    hint="Fes servir l’URL /p/ retornat per pccd_cerca.",
                )
            url = entrada
        elif entrada.startswith("/p/"):
            url = f"{BASE_URL}{entrada}"
        else:
            slug = entrada.replace("/", "\\").replace(" ", "_")
            url = f"{BASE_URL}/p/{quote(slug, safe='')}"
        result = await self.client.get_text(url, cache_ttl=86400)
        parsed = parse_fitxa(result.text)
        if not parsed["found"]:
            if result.status == 404:
                raise UpstreamError(
                    "La fitxa de la PCCD no existeix.",
                    hint="Cerca el refrany amb pccd_cerca i obre l’URL d’un resultat.",
                    source=url,
                )
            return {
                "status": "unexpected_response",
                "url": url,
                "warnings": list(dict.fromkeys(result.warnings + parsed["warnings"])),
                "source": url,
            }
        variants = parsed["variants"]
        max_variants = max(1, min(limit, 50))
        truncated = len(variants) > max_variants
        limited_variants = []
        for variant in variants[:max_variants]:
            item = dict(variant)
            item["citations"] = item["citations"][:5]
            if len(variant["citations"]) > 5:
                truncated = True
            limited_variants.append(item)
        warnings = list(result.warnings + parsed["warnings"])
        if truncated:
            warnings.append("truncated")
        return {
            "status": "ok",
            **{
                key: value
                for key, value in parsed.items()
                if key not in {"found", "warnings", "variants"}
            },
            "variants": limited_variants,
            "variants_total": len(variants),
            "url": url,
            "warnings": warnings,
            "source": url,
            "retrieved_at": _now(),
            "citation": f"PCCD, fitxa «{parsed['title']}», consultada el {_now()}.",
            "note": (
                "La datació més antiga és la que consta al recull, no necessàriament "
                "la primera documentació absoluta. Els recomptes descriuen el "
                "contingut de la fitxa, no la freqüència d’ús."
            ),
        }
