"""Adaptador de l'Optimot (Generalitat de Catalunya)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.optimot import decode_ref, parse_detail, parse_search
from llengua_mcp.text import clean_text, contains_words, normalize_key

BASE_URL = "https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html"
SOURCE = BASE_URL
MANY_RESULTS = 200

MODES = {
    "fitxes": "cerca.fitxes",
    "basica": "cerca.tot",
    "frase_exacta": "cerca.queSignifica",
    "castella_catala": "cerca.traduir",
    "verbs": "cerca.verbs",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relevance(query: str, item: dict[str, Any]) -> tuple[int, str]:
    """Ordena un resultat segons com hi apareix la consulta.

    El portal no dona una puntuació de rellevància: com a màxim, podem
    comprovar si la frase és al títol, al fragment o si hi són totes les
    paraules. És un senyal per ordenar, no una mesura de qualitat.
    """

    query_key = normalize_key(query)
    if not query_key:
        return 0, "none"
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    if contains_words(title, query_key):
        return 3, "title"
    if contains_words(snippet, query_key):
        return 2, "snippet"
    tokens = query_key.split()
    if len(tokens) > 1 and all(contains_words(f"{title} {snippet}", token) for token in tokens):
        return 1, "tokens"
    return 0, "none"


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
        scored = []
        for index, item in enumerate(parsed["results"]):
            score, label = _relevance(consulta, item)
            item["relevance"] = label
            scored.append((score, index, item))
        # Ordenació estable: primer els resultats que contenen la consulta.
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        max_score = scored[0][0] if scored else 0
        results = [item for _, _, item in scored][: max(1, limit)]

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
        multiword = len(normalize_key(consulta).split()) > 1
        if count is not None and count > MANY_RESULTS:
            warnings.append("many_results")
        if multiword and results and max_score == 0:
            warnings.append("low_relevance")
        suggested_mode = None
        if mode == "frase_exacta" and count == 0:
            suggested_mode = "fitxes"
        elif (
            mode in {"fitxes", "basica"}
            and multiword
            and ((count is not None and count > MANY_RESULTS) or max_score == 0)
        ):
            suggested_mode = "frase_exacta"

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
                "no una freqüència d'ús ni un recompte d'ocurrències. Els "
                "resultats s'ordenen per coincidència amb la consulta "
                "(`relevance`); si el mode no és prou precís, `suggested_mode` "
                "proposa una alternativa."
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
        if suggested_mode:
            payload["suggested_mode"] = suggested_mode
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
