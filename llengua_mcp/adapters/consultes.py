"""Adaptador del Corpus de consultes lingüístiques de l'IEC."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient, HttpResult
from llengua_mcp.parsers.consultes import (
    AJAX_URL,
    COLUMNS,
    PREGUNTA_COLUMN,
    SOURCE_URL,
    TEMA_COLUMN,
    parse_bootstrap,
    parse_rows,
)
from llengua_mcp.text import clean_text, normalize_key

BOOTSTRAP_TTL_SECONDS = 600
MAX_LIMIT = 20


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _column_filter(index: int, text: str, tema: str | None, camp: str) -> str:
    if index == TEMA_COLUMN and tema:
        return tema
    if index == PREGUNTA_COLUMN and camp == "pregunta":
        return text
    return ""


def _build_body(
    bootstrap: dict[str, Any],
    *,
    text: str,
    tema: str | None,
    camp: str,
    offset: int,
    limit: int,
) -> str:
    pairs: list[tuple[str, str]] = [
        ("draw", "1"),
        ("start", str(offset)),
        ("length", str(limit)),
        ("search[value]", "" if camp == "pregunta" else text),
        ("search[regex]", "false"),
        ("order[0][column]", "0"),
        ("order[0][dir]", "desc"),
        ("wdtNonce", str(bootstrap["nonce"])),
    ]
    for index, name in enumerate(COLUMNS):
        pairs.extend(
            [
                (f"columns[{index}][data]", name),
                (f"columns[{index}][name]", name),
                (f"columns[{index}][searchable]", "true"),
                (f"columns[{index}][orderable]", "true"),
                (f"columns[{index}][search][value]", _column_filter(index, text, tema, camp)),
                (f"columns[{index}][search][regex]", "false"),
            ]
        )
    return urlencode(pairs)


class ConsultesAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client
        self._bootstrap: dict[str, Any] | None = None
        self._bootstrap_at = 0.0

    async def _bootstrap_data(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            not force
            and self._bootstrap is not None
            and now - self._bootstrap_at < BOOTSTRAP_TTL_SECONDS
        ):
            return self._bootstrap

        result = await self.client.get_text(SOURCE_URL, cache_ttl=60, use_cache=not force)
        data = parse_bootstrap(result.text)
        self._bootstrap = data
        self._bootstrap_at = now
        return data

    async def _post(
        self, bootstrap: dict[str, Any], body: str
    ) -> tuple[dict[str, Any], HttpResult]:
        url = f"{AJAX_URL}?action=get_wdtable&table_id={bootstrap['table_id']}"
        return await self.client.post_json(
            url,
            body,
            headers={
                "Referer": SOURCE_URL,
                "Origin": "https://consultes-linguistiques.iec.cat",
            },
            cache_ttl=600,
        )

    async def cerca(
        self,
        cerca: str | None = None,
        *,
        tema: str | None = None,
        camp: str = "tot",
        limit: int = 5,
        offset: int = 0,
    ) -> dict[str, Any]:
        text = clean_text(cerca) if cerca else ""
        if len(text) > 120:
            raise InvalidQueryError(
                "La consulta és massa llarga.",
                hint="Consulta un mot o una expressió curta.",
            )
        if not text and not tema:
            raise InvalidQueryError(
                "Falta la cerca o el tema.",
                hint=(
                    "Indica un text a `cerca` o un `tema` (Fonètica, Lèxic, "
                    "Morfologia, Onomàstica, Ortografia, Sintaxi o Altres)."
                ),
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, MAX_LIMIT))

        camp_key = normalize_key(camp)
        if camp_key not in {"tot", "pregunta"}:
            raise InvalidQueryError(
                f"El camp «{camp}» no existeix.",
                hint="Valors: `tot` (pregunta i resposta) o `pregunta` (només la pregunta).",
            )

        bootstrap = await self._bootstrap_data()
        theme = clean_text(tema) if tema else None
        if theme:
            match = next(
                (
                    available
                    for available in bootstrap["themes"]
                    if normalize_key(available) == normalize_key(theme)
                ),
                None,
            )
            if bootstrap["themes"] and match is None:
                raise InvalidQueryError(
                    f"El tema «{theme}» no existeix.",
                    hint="Temes disponibles: " + ", ".join(bootstrap["themes"]) + ".",
                )
            theme = match or theme

        body = _build_body(
            bootstrap,
            text=text,
            tema=theme,
            camp=camp_key,
            offset=offset,
            limit=limit,
        )
        try:
            payload, result = await self._post(bootstrap, body)
        except UnexpectedResponseError:
            # El nonce pot haver caducat. Refresquem-lo i ho provem una sola vegada.
            bootstrap = await self._bootstrap_data(force=True)
            body = _build_body(
                bootstrap,
                text=text,
                tema=theme,
                camp=camp_key,
                offset=offset,
                limit=limit,
            )
            try:
                payload, result = await self._post(bootstrap, body)
            except UnexpectedResponseError as exc:
                raise UnexpectedResponseError(
                    "La consulta de l'IEC no ha retornat cap resposta vàlida.",
                    hint=(
                        "El nonce o la taula del portal poden haver canviat. "
                        "Torna-ho a provar més tard; si continua, cal revisar el parser."
                    ),
                    source=SOURCE_URL,
                ) from exc

        data = parse_rows(payload)
        results = data["results"]
        total = data["total"]

        warnings = _dedupe(list(result.warnings) + list(data["warnings"]))
        status = "ok"
        error = None
        if total == 0 and not results:
            status = "no_results"
            warnings.append("zero_results")
        elif total > 0 and not results and offset >= total:
            # Pàgina més enllà del total: no és un error de format.
            warnings.append("offset_out_of_range")
        elif total > 0 and not results:
            status = "unexpected_response"
            error = {
                "code": status,
                "message": (
                    "El portal dona un total positiu però no s'han pogut llegir consultes."
                ),
                "hint": "La taula pot haver canviat de format; no és una absència.",
            }

        has_more = total > offset + len(results)
        if has_more:
            warnings.append("truncated")

        response: dict[str, Any] = {
            "status": status,
            "query": {
                "cerca": text or None,
                "tema": theme,
                "camp": camp_key,
                "limit": limit,
                "offset": offset,
            },
            "total": total,
            "corpus_total": data["corpus_total"],
            "returned": len(results),
            "has_more": has_more,
            "next_offset": offset + len(results) if has_more else None,
            "results": results,
            "available_themes": bootstrap["themes"],
            "warnings": _dedupe(warnings),
            "note": (
                "Són respostes curades del Corpus de consultes lingüístiques de "
                "l'IEC. Cal citar la consulta i enllaçar la font; no substitueixen "
                "la norma ni la fitxa d'una altra font. Per buscar una pregunta "
                "semblant, `camp='pregunta'` sol ser més precís."
            ),
            "source": SOURCE_URL,
            "retrieved_at": _now(),
            "citation": (
                "Corpus de consultes lingüístiques de l'IEC, consulta feta el "
                + datetime.now(UTC).strftime("%d/%m/%Y")
                + f": {text or theme or ''}"
            ),
        }
        if error:
            response["error"] = error
        return response


__all__ = ["ConsultesAdapter"]
