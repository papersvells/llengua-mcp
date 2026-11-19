"""Adaptador del CTILC (IEC)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, quote_plus

from llengua_mcp.compiler import (
    compile_pattern,
    patro_query,
    phrase_elements,
    phrase_query,
)
from llengua_mcp.config import Settings
from llengua_mcp.cursors import CursorStore
from llengua_mcp.errors import (
    InvalidQueryError,
    LlenguaError,
    StaleSearchError,
    UpstreamError,
)
from llengua_mcp.http import HttpClient
from llengua_mcp.models import CtilcFilters, CursorPayload, PatternElement
from llengua_mcp.parsers.basiques import parse_basiques
from llengua_mcp.parsers.collocacions import COLLOCACIONS_URL, parse_collocacions
from llengua_mcp.parsers.ctilc import parse_ctilc_page, patterns_equivalent
from llengua_mcp.parsers.dades import parse_dades
from llengua_mcp.parsers.dispersions import (
    DIAL_URL,
    parse_cronologia,
    parse_dialectal,
)
from llengua_mcp.parsers.filtres import (
    EXTRA_PARAMS,
    FILTRES_URL,
    KINDS,
    parse_filter_values,
)
from llengua_mcp.parsers.fitxa import parse_fitxa
from llengua_mcp.parsers.obres import parse_authors, parse_works
from llengua_mcp.tagset import tagset_payload
from llengua_mcp.text import clean_text, normalize_key

BASE = "https://ctilc.iec.cat/scripts"
COOCUR_URL = f"{BASE}/CTILCQConc_Coocur2.asp"
FITXA_URL = f"{BASE}/CTILCQFitxaLocalitzacio.asp"
DADES_URL = f"{BASE}/CTILCQDadesNum.asp"
CRON_URL = f"{BASE}/CTILCQDispersionsCron.asp"
OBRES_AUT_URL = f"{BASE}/CTILCCorpus_Aut1.asp"
OBRES_AUT2_URL = f"{BASE}/CTILCCorpus_Aut2.asp"
OBRES_TITOL_URL = f"{BASE}/CTILCCorpus_Obr2.asp"
FORMES2_URL = f"{BASE}/CTILCQConc_Formes2.asp"
FORMESLEMA2_URL = f"{BASE}/CTILCQConc_FormesLema2.asp"
BASIC_FORMS_LIMIT = 200

CONTROL_TOTAL = 2136
CONTROL_DATE = "2026-11-18"
CONTROL_NOTE = (
    "Total de control observat el 18/11/2026. El corpus creix; una diferència "
    "no és un error de consulta."
)


def _date_label() -> str:
    return datetime.now(UTC).strftime("%d/%m/%Y")


def _citation(pattern: str) -> str:
    return (
        "Corpus Textual Informatitzat de la Llengua Catalana (CTILC), "
        f"Institut d'Estudis Catalans, consulta feta el {_date_label()}: {pattern}"
    )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _lema_matches(requested: str, echoed: str) -> bool:
    """Comprova que l'eco de la pàgina correspongui al lema demanat.

    El CTILC desambigua els homògrafs amb un sufix numèric (`altre_1`), que no
    forma part del lema que escriu l'usuari.
    """

    requested_norm = " ".join(requested.split()).casefold()
    echoed_norm = " ".join(echoed.split()).casefold()
    if not requested_norm or not echoed_norm:
        return False
    if echoed_norm == requested_norm:
        return True
    base, _, suffix = echoed_norm.rpartition("_")
    return bool(base) and suffix.isdigit() and base == requested_norm


MIN_YEAR = 1832
MAX_YEAR = 2022

_TIPUS_VALUES = {
    "lit": "LIT",
    "literari": "LIT",
    "nlit": "NLIT",
    "noliterari": "NLIT",
    "no literari": "NLIT",
}
_GENERE_VALUES = {
    "a": "A",
    "assaig": "A",
    "n": "N",
    "narrativa": "N",
    "p": "P",
    "poesia": "P",
    "t": "T",
    "teatre": "T",
}
_VARIETAT_VALUES = {
    "balearic": "baleàric",
    "baleàric": "baleàric",
    "central": "central",
    "nord-occidental": "nord-occidental",
    "nord occidental": "nord-occidental",
    "septentrional": "septentrional",
    "valencia": "valencià",
    "valencià": "valencià",
}


def _map_filter_values(
    values: list[str], mapping: dict[str, str], *, label: str, hint: str
) -> list[str]:
    mapped: list[str] = []
    for value in values:
        key = normalize_key(value)
        if key not in mapping:
            raise InvalidQueryError(
                f"El valor «{value}» no és vàlid per a {label}.",
                hint=hint,
            )
        if mapping[key] not in mapped:
            mapped.append(mapping[key])
    return mapped


def _resolve_filters(filters: CtilcFilters | None) -> tuple[dict[str, str], dict[str, Any] | None]:
    """Converteix els filtres públics en els camps del formulari del CTILC."""

    if filters is None:
        return {}, None

    fields: dict[str, str] = {}
    public: dict[str, Any] = {}

    if filters.autor:
        values = [clean_text(value) for value in filters.autor if clean_text(value)]
        if not values:
            raise InvalidQueryError("La llista d'autors és buida.")
        fields["autSelec"] = ", ".join(f"@{value}" for value in values)
        public["autor"] = values
    if filters.titol:
        values = [clean_text(value) for value in filters.titol if clean_text(value)]
        if not values:
            raise InvalidQueryError("La llista de títols és buida.")
        fields["titSelec"] = ", ".join(f"@{value}" for value in values)
        public["titol"] = values

    if filters.any_min is not None or filters.any_max is not None:
        low = filters.any_min if filters.any_min is not None else MIN_YEAR
        high = filters.any_max if filters.any_max is not None else MAX_YEAR
        if low < MIN_YEAR or high > MAX_YEAR or low > high:
            raise InvalidQueryError(
                f"El rang d'anys no és vàlid: {low}–{high}.",
                hint=f"El corpus va de {MIN_YEAR} a {MAX_YEAR} i el mínim no pot superar el màxim.",
            )
        fields["anySelec"] = ", ".join(f"@{year}" for year in range(low, high + 1))
        public["any_min"] = low
        public["any_max"] = high

    if filters.tipus:
        values = _map_filter_values(
            filters.tipus,
            _TIPUS_VALUES,
            label="tipus",
            hint="Valors: LIT (literari), NLIT (no literari).",
        )
        fields["tipusSelec"] = ", ".join(f"@{value}" for value in values)
        public["tipus"] = values

    if filters.genere:
        values = _map_filter_values(
            filters.genere,
            _GENERE_VALUES,
            label="gènere",
            hint="Valors: A (assaig), N (narrativa), P (poesia), T (teatre).",
        )
        fields["genSelec"] = ", ".join(f"@{value}" for value in values)
        public["genere"] = values

    if filters.varietat:
        values = _map_filter_values(
            filters.varietat,
            _VARIETAT_VALUES,
            label="varietat",
            hint=("Valors: baleàric, central, nord-occidental, septentrional, valencià."),
        )
        fields["varSelec"] = ", ".join(f"@{value}" for value in values)
        public["varietat"] = values

    if filters.traduccio is not None:
        fields["tradSelec"] = "sí" if filters.traduccio else "no"
        public["traduccio"] = filters.traduccio

    return fields, (public or None)


_BASIC_MODES = {
    "coincident": "0",
    "comenca per": "1",
    "comencada per": "1",
    "acaba en": "2",
    "acabada en": "2",
    "conte": "3",
    "en qualsevol posicio": "3",
}


def _basic_mode(mode: str) -> str:
    key = normalize_key(mode)
    if key in _BASIC_MODES:
        return _BASIC_MODES[key]
    raise InvalidQueryError(
        f"El mode «{mode}» no és vàlid per a una cerca bàsica.",
        hint=(
            "Modes: coincident, comença per, acaba en o conté. Els modes "
            "negatius (no comença per, no acaba en, que no contingui) no estan "
            "verificats i no s'exposen."
        ),
    )


def _filter_tokens(value: str) -> list[str]:
    """Separa `@A, @B` sense trencar els noms que contenen comes."""

    return sorted(
        clean_text(part).lstrip("@").strip().casefold()
        for part in re.split(r",\s*(?=@)", value)
        if part.strip()
    )


def _filters_match(sent: dict[str, str], echo: dict[str, str]) -> bool:
    if not sent:
        return True
    if not echo:
        return False
    for name, value in sent.items():
        echoed = echo.get(name, "")
        if name == "tradSelec":
            if normalize_key(echoed) != normalize_key(value):
                return False
        elif _filter_tokens(echoed) != _filter_tokens(value):
            return False
    return True


class CtilcAdapter:
    def __init__(
        self,
        client: HttpClient,
        settings: Settings,
        cursors: CursorStore,
    ) -> None:
        self.client = client
        self.settings = settings
        self.cursors = cursors

    async def search(
        self,
        *,
        elements: list[PatternElement],
        query: dict[str, Any],
        limit: int = 10,
        start: int = 1,
        cursor_token: str | None = None,
        use_cache: bool = True,
        persist_cursor: bool = True,
        filters: dict[str, str] | None = None,
        filter_query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if start < 1:
            raise InvalidQueryError("`start` ha de ser 1 o més gran.")
        offset = max(1, min(limit, self.settings.max_occurrences))
        compiled = compile_pattern(elements)
        body = compiled.body(start=start, offset=offset, filters=filters)
        result = await self.client.post_text(COOCUR_URL, body, use_cache=use_cache)
        expected_pattern = " ".join(compiled.expected.values())
        page = parse_ctilc_page(
            result.text,
            expected=compiled.expected,
            expected_pattern=expected_pattern,
        )
        if filter_query:
            query = {**query, "filters": filter_query}

        warnings = _dedupe(result.warnings + page.warnings)
        status = "ok"
        error_note = None
        filters_ok = True
        if filters and page.total_unfiltered != 0:
            if page.filtered_total is None:
                filters_ok = False
                warnings.append("filters_not_applied")
            elif not _filters_match(filters, page.filters_echo):
                filters_ok = False
                warnings.append("filters_echo_unexpected")

        if not filters_ok:
            status = "unexpected_response"
            error_note = (
                "Els filtres enviats no s'han pogut verificar a la pàgina del CTILC. "
                "El resultat no es pot presentar com un recompte filtrat ni com una absència."
            )
        elif page.total is None:
            status = "unexpected_response"
            error_note = (
                "No s'ha pogut llegir un total verificat. La pàgina no es pot "
                "interpretar com una absència lingüística."
            )
        elif not page.echo_verified:
            status = "unexpected_response"
            error_note = (
                "El patró retornat pel servidor no coincideix amb el que s'ha enviat. "
                "El resultat no es pot presentar com una absència lingüística."
            )
        elif page.total == 0:
            if page.explicit_zero and page.zero_message:
                status = "no_matches"
            else:
                status = "unexpected_response"
                error_note = (
                    "El total és zero però la pàgina no confirma explícitament cap coincidència."
                )
        elif page.total is not None and page.total > 0 and not page.occurrences:
            status = "unexpected_response"
            if filters and page.filtered_total is not None:
                warnings.append("filtered_empty_unverified")
                error_note = (
                    "Amb filtres, el portal dona un total positiu però no retorna files. "
                    "Aquest total pot ser un valor de control (1) i no un recompte fiable; "
                    "no es pot interpretar com una absència."
                )
            else:
                error_note = (
                    "El servidor dona un total positiu però la pàgina no conté files. "
                    "Pot ser un resultat remot caducat o un canvi de format."
                )

        returned = len(page.occurrences)
        # Avancem la mida de pàgina demanada, no les files parsejades: una fila
        # mal formada no ha de fer saltar la posició següent.
        next_start = start + offset
        has_more = bool(page.total and page.total > start - 1 + offset)
        search_cursor = None
        next_cursor = None

        if persist_cursor and status in {"ok", "no_matches"} and page.total is not None:
            payload = CursorPayload(
                query=query,
                elements=elements,
                pattern_echo=page.pattern_echo,
                total=page.total,
                resultat=page.server_fields.get("resultat"),
                qlocali=page.server_fields.get("Qlocali"),
                filters=filters or {},
                next_start=next_start,
                page_size=offset,
                created_at=datetime.now(UTC),
            )
            if cursor_token:
                self.cursors.update(cursor_token, payload)
                search_cursor = cursor_token
            else:
                # Un cursor estable per vincular-hi eines com la dispersió,
                # encara que tots els resultats càpiguen en una pàgina.
                search_cursor = self.cursors.create(payload)
            if has_more:
                next_cursor = search_cursor

        if status == "no_matches" and "zero_results" not in warnings:
            warnings.append("zero_results")
        if "transport_eof" in result.warnings:
            warnings.append("transport_eof")

        occurrences = [item.model_dump(exclude_none=True) for item in page.occurrences]
        response: dict[str, Any] = {
            "status": status,
            "query": {**query, "limit": offset, "start": start},
            "pattern_echo": page.pattern_echo,
            "echo_verified": page.echo_verified,
            "total": page.total,
            "returned": returned,
            "has_more": has_more,
            "search_cursor": search_cursor,
            "next_cursor": next_cursor,
            "occurrences": occurrences,
            "warnings": _dedupe(warnings),
            "source": COOCUR_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation(page.pattern_echo or "consulta sense eco"),
        }
        if error_note:
            response["error"] = {"code": status, "message": error_note}
        if page.zero_message:
            response["zero_message"] = page.zero_message
        if filters:
            response["filters_verified"] = filters_ok
            response["total_unfiltered"] = page.total_unfiltered
            response["filters_summary"] = page.filters_summary
        return response

    async def search_pattern(
        self,
        elements: list[PatternElement],
        *,
        limit: int = 10,
        filters: CtilcFilters | None = None,
    ) -> dict[str, Any]:
        filter_fields, filter_query = _resolve_filters(filters)
        return await self.search(
            elements=elements,
            query=patro_query(elements),
            limit=limit,
            start=1,
            filters=filter_fields,
            filter_query=filter_query,
        )

    async def cerca(
        self,
        *,
        lema: str | None = None,
        forma: str | None = None,
        categoria: str | None = None,
        limit: int = 10,
        filters: CtilcFilters | None = None,
    ) -> dict[str, Any]:
        """Cerca simple per lema o per forma, amb contextos."""

        lema = clean_text(lema) if lema else None
        forma = clean_text(forma) if forma else None
        categoria = clean_text(categoria) if categoria else None
        if lema and forma:
            raise InvalidQueryError(
                "Indica un lema o una forma, no tots dos alhora.",
                hint="Per a una combinació de lema i forma, fes servir `cerca_patro`.",
            )
        if not lema and not forma:
            raise InvalidQueryError(
                "Falta el lema o la forma.",
                hint="Indica `lema` (totes les formes) o `forma` (una forma concreta).",
            )
        if forma and categoria:
            raise InvalidQueryError(
                "Una forma no es pot restringir amb `categoria` en aquesta cerca.",
                hint=(
                    "La categoria és una posició adjacent, no una propietat de la forma. "
                    "Fes servir `cerca_patro` amb un element `cg` si vols aquesta combinació."
                ),
            )

        if lema:
            element = PatternElement(type="lema", value=lema, category=categoria)
            query = {"mode": "cerca", "lema": lema, "categoria": categoria}
        else:
            element = PatternElement(type="forma", value=forma)
            query = {"mode": "cerca", "forma": forma}

        filter_fields, filter_query = _resolve_filters(filters)
        return await self.search(
            elements=[element],
            query=query,
            limit=limit,
            start=1,
            filters=filter_fields,
            filter_query=filter_query,
        )

    def _basic_payload(
        self,
        *,
        kind: str,
        query: str,
        mode: str,
        cg: str,
        data: dict[str, Any],
        limit: int,
        offset: int,
        warnings: list[str],
        source: str,
    ) -> dict[str, Any]:
        total = data["total"]
        occurrences = data["occurrences"]
        forms = data["forms"]
        forms_truncated = len(forms) > BASIC_FORMS_LIMIT
        if forms_truncated:
            forms = forms[:BASIC_FORMS_LIMIT]
            warnings.append("forms_truncated")
        echo_verified = bool(data["echo"]) and normalize_key(query) in normalize_key(data["echo"])
        if data["echo"] and not echo_verified:
            warnings.append("echo_unexpected")
        if any(item["occurrence_id"] is None for item in occurrences):
            warnings.append("occurrence_id_missing")

        if total is None:
            status = "unexpected_response"
        elif total == 0:
            status = "no_matches"
            warnings.append("zero_results")
        elif not occurrences:
            status = "unexpected_response"
            warnings.append("parse_partial")
        else:
            status = "ok"

        returned = len(occurrences)
        has_more = bool(total) and returned > 0 and offset + returned < total
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        label = "la forma" if kind == "forma" else "el lema"
        payload: dict[str, Any] = {
            "status": status,
            "query": {
                kind: query,
                "mode": mode,
                "cg": cg or None,
                "limit": limit,
                "offset": offset,
            },
            "echo": data["echo"],
            "echo_verified": echo_verified,
            "total": total,
            "returned": returned,
            "has_more": has_more,
            "next_offset": offset + returned if has_more else None,
            "page": data["page"],
            "pages": data["pages"],
            "forms": forms,
            "forms_truncated": forms_truncated,
            "occurrences": occurrences,
            "warnings": _dedupe(warnings + data["warnings"]),
            "note": (
                "`total` és la freqüència total de la cerca; `occurrences` és "
                "només la pàgina demanada i `forms` resumeix les formes del "
                "resultat amb la categoria i la morfologia (consulta `etiquetes` "
                "per interpretar els codis). Per continuar, passa `offset`. "
                "Aquestes pàgines no apliquen els filtres de la consulta "
                "combinada."
            ),
            "source": source,
            "retrieved_at": retrieved_at,
            "citation": (
                f"CTILC (IEC), concordança de {label} «{query}» ({mode}), "
                f"consulta feta el {_date_label()}."
            ),
        }
        if status == "unexpected_response":
            payload["error"] = {
                "code": "unexpected_response",
                "message": "No s'ha pogut llegir la pàgina de concordança bàsica.",
                "hint": "El portal pot haver canviat; cal revisar el parser.",
            }
        return payload

    async def cerca_forma(
        self,
        forma: str,
        *,
        mode: str = "coincident",
        cg: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Concordança bàsica d'una forma, amb les formes agrupades."""

        forma = clean_text(forma)
        if not forma:
            raise InvalidQueryError(
                "Falta la forma.",
                hint="Indica una forma gràfica, sense espais (per exemple «somriu»).",
            )
        if len(forma) > 80:
            raise InvalidQueryError(
                "La forma és massa llarga.",
                hint="Consulta una forma o un truncament curt.",
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, 50))
        cg = clean_text(cg) if cg else ""
        condition = _basic_mode(mode)
        body = (
            f"cadforma={quote_plus(forma)}&cadformacond={condition}"
            f"&cg={quote_plus(cg)}&seccio=CTILC1"
            f"&iStart={offset + 1}&iOffset={limit}"
        )
        result = await self.client.post_text(FORMES2_URL, body)
        data = parse_basiques(result.text, kind="forma")
        return self._basic_payload(
            kind="forma",
            query=forma,
            mode=mode,
            cg=cg,
            data=data,
            limit=limit,
            offset=offset,
            warnings=list(result.warnings),
            source=FORMES2_URL,
        )

    async def cerca_lema(
        self,
        lema: str,
        *,
        mode: str = "coincident",
        cg: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Concordança bàsica d'un lema, amb les seves formes."""

        lema = clean_text(lema)
        if not lema:
            raise InvalidQueryError(
                "Falta el lema.",
                hint="Indica un lema (per exemple «somriure»).",
            )
        if len(lema) > 80:
            raise InvalidQueryError(
                "El lema és massa llarg.",
                hint="Consulta un lema o un truncament curt.",
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, 50))
        cg = clean_text(cg) if cg else ""
        condition = _basic_mode(mode)
        body = (
            f"cadlema={quote_plus(lema)}&cadlemacond={condition}"
            f"&cg={quote_plus(cg)}&seccio=CTILC1"
            f"&iStart={offset + 1}&iOffset={limit}"
        )
        result = await self.client.post_text(FORMESLEMA2_URL, body)
        data = parse_basiques(result.text, kind="lema")
        return self._basic_payload(
            kind="lema",
            query=lema,
            mode=mode,
            cg=cg,
            data=data,
            limit=limit,
            offset=offset,
            warnings=list(result.warnings),
            source=FORMESLEMA2_URL,
        )

    async def search_phrase(
        self,
        frase: str,
        *,
        variants: list[str] | None = None,
        limit: int = 10,
        filters: CtilcFilters | None = None,
    ) -> dict[str, Any]:
        phrases = [clean_text(frase)]
        for variant in variants or []:
            cleaned = clean_text(variant)
            if cleaned and cleaned not in phrases:
                phrases.append(cleaned)

        filter_fields, filter_query = _resolve_filters(filters)
        base_query = phrase_query(frase, variants)
        if filter_query:
            base_query = {**base_query, "filters": filter_query}

        outcomes: list[dict[str, Any]] = []
        errors = 0
        matches = 0
        zeroes = 0
        problems = 0
        for variant in phrases:
            try:
                outcome = await self.search(
                    elements=phrase_elements(variant),
                    query={**base_query, "variant": variant},
                    limit=limit,
                    start=1,
                    filters=filter_fields,
                )
            except LlenguaError as exc:
                errors += 1
                outcomes.append(
                    {
                        "variant": variant,
                        "status": exc.status,
                        "error": {"message": exc.message, "hint": exc.hint},
                        "occurrences": [],
                    }
                )
                continue
            if outcome["status"] == "ok":
                matches += 1
            elif outcome["status"] == "no_matches":
                zeroes += 1
            else:
                problems += 1
            outcomes.append(
                {
                    "variant": variant,
                    **{
                        key: outcome.get(key)
                        for key in (
                            "status",
                            "pattern_echo",
                            "echo_verified",
                            "total",
                            "returned",
                            "has_more",
                            "search_cursor",
                            "next_cursor",
                            "filters_verified",
                            "total_unfiltered",
                            "filters_summary",
                            "occurrences",
                            "warnings",
                            "zero_message",
                        )
                    },
                }
            )

        if matches and not errors and not problems:
            status = "ok"
        elif matches:
            status = "partial"
        elif errors == len(outcomes):
            status = outcomes[0]["status"] if outcomes else "unexpected_response"
        elif errors or problems:
            status = "partial"
        elif zeroes:
            status = "no_matches"
        else:
            status = "partial"

        warnings = _dedupe(
            [warning for item in outcomes for warning in item.get("warnings", []) if warning]
        )
        return {
            "status": status,
            "query": {**base_query, "limit": limit},
            "variants": outcomes,
            "variants_tested": [item["variant"] for item in outcomes],
            "not_summed_note": (
                "Els totals de cada variant es presenten per separat i no se sumen: "
                "poden solapar-se."
            ),
            "total": None,
            "warnings": warnings,
            "source": COOCUR_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation(frase),
        }

    async def continue_search(self, cursor: str, *, limit: int | None = None) -> dict[str, Any]:
        if limit is not None and limit < 1:
            raise InvalidQueryError("`limit` ha de ser 1 o més gran.")
        payload = self.cursors.get(cursor)
        if payload is None:
            raise StaleSearchError(
                "El cursor no existeix o ha caducat.",
                hint=(
                    "Torna a executar la cerca original. El cursor és local i té "
                    "una validesa limitada."
                ),
                source=COOCUR_URL,
            )
        if payload.total and payload.next_start > payload.total:
            return {
                "status": "ok",
                "query": payload.query,
                "total": payload.total,
                "returned": 0,
                "has_more": False,
                "search_cursor": cursor,
                "next_cursor": None,
                "occurrences": [],
                "warnings": [],
                "note": "No hi ha més files: la posició ja supera el total.",
                "source": COOCUR_URL,
                "retrieved_at": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "citation": _citation(payload.pattern_echo),
            }

        result = await self.search(
            elements=payload.elements,
            query=payload.query,
            limit=limit or payload.page_size,
            start=payload.next_start,
            cursor_token=cursor,
            filters=payload.filters or None,
        )
        if (
            result["status"] == "unexpected_response"
            and not payload.filters
            and result.get("total")
            and result.get("returned") == 0
            and result["total"] >= payload.next_start
        ):
            result["status"] = "stale_search"
            result.setdefault("warnings", []).append("result_cache_miss")
            result["error"] = {
                "code": "result_cache_miss",
                "message": (
                    "La pàgina continua dient que hi ha resultats, però no retorna files. "
                    "El resultat remot pot haver caducat."
                ),
                "hint": "Torna a executar la cerca original per obtenir un resultat nou.",
            }
        stale_reason = None
        total_changed = payload.total and result.get("total") not in (None, payload.total)
        pattern_changed = (
            payload.pattern_echo
            and result.get("pattern_echo")
            and not patterns_equivalent(result["pattern_echo"], payload.pattern_echo)
        )
        if total_changed or pattern_changed:
            stale_reason = "corpus_updated" if total_changed else "pattern_echo_unexpected"
        elif (
            payload.pattern_echo
            and result.get("pattern_echo")
            and not patterns_equivalent(result["pattern_echo"], payload.pattern_echo)
        ):
            stale_reason = "pattern_echo_unexpected"
        if stale_reason:
            # No barregem files d'una cerca que ja no podem confirmar amb les
            # de la cerca original.
            self.cursors.update(cursor, payload)
            return {
                "status": "stale_search",
                "query": payload.query,
                "total": None,
                "previous_total": payload.total,
                "returned": 0,
                "has_more": False,
                "next_cursor": None,
                "occurrences": [],
                "warnings": [stale_reason],
                "error": {
                    "code": "stale_search",
                    "message": (
                        "La continuació no correspon a la cerca original: el total "
                        "o el patró han canviat."
                    ),
                    "hint": "Torna a executar la cerca original per obtenir un resultat nou.",
                },
                "source": COOCUR_URL,
                "retrieved_at": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "citation": _citation(payload.pattern_echo),
            }
        return result

    async def dispersio_cronologica(self, cursor: str) -> dict[str, Any]:
        """Dispersió cronològica d'una cerca, vinculada pel seu cursor.

        Accepta el `search_cursor` de qualsevol cerca vàlida, tingui o no
        pàgines següents. Es validen tres coses abans de presentar les dades:
        que el patró de la pàgina sigui el de la cerca, que el total coincideixi
        amb el de la cerca i que la suma dels trams sigui el total. Si no
        quadren, les dades queden a `unvalidated` i `periods` buit.
        """

        payload = self.cursors.get(cursor)
        if payload is None:
            raise StaleSearchError(
                "El cursor no existeix o ha caducat.",
                hint="Torna a executar la cerca original i demana la dispersió.",
                source=CRON_URL,
            )

        params = {
            "tipusorig": "Coocurrències",
            "cadlema": payload.pattern_echo,
            "cadlemacondtxt": payload.pattern_echo,
            "resultat": payload.resultat or "",
            "Qlocali": payload.qlocali or str(payload.total),
            "seccio": "CTILC1",
        }
        result = await self.client.get_text(CRON_URL, params=params, use_cache=False)
        data = parse_cronologia(result.text)

        warnings: list[str] = list(result.warnings)
        if not payload.resultat:
            warnings.append("no_remote_result")
        if payload.filters:
            warnings.append("filters_not_applied")
        if (
            payload.pattern_echo
            and data["pattern_echo"]
            and not patterns_equivalent(data["pattern_echo"], payload.pattern_echo)
        ):
            warnings.append("pattern_echo_unexpected")
        if data["search_total"] is not None and data["search_total"] != payload.total:
            warnings.append("corpus_updated")
        if not data["totals_match_search"]:
            warnings.append("totals_mismatch")

        invalid_reasons = [
            reason
            for reason in ("pattern_echo_unexpected", "corpus_updated", "totals_mismatch")
            if reason in warnings
        ]
        data_valid = not invalid_reasons

        if "pattern_echo_unexpected" in warnings:
            status = "unexpected_response"
        elif invalid_reasons or "filters_not_applied" in warnings:
            status = "partial"
        else:
            status = "ok"

        response: dict[str, Any] = {
            "status": status,
            "query": payload.query,
            "pattern_echo": data["pattern_echo"] or payload.pattern_echo,
            "search_total": payload.total,
            "data_valid": data_valid,
            "periods": data["periods"] if data_valid else [],
            "totals": data["totals"] if data_valid else None,
            "totals_match_search": data["totals_match_search"],
            "peak_absolute": data["peak_absolute"] if data_valid else None,
            "peak_relative": data["peak_relative"] if data_valid else None,
            "unvalidated": None,
            "warnings": _dedupe(warnings),
            "note": (
                "La taxa és ocurrències per milió de paraules del tram, derivada "
                "dels enters del gràfic. La unitat del denominador són paraules "
                "del corpus. Si hi ha pocs testimonis, parlem de concentració "
                "observada, no de tendència general. Si `data_valid` és fals, "
                "`periods` queda buit i les dades sense validar són a "
                "`unvalidated`: no s'han de presentar com a resultats. Si la "
                "cerca tenia filtres, la dispersió no els aplica "
                "(`filters_not_applied`)."
            ),
            "source": CRON_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation(payload.pattern_echo),
        }
        if not data_valid:
            response["unvalidated"] = {
                "periods": data["periods"],
                "totals": data["totals"],
                "peak_absolute": data["peak_absolute"],
                "peak_relative": data["peak_relative"],
            }
            response["error"] = {
                "code": invalid_reasons[0],
                "message": (
                    "Les dades de la dispersió no s'han pogut validar contra la "
                    "cerca original: el patró o els totals no coincideixen."
                ),
                "hint": (
                    "No presentis la distribució com a vàlida. Torna a executar "
                    "la cerca i demana la dispersió amb el `search_cursor` nou."
                ),
            }
        return response

    async def dispersio_dialectal(self, cursor: str) -> dict[str, Any]:
        """Distribució dialectal d'una cerca, vinculada pel seu cursor.

        La varietat és la de l'obra, no la del parlant. La taxa per milió
        normalitza les diferències de mida dels sis subcorpus; comparar només
        els recomptes absoluts afavoreix el català central.
        """

        payload = self.cursors.get(cursor)
        if payload is None:
            raise StaleSearchError(
                "El cursor no existeix o ha caducat.",
                hint="Torna a executar la cerca original i demana la dispersió.",
                source=DIAL_URL,
            )

        params = {
            "tipusorig": "Coocurrències",
            "cadlema": payload.pattern_echo,
            "cadlemacondtxt": payload.pattern_echo,
            "resultat": payload.resultat or "",
            "Qlocali": payload.qlocali or str(payload.total),
            "seccio": "CTILC1",
        }
        result = await self.client.get_text(DIAL_URL, params=params, use_cache=False)
        data = parse_dialectal(result.text)

        warnings: list[str] = list(result.warnings)
        if not payload.resultat:
            warnings.append("no_remote_result")
        if payload.filters:
            warnings.append("filters_not_applied")
        if (
            payload.pattern_echo
            and data["pattern_echo"]
            and not patterns_equivalent(data["pattern_echo"], payload.pattern_echo)
        ):
            warnings.append("pattern_echo_unexpected")
        if data["search_total"] is not None and data["search_total"] != payload.total:
            warnings.append("corpus_updated")
        if not data["totals_match_search"]:
            warnings.append("totals_mismatch")

        invalid_reasons = [
            reason
            for reason in ("pattern_echo_unexpected", "corpus_updated", "totals_mismatch")
            if reason in warnings
        ]
        data_valid = not invalid_reasons

        if "pattern_echo_unexpected" in warnings:
            status = "unexpected_response"
        elif invalid_reasons or "filters_not_applied" in warnings:
            status = "partial"
        else:
            status = "ok"

        response: dict[str, Any] = {
            "status": status,
            "query": payload.query,
            "pattern_echo": data["pattern_echo"] or payload.pattern_echo,
            "search_total": payload.total,
            "data_valid": data_valid,
            "varieties": data["varieties"] if data_valid else [],
            "totals": data["totals"] if data_valid else None,
            "index": data["index"] if data_valid else None,
            "totals_match_search": data["totals_match_search"],
            "peak_absolute": data["peak_absolute"] if data_valid else None,
            "peak_relative": data["peak_relative"] if data_valid else None,
            "unvalidated": None,
            "warnings": _dedupe(warnings),
            "note": (
                "La varietat és la de l'obra, no la del parlant: el CTILC és un "
                "corpus escrit. `share_of_query` és el percentatge de les "
                "ocurrències de la cerca en cada varietat; `share_of_corpus` és "
                "el pes de cada varietat dins del corpus; `per_million` és la "
                "taxa per milió de paraules d'aquella varietat, derivada dels "
                "enters del gràfic. Per comparar varietats de mides diferents, "
                "fes servir `per_million`, no els recomptes absoluts. `index` és "
                "l'índex de dispersió que calcula el portal. Un zero pot ser una "
                "mancança del corpus. Si `data_valid` és fals, `varieties` queda "
                "buit i les dades són a `unvalidated`."
            ),
            "source": DIAL_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation(payload.pattern_echo),
        }
        if not data_valid:
            response["unvalidated"] = {
                "varieties": data["varieties"],
                "totals": data["totals"],
                "index": data["index"],
                "peak_absolute": data["peak_absolute"],
                "peak_relative": data["peak_relative"],
            }
            response["error"] = {
                "code": invalid_reasons[0],
                "message": (
                    "Les dades de la dispersió dialectal no s'han pogut validar "
                    "contra la cerca original: el patró o els totals no coincideixen."
                ),
                "hint": (
                    "No presentis la distribució com a vàlida. Torna a executar "
                    "la cerca i demana la dispersió amb el `search_cursor` nou."
                ),
            }
        return response

    async def collocacions(
        self,
        lema: str,
        *,
        radi: int = 3,
        freq_min: int = 5,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Col·locacions d'un lema, agrupades per categoria gramatical.

        Les xifres són freqüències de coaparició dins d'una finestra de ±`radi`
        mots (0-5), no d'adjacència: no es barregen amb els recomptes de
        `cerca_frase` ni de `cerca_patro`.
        """

        term = clean_text(lema)
        if not term:
            raise InvalidQueryError(
                "Falta el lema.",
                hint="Escriu el lema de què vols les col·locacions.",
            )
        if len(term) > 60 or re.search(r"\s", term):
            raise InvalidQueryError(
                f"«{term}» no és un lema vàlid.",
                hint="Indica un sol lema, sense espais.",
            )
        radi = max(0, min(radi, 5))
        freq_min = max(1, min(freq_min, 100))
        limit = max(1, min(limit, 10))

        body = (
            f"seccio=CTILC1&cadlema={quote(term, safe='')}"
            f"&cadlemacond=0&freqMin={freq_min}&radiE={radi}&radiD={radi}"
        )
        try:
            result = await self.client.post_text(COLLOCACIONS_URL, body)
        except UpstreamError as exc:
            if "supera el límit de mida" not in exc.message:
                raise
            raise UpstreamError(
                f"La pàgina de col·locacions de «{term}» és massa gran per descarregar-la.",
                hint=(
                    f"El lema «{term}» és molt freqüent. Apuja `freq_min` "
                    f"(ara {freq_min}) o consulta'n un de més específic."
                ),
                source=COLLOCACIONS_URL,
            ) from exc
        data = parse_collocacions(result.text)

        warnings = list(result.warnings)
        lema_echo = data["lema_echo"]
        echo_verified = _lema_matches(term, lema_echo)
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        citation = f"CTILC (IEC), col·locacions del lema {term}, consulta feta el {_date_label()}."
        note = (
            "Les xifres són freqüències de coaparició dins d'una finestra de "
            f"±{radi} mots, amb un mínim de {freq_min} coaparicions. No són "
            "recomptes d'adjacència ni de patró: no es poden comparar directament "
            "amb els totals de `cerca_frase` o `cerca_patro`."
        )
        common = {
            "query": {"lema": term, "radi": radi, "freq_min": freq_min},
            "lema": term,
            "lema_echo": lema_echo,
            "total": data["total"],
            "counted_rows": data["counted_rows"],
            "excluded_rows": data["excluded_rows"],
        }

        if not echo_verified:
            return {
                "status": "unexpected_response",
                **common,
                "lema_echo_verified": False,
                "returned_categories": 0,
                "returned_items": 0,
                "categories": [],
                "altres": {"rows": 0, "items": []},
                "warnings": _dedupe(warnings + ["lema_echo_unexpected"]),
                "error": {
                    "code": "lema_echo_unexpected",
                    "message": (
                        f"El servidor ha retornat col·locacions de «{lema_echo}» "
                        f"en lloc de «{term}»."
                    ),
                    "hint": (
                        "No es poden presentar aquestes dades com a col·locacions "
                        "del lema demanat. Torna a provar la consulta."
                    ),
                },
                "note": note,
                "source": COLLOCACIONS_URL,
                "retrieved_at": retrieved_at,
                "citation": citation,
            }

        categories = [
            {**category, "items": category["items"][:limit]} for category in data["categories"]
        ]
        altres_items = data["altres"]["items"][:limit]
        truncated = any(category["rows"] > len(category["items"]) for category in categories) or (
            data["altres"]["rows"] > len(altres_items)
        )
        if data["excluded_rows"]:
            warnings.append("partial_rows")
        if truncated:
            warnings.append("collocations_truncated")
        returned_items = sum(len(category["items"]) for category in categories) + len(altres_items)
        rows_note = (
            "`total` és el recompte del servidor i inclou les files de puntuació "
            f"descartades ({data['excluded_rows']}); per això s'afegeix l'avís "
            "`partial_rows` quan n'hi ha. `counted_rows` en són les files "
            "aprofitables; `rows` de cada categoria és el nombre disponible abans "
            "de retallar-lo a `limit`."
        )
        return {
            "status": "ok",
            **common,
            "lema_echo_verified": True,
            "returned_categories": len(categories),
            "returned_items": returned_items,
            "categories": categories,
            "altres": {"rows": data["altres"]["rows"], "items": altres_items},
            "warnings": _dedupe(warnings),
            "note": f"{note} {rows_note}",
            "source": COLLOCACIONS_URL,
            "retrieved_at": retrieved_at,
            "citation": citation,
        }

    async def filtres_disponibles(
        self,
        cursor: str,
        *,
        tipus: str = "autors",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Valors disponibles d'un filtre per a una cerca concreta."""

        if tipus not in KINDS:
            raise InvalidQueryError(
                f"El tipus de filtre «{tipus}» no existeix.",
                hint="Tipus disponibles: " + ", ".join(sorted(KINDS)) + ".",
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, 100))

        payload = self.cursors.get(cursor)
        if payload is None:
            raise StaleSearchError(
                "El cursor no existeix o ha caducat.",
                hint="Torna a executar la cerca i demana'n els filtres.",
                source=FILTRES_URL,
            )
        if not payload.resultat:
            raise StaleSearchError(
                "Aquesta cerca no té un resultat remot per consultar-ne els filtres.",
                hint="Torna a executar la cerca; el cursor pot haver quedat desfassat.",
                source=FILTRES_URL,
            )

        body = (
            f"filt={KINDS[tipus]}&seccio=CTILC1&resultat={payload.resultat}&{EXTRA_PARAMS[tipus]}"
        )
        result = await self.client.post_text(FILTRES_URL, body, cache_ttl=300)
        values = parse_filter_values(result.text, tipus=tipus)
        total = len(values)
        page = values[offset : offset + limit]
        has_more = offset + len(page) < total
        return {
            "status": "ok",
            "query": {"tipus": tipus, "limit": limit, "offset": offset},
            "result_total": payload.total,
            "total": total,
            "returned": len(page),
            "has_more": has_more,
            "next_offset": offset + len(page) if has_more else None,
            "values": page,
            "warnings": list(result.warnings),
            "note": (
                "Els recomptes són de la cerca original i indiquen quantes "
                "ocurrències té cada valor. Passa `value` a `filtres`; `label` "
                "és el nom llegible."
            ),
            "source": FILTRES_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": (
                f"CTILC (IEC), filtres de {tipus} per a una consulta feta el {_date_label()}."
            ),
        }

    def _obres_payload(
        self,
        *,
        status: str,
        query: dict[str, Any],
        total: int | None,
        works: list[dict[str, Any]],
        offset: int,
        limit: int,
        note: str,
        source: str,
        retrieved_at: str,
        authors: list[dict[str, str]] | None = None,
        echo_verified: bool = True,
        warnings: list[str] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        page = works[offset : offset + limit]
        has_more = bool(works) and total is not None and offset + len(page) < total
        parts = []
        if query.get("autor"):
            parts.append(f"autor «{query['autor']}»")
        if query.get("titol"):
            parts.append(f"títol «{query['titol']}»")
        if query.get("autor_id"):
            parts.append(f"autor_id {query['autor_id']}")
        detail = ", ".join(parts) or "consulta"
        payload: dict[str, Any] = {
            "status": status,
            "query": query,
            "total": total,
            "returned": len(page),
            "has_more": has_more,
            "next_offset": offset + len(page) if has_more else None,
            "works": page,
            "echo_verified": echo_verified,
            "warnings": _dedupe(warnings or []),
            "note": note,
            "source": source,
            "retrieved_at": retrieved_at,
            "citation": (f"CTILC (IEC), obres ({detail}), consulta feta el {_date_label()}."),
        }
        if authors:
            payload["authors"] = authors
        if error:
            payload["error"] = error
        return payload

    async def obres(
        self,
        *,
        autor: str | None = None,
        titol: str | None = None,
        autor_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Metadades de les obres del corpus, per autor o per títol."""

        autor = clean_text(autor) if autor else ""
        titol = clean_text(titol) if titol else ""
        autor_id = clean_text(autor_id) if autor_id else ""
        if not autor and not titol and not autor_id:
            raise InvalidQueryError(
                "Cal un autor, un títol o un `autor_id`.",
                hint=(
                    "Indica `autor` (cognom), `titol` (fragment) o l'`autor_id` "
                    "retornat quan hi ha més d'un autor."
                ),
                source=OBRES_AUT_URL,
            )
        if autor and titol:
            raise InvalidQueryError(
                "La consulta per autor i la consulta per títol són cerques diferents.",
                hint="Fes una sola cerca: `autor` o `titol`.",
                source=OBRES_AUT_URL,
            )
        if offset < 0:
            raise InvalidQueryError("`offset` ha de ser 0 o més gran.")
        limit = max(1, min(limit, 100))

        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        query = {
            "autor": autor or None,
            "titol": titol or None,
            "autor_id": autor_id or None,
        }
        warnings: list[str] = []
        authors: list[dict[str, str]] = []
        echo_verified = True
        selected_name: str | None = None

        def too_many(source_url: str) -> dict[str, Any]:
            return self._obres_payload(
                status="too_many_results",
                query=query,
                total=None,
                works=[],
                offset=offset,
                limit=limit,
                echo_verified=echo_verified,
                warnings=warnings + ["response_too_large"],
                note=(
                    "La llista d'obres és massa gran per tornar-la sencera. "
                    "Indica un títol més específic o consulta per autor."
                ),
                source=source_url,
                retrieved_at=retrieved_at,
                error={
                    "code": "too_many_results",
                    "message": "La resposta del CTILC supera el límit de mida.",
                    "hint": "Concreta més el títol o consulta per autor.",
                },
            )

        if autor and not autor_id:
            body = f"autor={quote_plus(autor)}"
            result = await self.client.post_text(OBRES_AUT_URL, body, cache_ttl=86400)
            parsed = parse_authors(result.text)
            warnings.extend(result.warnings + parsed["warnings"])
            authors = parsed["authors"]
            echo_verified = normalize_key(parsed["echo"]) == normalize_key(autor)
            if not echo_verified:
                warnings.append("echo_unexpected")
            if not authors:
                if parsed["explicit_zero"]:
                    return self._obres_payload(
                        status="no_matches",
                        query=query,
                        total=0,
                        works=[],
                        offset=offset,
                        limit=limit,
                        echo_verified=echo_verified,
                        warnings=warnings + ["zero_results"],
                        note=(
                            "No hi ha cap autor que comenci pel text indicat. "
                            "Prova un cognom més curt o una altra grafia."
                        ),
                        source=OBRES_AUT_URL,
                        retrieved_at=retrieved_at,
                    )
                return self._obres_payload(
                    status="unexpected_response",
                    query=query,
                    total=None,
                    works=[],
                    offset=offset,
                    limit=limit,
                    echo_verified=echo_verified,
                    warnings=warnings,
                    note="La pàgina d'autors no té el format esperat.",
                    source=OBRES_AUT_URL,
                    retrieved_at=retrieved_at,
                    error={
                        "code": "unexpected_response",
                        "message": "No s'ha pogut llegir la llista d'autors.",
                        "hint": "El portal pot haver canviat; cal revisar el parser.",
                    },
                )
            if len(authors) > 1:
                exact = [
                    item for item in authors if normalize_key(item["name"]) == normalize_key(autor)
                ]
                if len(exact) != 1:
                    return self._obres_payload(
                        status="ambiguous_author",
                        query=query,
                        total=None,
                        works=[],
                        offset=0,
                        limit=limit,
                        authors=authors,
                        echo_verified=echo_verified,
                        warnings=warnings + ["author_candidates"],
                        note=(
                            "Hi ha més d'un autor que coincideix. Torna a cridar "
                            "`obres` amb `autor_id` (o escriu el nom complet)."
                        ),
                        source=OBRES_AUT_URL,
                        retrieved_at=retrieved_at,
                    )
                selected_name = exact[0]["name"]
                autor_id = exact[0]["id"]
            else:
                selected_name = authors[0]["name"]
                autor_id = authors[0]["id"]

        if autor_id:
            try:
                result = await self.client.post_text(
                    OBRES_AUT2_URL, f"autorL={quote_plus(autor_id)}"
                )
            except UpstreamError as exc:
                if "supera el límit" in exc.message:
                    return too_many(OBRES_AUT2_URL)
                raise
            parsed = parse_works(result.text)
            warnings.extend(result.warnings + parsed["warnings"])
            if selected_name and parsed["works"]:
                needle = normalize_key(selected_name)
                names = [normalize_key(work.get("author") or "") for work in parsed["works"]]
                if not any(needle in name or name in needle for name in names):
                    warnings.append("author_echo_unexpected")
            source = OBRES_AUT2_URL
        else:
            try:
                result = await self.client.post_text(OBRES_TITOL_URL, f"obra={quote_plus(titol)}")
            except UpstreamError as exc:
                if "supera el límit" in exc.message:
                    return too_many(OBRES_TITOL_URL)
                raise
            parsed = parse_works(result.text)
            warnings.extend(result.warnings + parsed["warnings"])
            echo_verified = normalize_key(parsed["echo"]) == normalize_key(titol)
            if not echo_verified:
                warnings.append("echo_unexpected")
            source = OBRES_TITOL_URL

        total = parsed["total"]
        if total is None:
            return self._obres_payload(
                status="unexpected_response",
                query=query,
                total=None,
                works=[],
                offset=offset,
                limit=limit,
                echo_verified=echo_verified,
                warnings=warnings,
                note="La pàgina d'obres no té el format esperat.",
                source=source,
                retrieved_at=retrieved_at,
                error={
                    "code": "unexpected_response",
                    "message": "No s'ha pogut llegir la llista d'obres.",
                    "hint": "El portal pot haver canviat; cal revisar el parser.",
                },
            )

        status = "ok" if total > 0 else "no_matches"
        if status == "no_matches":
            warnings.append("zero_results")
        return self._obres_payload(
            status=status,
            query=query,
            total=total,
            works=parsed["works"],
            offset=offset,
            limit=limit,
            echo_verified=echo_verified,
            warnings=warnings,
            note=(
                "Metadades de les obres del corpus. `translation` indica una obra "
                "traduïda; `classification` és la classificació temàtica de les "
                "obres no literàries. Els resultats es paginen amb `offset`."
            ),
            source=source,
            retrieved_at=retrieved_at,
        )

    async def context(self, occurrence_id: str, *, obra: str | None = None) -> dict[str, Any]:
        if not occurrence_id.isdigit():
            raise InvalidQueryError(
                "L'identificador d'ocurrència ha de ser numèric.",
                hint="Fes servir l'`occurrence_id` retornat per una cerca.",
            )
        common = f"id={occurrence_id}&seccio=CTILC1"
        if obra:
            if not obra.strip().isdigit():
                raise InvalidQueryError(
                    "El paràmetre `obra` ha de ser numèric.",
                    hint="Agafa'l de l'`obra_param` de la mateixa ocurrència.",
                )
            common += f"&obra={obra.strip()}"

        context_result = await self.client.post_text(
            FITXA_URL,
            f"{common}&context=50&tok=no",
        )
        context_data = parse_fitxa(context_result.text)

        paragraph = None
        paragraph_warnings: list[str] = []
        try:
            paragraph_result = await self.client.get_text(
                FITXA_URL,
                params={
                    "id": occurrence_id,
                    "tok": "no",
                    "seccio": "CTILC1",
                    **({"obra": obra.strip()} if obra else {}),
                },
            )
            paragraph_data = parse_fitxa(paragraph_result.text)
            paragraph = paragraph_data["context"]
            paragraph_warnings = paragraph_result.warnings + paragraph_data["warnings"]
        except LlenguaError:
            paragraph_warnings = ["parse_partial"]

        warnings = _dedupe(context_result.warnings + paragraph_warnings + context_data["warnings"])
        status = "ok" if context_data["work"]["id"] else "partial"
        return {
            "status": status,
            "occurrence_id": occurrence_id,
            "obra_param": obra,
            "work": context_data["work"],
            "stats": context_data["stats"],
            "occurrence": context_data["occurrence"],
            "context_50": context_data["context"],
            "left": context_data["left"],
            "nucleus": context_data["nucleus"],
            "right": context_data["right"],
            "paragraph": paragraph,
            "id_obra_note": (
                "`obra_param` és el paràmetre de la URL; l'ID bibliogràfic canònic "
                "és `work.id`, llegit de la fitxa."
            ),
            "warnings": warnings,
            "source": FITXA_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": (
                "Fitxa de localització del CTILC (IEC), consulta feta el "
                f"{_date_label()} per a l'ocurrència {occurrence_id}."
            ),
        }

    async def xifres(self) -> dict[str, Any]:
        result = await self.client.get_text(DADES_URL)
        data = parse_dades(result.text)
        return {
            "status": "ok",
            "corpus": {
                "total_words": data["total_words"],
                "analyzed": data["analyzed"],
                "proper_nouns": data["proper_nouns"],
                "unanalyzable": data["unanalyzable"],
                "others": data["others"],
            },
            "periods": data["periods"],
            "notes": [
                "El total inclou paraules analitzades, noms propis, no analitzables i altres.",
                "Un zero en una cerca per lema o categoria pot reflectir una manca d'anotació.",
                "El corpus és escrit i no representa la llengua oral ni l'ús quotidià.",
            ],
            "warnings": result.warnings,
            "source": DADES_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": (
                "CTILC (IEC), «El corpus en xifres», consulta feta el " + _date_label() + "."
            ),
        }

    async def salut(self) -> dict[str, Any]:
        """Diagnòstic del CTILC sense efectes sobre els cursors de l'usuari."""

        elements = [
            PatternElement(type="lema", value="somriure"),
            PatternElement(type="cg", category="adj", morphology="-"),
        ]
        result = await self.search(
            elements=elements,
            query=patro_query(elements),
            limit=1,
            start=1,
            use_cache=False,
            persist_cursor=False,
        )
        warnings = list(result.get("warnings", []))
        if result.get("total") != CONTROL_TOTAL:
            warnings.append("corpus_updated")
        return {
            "status": "ok"
            if result.get("status") in {"ok", "no_matches"}
            else result.get("status"),
            "control_query": "00*lema=somriure&01*cg=adj:-",
            "control_total_2026_11_18": CONTROL_TOTAL,
            "observed_total": result.get("total"),
            "pattern_echo": result.get("pattern_echo"),
            "echo_verified": result.get("echo_verified"),
            "warnings": _dedupe(warnings),
            "note": CONTROL_NOTE,
            "source": COOCUR_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation("consulta de control"),
        }

    def etiquetes(self) -> dict[str, Any]:
        return {
            "status": "ok",
            **tagset_payload(),
        }


__all__ = ["CtilcAdapter"]
