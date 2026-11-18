"""Adaptador de l'Optimot (Generalitat de Catalunya)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.optimot import decode_ref, parse_detail, parse_search
from llengua_mcp.text import clean_text

BASE_URL = "https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html"
SOURCE = BASE_URL

MODES = {
    "fitxes": "cerca.fitxes",
    "basica": "cerca.tot",
    "frase_exacta": "cerca.queSignifica",
    "castella_catala": "cerca.traduir",
    "verbs": "cerca.verbs",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class OptimotAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(
        self,
        consulta: str,
        *,
        mode: str = "fitxes",
        limit: int = 5,
    ) -> dict[str, Any]:
        consulta = clean_text(consulta)
        if not consulta:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu una paraula, una expressió o una frase curta.",
            )
        if mode not in MODES:
            raise InvalidQueryError(
                f"El mode «{mode}» no existeix.",
                hint="Modes disponibles: " + ", ".join(MODES) + ".",
            )
        if len(consulta) > 120:
            raise InvalidQueryError(
                "La consulta és massa llarga per a l'Optimot.",
                hint="Consulta un mot, una expressió o una frase curta.",
            )

        params = {
            "action": "Principal",
            "method": "cerca_generica",
            "input_cercar": consulta,
            "tipusCerca": MODES[mode],
        }
        result = await self.client.get_text(BASE_URL, params=params)
        parsed = parse_search(result.text)

        count = parsed["count"]
        results = parsed["results"][: max(1, limit)]
        status = "ok"
        error = None
        if count is None and not results:
            status = "unexpected_response"
            error = {
                "code": status,
                "message": "La pàgina de l'Optimot no té el format esperat.",
                "hint": "Pot haver canviat el portal o haver-hi una pàgina d'error.",
            }
        elif count == 0 and not results:
            status = "no_results"
        elif count and not results:
            status = "unexpected_response"
            error = {
                "code": status,
                "message": (
                    "El portal dona un recompte positiu però no s'han pogut llegir candidats."
                ),
            }

        for item in results:
            item.pop("params", None)

        warnings = list(parsed["warnings"])
        if count is not None and count > len(results):
            warnings.append("truncated")
        if result.warnings:
            warnings.extend(result.warnings)

        payload: dict[str, Any] = {
            "status": status,
            "query": {"consulta": consulta, "mode": mode},
            "result_count": count,
            "returned": len(results),
            "has_more": bool(count and count > len(results)),
            "results": results,
            "warnings": list(dict.fromkeys(warnings)),
            "note": (
                "El nombre de resultats és un recompte de documents del portal, "
                "no una freqüència d'ús ni un recompte d'ocurrències."
            ),
            "source": str(result.url),
            "retrieved_at": _now(),
            "citation": (
                "Optimot (Departament de Política Lingüística), consulta feta el "
                + datetime.now(UTC).strftime("%d/%m/%Y")
                + f": {consulta}"
            ),
        }
        if error:
            payload["error"] = error
        return payload

    async def fitxa(self, ref: str) -> dict[str, Any]:
        try:
            params = decode_ref(ref)
        except ValueError as exc:
            raise InvalidQueryError(
                "La referència de fitxa no és vàlida.",
                hint="Fes servir el `detail_ref` retornat per `optimot_cerca`.",
                source=SOURCE,
            ) from exc

        if not params.get("idFont"):
            raise InvalidQueryError(
                "La referència no identifica cap fitxa.",
                hint="Torna a fer la cerca i obre un candidat amb `detail_ref`.",
                source=SOURCE,
            )

        method = params.get("method", "detall")
        if method not in {"detall", "detall_completa"}:
            method = "detall"
        query = {
            key: value
            for key, value in params.items()
            if key
            in {
                "action",
                "method",
                "input_cercar",
                "numPagina",
                "database",
                "idFont",
                "idHit",
                "tipusFont",
                "numeroResultat",
                "clickLink",
                "titol",
                "tipusCerca",
            }
        }
        query["action"] = "Principal"
        query["method"] = method

        result = await self.client.get_text(BASE_URL, params=query, cache_ttl=86400)
        parsed = parse_detail(result.text)
        if not parsed["title"] and not parsed["sections"]:
            raise UnexpectedResponseError(
                "No s'ha pogut llegir la fitxa.",
                hint=(
                    "El detall pot dependre de paràmetres de la cerca o haver canviat "
                    "de format. Torna a fer `optimot_cerca` i obre un altre candidat."
                ),
                source=str(result.url),
            )

        status = "ok" if parsed["title"] and parsed["sections"] else "partial"
        warnings = list(dict.fromkeys(result.warnings + parsed["warnings"]))
        return {
            "status": status,
            "fitxa": parsed["fitxa_number"],
            "version": parsed["version"],
            "title": parsed["title"],
            "sections": parsed["sections"],
            "related": parsed["related"],
            "font": params.get("tipusFont"),
            "warnings": warnings,
            "note": (
                "Cal citar la font original de la fitxa (Optimot, DIEC, TERMCAT...) "
                "i la data de versió quan consti."
            ),
            "source": str(result.url),
            "retrieved_at": _now(),
            "citation": (
                "Optimot, fitxa "
                f"{parsed['fitxa_number'] or ''}"
                + (f" (versió {parsed['version']})" if parsed["version"] else "")
                + f", consulta feta el {datetime.now(UTC).strftime('%d/%m/%Y')}."
            ),
        }


__all__ = ["MODES", "OptimotAdapter"]
