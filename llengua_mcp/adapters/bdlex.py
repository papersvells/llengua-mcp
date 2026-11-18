"""Adaptador de BDLex (IEC): diccionaris històrics i dialectals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from llengua_mcp.errors import InvalidQueryError, UnexpectedResponseError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.bdlex import DICTIONARY_LABELS, parse_entries, parse_ids
from llengua_mcp.text import normalize_key

MOTOR_URL = "https://motor-bdlex.iec.cat/bdlex"
PUBLIC_URL = "https://bdlex.iec.cat/"
DEFAULT_DICTS = ("DCVB", "DIEe")
MAX_FETCH_IDS = 20
_DICT_PRIORITY = {
    code: index
    for index, code in enumerate(
        ("DIEe", "DIE2", "DIEC", "DCVB", "DGLC", "DGFP", "DPCV", "DGMG", "DMCT", "NDMA")
    )
}
MATCH_TYPES = {
    "exact": "exact",
    "coincident": "exact",
    "contains": "contains",
    "conte": "contains",
    "starts-with": "starts-with",
    "comenca": "starts-with",
    "ends-with": "ends-with",
    "acaba": "ends-with",
}


def _canonical_dicts(dicts: list[str] | None) -> list[str]:
    if not dicts:
        return list(DEFAULT_DICTS)
    by_lower = {code.lower(): code for code in DICTIONARY_LABELS}
    result: list[str] = []
    for item in dicts:
        code = by_lower.get(item.strip().lower())
        if code is None:
            raise InvalidQueryError(
                f"El diccionari «{item}» no existeix a BDLex.",
                hint="Codis disponibles: " + ", ".join(sorted(DICTIONARY_LABELS)) + ".",
            )
        if code not in result:
            result.append(code)
    return result


def _query_url(params: list[tuple[str, str]]) -> str:
    return f"{MOTOR_URL}?{urlencode(params, doseq=True, safe='[]')}"


class BdlexAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def consulta(
        self,
        paraula: str | None = None,
        *,
        definicio: str | None = None,
        exemple: str | None = None,
        text_lliure: str | None = None,
        dicts: list[str] | None = None,
        coincidencia: str = "exact",
        limit: int = 5,
        max_senses: int = 6,
    ) -> dict[str, Any]:
        term = " ".join((paraula or "").split())
        definition = " ".join((definicio or "").split())
        example = " ".join((exemple or "").split())
        free_text = " ".join((text_lliure or "").split())
        if not any((term, definition, example, free_text)):
            raise InvalidQueryError(
                "La consulta és buida.",
                hint="Indica una paraula, una definició, un exemple o un text lliure.",
            )
        for label, value in (
            ("paraula", term),
            ("definició", definition),
            ("exemple", example),
            ("text lliure", free_text),
        ):
            if len(value) > 120:
                raise InvalidQueryError(
                    f"El camp «{label}» és massa llarg per a BDLex.",
                    hint="Consulta un mot, una expressió o un fragment curt.",
                )
        match = MATCH_TYPES.get(coincidencia.strip().lower())
        if match is None:
            raise InvalidQueryError(
                f"El tipus de coincidència «{coincidencia}» no existeix.",
                hint="Valors: exact, contains, starts-with, ends-with.",
            )
        selected_dicts = _canonical_dicts(dicts)
        limit = max(1, min(limit, 10))
        max_senses = max(1, min(max_senses, 15))

        zones: list[tuple[str, str]] = []
        if term:
            zones.extend([("key_ext", term), ("key_ext_type", match)])
        if definition:
            zones.extend([("def[]", definition), ("def_type", "all")])
        if example:
            zones.extend([("exs[]", example), ("exs_type", "all")])
        if free_text:
            zones.append(("text[]", free_text))

        ids_url = _query_url(
            [
                *zones,
                ("element", "entry"),
                *[("dict[]", code) for code in selected_dicts],
                ("result_type", "ids"),
            ]
        )
        ids_result = await self.client.get_text(ids_url, cache_ttl=86400)
        try:
            ids = parse_ids(ids_result.text)
        except ET.ParseError as exc:
            raise UnexpectedResponseError(
                "La resposta d'identificadors de BDLex no és XML vàlid.",
                hint="El servei pot haver canviat de protocol; cal revisar el parser.",
                source=PUBLIC_URL,
            ) from exc

        warnings = list(ids_result.warnings)
        if not ids:
            return {
                "status": "no_results",
                "query": {
                    "paraula": term or None,
                    "definicio": definition or None,
                    "exemple": example or None,
                    "text_lliure": free_text or None,
                    "dicts": selected_dicts,
                    "coincidencia": match,
                },
                "total_entries": 0,
                "returned": 0,
                "entries": [],
                "warnings": warnings,
                "note": (
                    "No hi ha cap entrada que respongui a aquesta consulta. "
                    "Prova el singular, una variant ortogràfica o `coincidencia=contains`."
                ),
                "source": PUBLIC_URL,
                "retrieved_at": _now(),
                "citation": _citation(term or definition or example or free_text),
            }

        fetched_ids = ids[:MAX_FETCH_IDS]
        if len(ids) > len(fetched_ids) or len(ids) > limit:
            warnings.append("truncated")
        entries_url = _query_url(
            [
                *[("entry_id[]", entry_id) for entry_id in fetched_ids],
                ("element", "entry"),
            ]
        )
        entries_result = await self.client.get_text(entries_url, cache_ttl=86400)
        try:
            entries = parse_entries(entries_result.text, max_senses=max_senses)
        except ET.ParseError as exc:
            raise UnexpectedResponseError(
                "La resposta d'entrades de BDLex no és XML vàlid.",
                hint="El servei pot haver canviat de protocol; cal revisar el parser.",
                source=PUBLIC_URL,
            ) from exc

        warnings.extend(entries_result.warnings)
        if len(entries) < len(fetched_ids):
            warnings.append("parse_partial")

        # El motor retorna variants i entrades creuades abans de l'article
        # principal. Prioritzem la coincidència exacta de la forma buscada.
        query_key = normalize_key(term) if term else ""
        entries.sort(
            key=lambda entry: (
                bool(query_key) and normalize_key(entry.get("headword", "")) != query_key,
                not any(sense.get("definition") for sense in entry.get("senses", [])),
                _DICT_PRIORITY.get(entry.get("dictionary", ""), 99),
            )
        )
        entries = entries[:limit]
        if any(entry.get("senses_truncated") for entry in entries):
            warnings.append("senses_truncated")
        if any(
            entry.get("phonetics_truncated")
            or entry.get("synonyms_truncated")
            or entry.get("phrases_truncated")
            or any(sense.get("subentries_truncated") for sense in entry.get("senses", []))
            for entry in entries
        ):
            warnings.append("details_truncated")
        for entry in entries:
            entry["exact_headword"] = bool(query_key) and (
                normalize_key(entry.get("headword", "")) == query_key
            )

        return {
            "status": "ok" if entries else "unexpected_response",
            "query": {
                "paraula": term or None,
                "definicio": definition or None,
                "exemple": example or None,
                "text_lliure": free_text or None,
                "dicts": selected_dicts,
                "coincidencia": match,
            },
            "total_entries": len(ids),
            "returned": len(entries),
            "has_more": len(ids) > len(entries),
            "entries": entries,
            "warnings": list(dict.fromkeys(warnings)),
            "note": (
                "BDLex agrupa diccionaris de períodes i abasts diferents. "
                "La presència d'una forma no la converteix en normativa actual; "
                "una absència tampoc no la fa incorrecta. Cita sempre el diccionari concret."
            ),
            "source": PUBLIC_URL,
            "retrieved_at": _now(),
            "citation": _citation(term or definition or example or free_text),
        }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _citation(term: str) -> str:
    return (
        "BDLex (Institut d'Estudis Catalans), consulta feta el "
        + datetime.now(UTC).strftime("%d/%m/%Y")
        + f": {term}"
    )


__all__ = ["BdlexAdapter", "DEFAULT_DICTS", "DICTIONARY_LABELS", "MATCH_TYPES"]
