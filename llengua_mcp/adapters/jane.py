"""Adaptador del diccionari de sinònims d'Albert Jané (IEC)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient, HttpResult
from llengua_mcp.parsers.jane import (
    AJAX_URL,
    COLUMNS,
    FUNCIO_COLUMNS,
    SOURCE_URLS,
    parse_bootstrap,
    parse_rows,
)
from llengua_mcp.text import clean_text, normalize_key

BOOTSTRAP_TTL_SECONDS = 600
DEFAULT_CACHE_TTL_SECONDS = 86400
MAX_LIMIT = 20
MIN_QUERY = 2

MODES = {
    "lema": {"url": SOURCE_URLS["lema"], "columns": COLUMNS, "var": "wdt_var1"},
    "general": {"url": SOURCE_URLS["general"], "columns": COLUMNS, "var": "wdt_var2"},
    "funcio": {
        "url": SOURCE_URLS["funcio"],
        "columns": FUNCIO_COLUMNS,
        "var": "wdt_var3",
    },
}

# Codis del desplegable «funció sintàctica» del web.
FUNCIONS = {
    "adjectiva": "1",
    "adverbial": "8",
    "conjuntiva": "9",
    "determinant": "5",
    "formularia": "14",
    "interjectiva": "11",
    "nominal": "3",
    "oracional": "12",
    "paremial": "13",
    "prepositiva": "10",
    "pronominal": "4",
    "quantificadora": "6",
    "verbal": "7",
    "altra": "0",
    "altra funcio": "0",
    "una altra funcio": "0",
}

LICENSE = "CC BY-NC-ND 3.0 ES"
FUNCIONS_LABELS = (
    "adjectiva",
    "adverbial",
    "conjuntiva",
    "determinant",
    "formularia",
    "interjectiva",
    "nominal",
    "oracional",
    "paremial",
    "prepositiva",
    "pronominal",
    "quantificadora",
    "verbal",
    "altra",
)
ATTRIBUTION = (
    "Diccionari de sinònims d'Albert Jané, tercera edició en línia (2015), "
    "IEC. © Albert Jané i Riera; © Institut d'Estudis Catalans."
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _build_body(
    *,
    columns: tuple[str, ...],
    nonce: str,
    offset: int,
    limit: int,
) -> str:
    pairs: list[tuple[str, str]] = [
        ("draw", "1"),
        ("start", str(offset)),
        ("length", str(limit)),
        ("search[value]", ""),
        ("search[regex]", "false"),
        ("order[0][column]", str(columns.index("ordenacio"))),
        ("order[0][dir]", "asc"),
        ("wdtNonce", nonce),
    ]
    for index, name in enumerate(columns):
        pairs.extend(
            [
                (f"columns[{index}][data]", name),
                (f"columns[{index}][name]", name),
                (f"columns[{index}][searchable]", "true"),
                (f"columns[{index}][orderable]", "true"),
                (f"columns[{index}][search][value]", ""),
                (f"columns[{index}][search][regex]", "false"),
            ]
        )
    return urlencode(pairs)


class JaneAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client
        self._bootstrap: dict[str, dict[str, Any]] = {}
        self._bootstrap_at: dict[str, float] = {}

    async def _bootstrap_data(self, mode: str, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._bootstrap.get(mode)
        if (
            not force
            and cached is not None
            and now - self._bootstrap_at.get(mode, 0.0) < BOOTSTRAP_TTL_SECONDS
        ):
            return cached

        source = MODES[mode]["url"]
        result = await self.client.get_text(source, cache_ttl=60, use_cache=not force)
        data = parse_bootstrap(result.text, source=source)
        self._bootstrap[mode] = data
        self._bootstrap_at[mode] = now
        return data

    async def _post(
        self, mode: str, bootstrap: dict[str, Any], body: str
    ) -> tuple[dict[str, Any], HttpResult]:
        source = MODES[mode]["url"]
        var = MODES[mode]["var"]
        value = quote(str(bootstrap["query"]), safe="")
        url = f"{AJAX_URL}?action=get_wdtable&table_id={bootstrap['table_id']}&{var}={value}"
        if mode == "funcio":
            url += f"&wdt_var4={bootstrap['funcio']}"
        return await self.client.post_json(
            url,
            body,
            headers={
                "Referer": source,
                "Origin": "https://sinonims.iec.cat",
            },
            cache_ttl=DEFAULT_CACHE_TTL_SECONDS,
        )

    async def cerca(
        self,
        paraula: str,
        *,
        mode: str = "lema",
        funcio: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        text = clean_text(paraula)
        if not text:
            raise InvalidQueryError(
                "Falta la paraula.",
                hint="Indica un mot o una expressió curta (per exemple «maliciós»).",
            )
        if len(text) < MIN_QUERY:
            raise InvalidQueryError(
                "La paraula és massa curta.",
                hint="Calen com a mínim dos caràcters.",
            )
        if len(text) > 80:
            raise InvalidQueryError(
                "La paraula és massa llarga.",
                hint="Consulta un mot o una expressió curta.",
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, MAX_LIMIT))

        mode_key = normalize_key(mode)
        if mode_key not in MODES:
            raise InvalidQueryError(
                f"El mode «{mode}» no existeix.",
                hint="Modes: " + ", ".join(MODES) + ".",
            )

        function_code: str | None = None
        function_label: str | None = None
        if mode_key == "funcio":
            if not funcio:
                raise InvalidQueryError(
                    "Falta la funció sintàctica.",
                    hint=(
                        "Indica `funcio` (per exemple «nominal», «adjectiva» o "
                        "«verbal»). Funcions: " + ", ".join(FUNCIONS_LABELS) + "."
                    ),
                )
            key = normalize_key(funcio)
            function_code = FUNCIONS.get(key)
            if function_code is None:
                raise InvalidQueryError(
                    f"La funció «{funcio}» no existeix.",
                    hint="Funcions: " + ", ".join(FUNCIONS_LABELS) + ".",
                )
            function_label = key
        elif funcio:
            raise InvalidQueryError(
                '`funcio` només es pot fer servir amb `mode="funcio"`.',
                hint="Treu `funcio` o canvia el mode.",
            )

        bootstrap = await self._bootstrap_data(mode_key)
        bootstrap = {**bootstrap, "query": text, "funcio": function_code}
        body = _build_body(
            columns=MODES[mode_key]["columns"],
            nonce=str(bootstrap["nonce"]),
            offset=offset,
            limit=limit,
        )
        try:
            payload, result = await self._post(mode_key, bootstrap, body)
        except UnexpectedResponseError:
            # El nonce pot haver caducat. Refresquem-lo i ho provem una sola vegada.
            bootstrap = await self._bootstrap_data(mode_key, force=True)
            bootstrap = {**bootstrap, "query": text, "funcio": function_code}
            body = _build_body(
                columns=MODES[mode_key]["columns"],
                nonce=str(bootstrap["nonce"]),
                offset=offset,
                limit=limit,
            )
            try:
                payload, result = await self._post(mode_key, bootstrap, body)
            except UnexpectedResponseError as exc:
                raise UnexpectedResponseError(
                    "El diccionari de sinònims no ha retornat cap resposta vàlida.",
                    hint=(
                        "El nonce o la taula del web poden haver canviat. "
                        "Torna-ho a provar més tard; si continua, cal revisar el parser."
                    ),
                    source=MODES[mode_key]["url"],
                ) from exc

        data = parse_rows(payload, columns=MODES[mode_key]["columns"])
        results = data["results"]
        total = data["total"]

        warnings = _dedupe(list(result.warnings) + list(data["warnings"]))
        status = "ok"
        error = None
        if total is None:
            status = "unexpected_response"
            error = {
                "code": status,
                "message": (
                    "El comptador de resultats falta o no és vàlid i no hi ha "
                    "cap fila: no es pot afirmar que no hi hagi entrades."
                ),
                "hint": (
                    "Torna-ho a provar; si continua, la taula pot haver canviat de "
                    "format. No és una absència verificada."
                ),
            }
        elif total == 0 and not results:
            status = "no_results"
            warnings.append("zero_results")
        elif total > 0 and not results and offset >= total:
            warnings.append("offset_out_of_range")
        elif total > 0 and not results:
            status = "unexpected_response"
            error = {
                "code": status,
                "message": "El web dona un total positiu però no s'han pogut llegir entrades.",
                "hint": "La taula pot haver canviat de format; no és una absència.",
            }

        has_more = total is not None and total > offset + len(results)
        if has_more:
            warnings.append("truncated")

        response: dict[str, Any] = {
            "status": status,
            "query": {
                "paraula": text,
                "mode": mode_key,
                "funcio": function_label,
                "limit": limit,
                "offset": offset,
            },
            "total": total,
            "catalog_total": data["catalog_total"],
            "returned": len(results),
            "has_more": has_more,
            "next_offset": offset + len(results) if has_more else None,
            "results": results,
            "modes": list(MODES),
            "funcions": list(FUNCIONS_LABELS),
            "warnings": _dedupe(warnings),
            "note": (
                "Les accepcions numerades (`1.`, `2.`) separen sentits: tria la "
                'que encaixi en la frase abans de substituir res. `mode="general"` '
                "cerca el mot també dins les llistes de sinònims (no és una cerca "
                'per frases) i `mode="funcio"` el cerca per funció sintàctica. '
                "Els sinònims són propostes de significat, no equivalents exactes."
            ),
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "source": MODES[mode_key]["url"],
            "retrieved_at": _now(),
        }
        if error:
            response["error"] = error
        return response


__all__ = ["FUNCIONS", "JaneAdapter", "MODES"]
