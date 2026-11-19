"""Adaptador d'ésAdir (CCMA)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from llengua_mcp.errors import (
    InvalidQueryError,
    LlenguaError,
    UpstreamError,
)
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.esadir import parse_fitxa, parse_search
from llengua_mcp.text import clean_text, normalize_key

BASE_URL = "https://www.esadir.cat"
SEARCH_URL = f"{BASE_URL}/cerca/resavancada"

CONDITIONS = {
    normalize_key("coincident"): "0",
    normalize_key("aproximat"): "1",
    normalize_key("comença per"): "2",
    normalize_key("conté"): "3",
    normalize_key("acaba en"): "4",
}

_SECTION_LABELS = {
    "lexic": "lexic",
    "lèxic": "lexic",
    "gramatica": "gramatica",
    "gramàtica": "gramatica",
    "toponim": "toponim",
    "topònim": "toponim",
    "toponims": "toponim",
    "topònims": "toponim",
    "nompropi": "nompropi",
    "nom propi": "nompropi",
    "noms propis": "nompropi",
    "convencions": "convencions",
    "traduccio": "traduccio",
    "traducció": "traduccio",
    "doblatge": "traduccio",
    "altresllengues": "altresllengues",
    "altres llengües": "altresllengues",
    "enllac": "enllac",
    "enllaç": "enllac",
    "enllaços": "enllac",
}
SECTIONS = {normalize_key(key): value for key, value in _SECTION_LABELS.items()}

_ALLOWED_PREFIXES = ("/entrades/", "/toponims/", "/nomspropis/")


def _is_entry_url(url: str) -> bool:
    """Distingeix una fitxa d'entrada dels títols de filmoteca i del llibre d'estil."""

    return urlsplit(url).path.startswith(_ALLOWED_PREFIXES)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class EsadirAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def consulta(
        self,
        termes: str,
        *,
        seccio: str | None = None,
        condicio: str = "coincident",
        limit: int = 5,
    ) -> dict[str, Any]:
        termes = clean_text(termes)
        if not termes:
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Escriu un mot, una expressió o un topònim.",
            )
        if len(termes) > 120:
            raise InvalidQueryError(
                "La consulta és massa llarga per a ésAdir.",
                hint="Consulta un mot o una expressió curta.",
            )
        condition = CONDITIONS.get(normalize_key(condicio))
        if condition is None:
            raise InvalidQueryError(
                f"La condició «{condicio}» no existeix.",
                hint="Condicions: " + ", ".join(CONDITIONS) + ".",
            )
        params = {
            "critericerca": termes,
            "condiciocerca": condition,
            "criteri": "General",
            "marca": "1",
        }
        if seccio:
            key = normalize_key(seccio)
            section = SECTIONS.get(key)
            if section is None:
                raise InvalidQueryError(
                    f"La secció «{seccio}» no existeix.",
                    hint="Seccions: " + ", ".join(sorted(set(SECTIONS.values()))) + ".",
                )
            params["lstTipusElement"] = f"{section}#pagina#general"

        result = await self.client.get_text(SEARCH_URL, params=params, cache_ttl=86400)
        parsed = parse_search(result.text)
        # Les fitxes d'entrada van primer: la filmoteca i el llibre d'estil
        # no són entrades lèxiques.
        ordered = sorted(
            parsed["results"],
            key=lambda item: 0 if _is_entry_url(item["url"]) else 1,
        )
        results = ordered[: max(1, limit)]
        count = parsed["count"]

        warnings = list(dict.fromkeys(result.warnings + parsed["warnings"]))
        if count and count > len(results):
            warnings.append("truncated")
        if count == 0:
            warnings.append("zero_results")
        if condition == "0" and not any(_is_entry_url(item["url"]) for item in ordered):
            warnings.append("no_entry_results")
        status = "ok"
        if count == 0:
            status = "no_results"
        elif count is None and not results:
            status = "unexpected_response"

        payload: dict[str, Any] = {
            "status": status,
            "query": {
                "termes": termes,
                "seccio": seccio,
                "condicio": condicio,
            },
            "result_count": count,
            "returned": len(results),
            "has_more": bool(count and count > len(results)),
            "results": results,
            "warnings": warnings,
            "note": (
                "ésAdir és el portal d'estil de la CCMA, no la norma de l'IEC. "
                "La cerca exacta pot no trobar entrades multiparaula i retornar "
                "títols de filmoteca o documents del llibre d'estil: si apareix "
                "`no_entry_results`, obre la fitxa amb `esadir_fitxa(termes)` "
                "abans de concloure que no hi ha entrada. Un `no_results` amb "
                "`zero_results` és una absència a la cerca, no una prova que la "
                "forma sigui incorrecta."
            ),
            "source": str(result.url),
            "retrieved_at": _now(),
            "citation": (
                "ésAdir (CCMA), consulta feta el "
                + datetime.now(UTC).strftime("%d/%m/%Y")
                + f": {termes}"
            ),
        }
        if "no_entry_results" in warnings:
            payload["suggested_fitxa"] = termes
        if status == "unexpected_response":
            payload["error"] = {
                "code": status,
                "message": "La pàgina d'ésAdir no té el format esperat.",
                "hint": "Pot haver canviat el portal o haver-hi una pàgina d'error.",
            }
        return payload

    async def fitxa(self, entrada: str) -> dict[str, Any]:
        entrada = clean_text(entrada)
        if not entrada:
            raise InvalidQueryError(
                "Falta l'entrada.",
                hint="Indica una URL d'ésAdir, un slug o el títol de la fitxa.",
            )

        candidates = self._candidate_urls(entrada)
        transport_error: LlenguaError | None = None
        for url in candidates:
            try:
                result = await self.client.get_text(url, cache_ttl=86400)
            except UpstreamError as exc:
                if "404" not in exc.message:
                    transport_error = exc
                continue
            parsed = parse_fitxa(result.text)
            if not parsed["found"]:
                continue
            warnings = list(dict.fromkeys(result.warnings + parsed["warnings"]))
            return {
                "status": "ok" if parsed["definitions"] or parsed["examples"] else "partial",
                "title": parsed["title"],
                "labels": parsed["labels"],
                "pronunciation": parsed["pronunciation"],
                "definitions": parsed["definitions"],
                "examples": parsed["examples"],
                "related": parsed["related"],
                "audio_urls": parsed["audio_urls"],
                "audio_note": (
                    "Les URL d'àudio són metadades. No s'ha descarregat cap fitxer "
                    "de /back/, que robots.txt bloqueja."
                ),
                "warnings": warnings,
                "source": url,
                "retrieved_at": _now(),
                "citation": (
                    "ésAdir (CCMA), fitxa «"
                    + parsed["title"]
                    + "», consulta feta el "
                    + datetime.now(UTC).strftime("%d/%m/%Y")
                    + "."
                ),
            }

        if transport_error is not None:
            raise UpstreamError(
                "No s'ha pogut obrir cap candidat de fitxa.",
                hint=transport_error.hint or "Comprova la connexió o el slug.",
                source=transport_error.source,
            )
        raise InvalidQueryError(
            f"No s'ha trobat cap fitxa per a «{entrada}».",
            hint=(
                "Prova el slug exacte (per exemple `a_gust` o `marxa-a-vista`), "
                "una URL `/entrades/fitxa/node/...` o cerca'l amb `esadir_consulta`."
            ),
            source=SEARCH_URL,
        )

    def _candidate_urls(self, entrada: str) -> list[str]:
        if entrada.startswith(("http://", "https://")):
            parts = urlsplit(entrada)
            if parts.netloc.lower() not in {"www.esadir.cat", "esadir.cat"}:
                raise InvalidQueryError(
                    "Només es poden obrir fitxes d'ésAdir.",
                    hint="L'URL ha de ser del domini www.esadir.cat.",
                )
            if not parts.path.startswith(_ALLOWED_PREFIXES):
                raise InvalidQueryError(
                    "Aquest camí d'ésAdir no és una fitxa consultable.",
                    hint="Fes servir un camí `/entrades/`, `/toponims/` o `/nomspropis/`.",
                )
            if "/back/" in parts.path:
                raise InvalidQueryError(
                    "Els fitxers de /back/ no es poden descarregar.",
                    hint="L'àudio es pot enllaçar, però no baixar.",
                )
            return [entrada]

        path = entrada.strip("/")
        if path.startswith(("entrades/", "toponims/", "nomspropis/")):
            return [f"{BASE_URL}/{path}"]

        slug = path.replace(" ", "_")
        candidates = [
            f"{BASE_URL}/entrades/fitxa/node/{slug}",
            f"{BASE_URL}/entrades/fitxa/node/{slug.replace('_', '-')}",
        ]
        if path.isdigit():
            candidates.insert(0, f"{BASE_URL}/entrades/fitxa/id/{path}")
        return list(dict.fromkeys(candidates))


__all__ = ["CONDITIONS", "SECTIONS", "EsadirAdapter"]
