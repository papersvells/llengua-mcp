"""Adaptador del CTILC (IEC)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
)
from llengua_mcp.http import HttpClient
from llengua_mcp.models import CursorPayload, PatternElement
from llengua_mcp.parsers.ctilc import parse_ctilc_page, patterns_equivalent
from llengua_mcp.parsers.dades import parse_dades
from llengua_mcp.parsers.dispersions import parse_cronologia
from llengua_mcp.parsers.fitxa import parse_fitxa
from llengua_mcp.tagset import tagset_payload
from llengua_mcp.text import clean_text

BASE = "https://ctilc.iec.cat/scripts"
COOCUR_URL = f"{BASE}/CTILCQConc_Coocur2.asp"
FITXA_URL = f"{BASE}/CTILCQFitxaLocalitzacio.asp"
DADES_URL = f"{BASE}/CTILCQDadesNum.asp"
CRON_URL = f"{BASE}/CTILCQDispersionsCron.asp"

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
    ) -> dict[str, Any]:
        if start < 1:
            raise InvalidQueryError("`start` ha de ser 1 o més gran.")
        offset = max(1, min(limit, self.settings.max_occurrences))
        compiled = compile_pattern(elements)
        body = compiled.body(start=start, offset=offset)
        result = await self.client.post_text(COOCUR_URL, body, use_cache=use_cache)
        expected_pattern = " ".join(compiled.expected.values())
        page = parse_ctilc_page(
            result.text,
            expected=compiled.expected,
            expected_pattern=expected_pattern,
        )

        warnings = _dedupe(result.warnings + page.warnings)
        status = "ok"
        error_note = None

        if page.total is None:
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
            error_note = (
                "El servidor dona un total positiu però la pàgina no conté files. "
                "Pot ser un resultat remot caducat o un canvi de format."
            )

        returned = len(page.occurrences)
        # Avancem la mida de pàgina demanada, no les files parsejades: una fila
        # mal formada no ha de fer saltar la posició següent.
        next_start = start + offset
        has_more = bool(page.total and page.total > start - 1 + offset)
        next_cursor = None

        if status in {"ok", "no_matches"} and page.total is not None:
            payload = CursorPayload(
                query=query,
                elements=elements,
                pattern_echo=page.pattern_echo,
                total=page.total,
                resultat=page.server_fields.get("resultat"),
                qlocali=page.server_fields.get("Qlocali"),
                next_start=next_start,
                page_size=offset,
                created_at=datetime.now(UTC),
            )
            if cursor_token:
                self.cursors.update(cursor_token, payload)
            if has_more:
                next_cursor = cursor_token or self.cursors.create(payload)

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
        return response

    async def search_pattern(
        self, elements: list[PatternElement], *, limit: int = 10
    ) -> dict[str, Any]:
        return await self.search(
            elements=elements,
            query=patro_query(elements),
            limit=limit,
            start=1,
        )

    async def cerca(
        self,
        *,
        lema: str | None = None,
        forma: str | None = None,
        categoria: str | None = None,
        limit: int = 10,
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

        return await self.search(
            elements=[element],
            query=query,
            limit=limit,
            start=1,
        )

    async def search_phrase(
        self,
        frase: str,
        *,
        variants: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        phrases = [clean_text(frase)]
        for variant in variants or []:
            cleaned = clean_text(variant)
            if cleaned and cleaned not in phrases:
                phrases.append(cleaned)

        outcomes: list[dict[str, Any]] = []
        errors = 0
        matches = 0
        zeroes = 0
        problems = 0
        for variant in phrases:
            try:
                outcome = await self.search(
                    elements=phrase_elements(variant),
                    query={**phrase_query(frase), "variant": variant},
                    limit=limit,
                    start=1,
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
                            "next_cursor",
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
            "query": {**phrase_query(frase, variants), "limit": limit},
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
        )
        if (
            result["status"] == "unexpected_response"
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

        Només es pot demanar sobre una cerca concreta: el gràfic s'ha de poder
        vincular a aquella consulta. Es validen tres coses abans de presentar
        les dades: que el patró de la pàgina sigui el de la cerca, que el total
        coincideixi amb el de la cerca i que la suma dels trams sigui el total.
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

        status = "ok"
        if "pattern_echo_unexpected" in warnings:
            status = "unexpected_response"
        elif "totals_mismatch" in warnings or "corpus_updated" in warnings:
            status = "partial"

        periods = data["periods"]
        return {
            "status": status,
            "query": payload.query,
            "pattern_echo": data["pattern_echo"] or payload.pattern_echo,
            "search_total": payload.total,
            "periods": periods,
            "totals": data["totals"],
            "totals_match_search": data["totals_match_search"],
            "peak_absolute": data["peak_absolute"],
            "peak_relative": data["peak_relative"],
            "warnings": _dedupe(warnings),
            "note": (
                "La taxa és ocurrències per milió de paraules del tram, derivada "
                "dels enters del gràfic. La unitat del denominador són paraules "
                "del corpus. Si hi ha pocs testimonis, parlem de concentració "
                "observada, no de tendència general."
            ),
            "source": CRON_URL,
            "retrieved_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "citation": _citation(payload.pattern_echo),
        }

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
        )
        # `salut` és un diagnòstic: no deixem cap cursor de continuació.
        for token, entry in list(self.cursors._entries.items()):
            if entry.payload.query == patro_query(elements):
                self.cursors._entries.pop(token, None)
        result["next_cursor"] = None
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
