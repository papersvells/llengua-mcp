"""Adaptador per consultar el conjugador públic de Softcatalà."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from llengua_mcp.errors import InvalidQueryError, UpstreamError
from llengua_mcp.http import HttpClient
from llengua_mcp.parsers.conjugador import parse_conjugation
from llengua_mcp.text import clean_text, normalize_key

BASE_URL = "https://www.softcatala.org"
_PERSON_ALIASES = {
    "jo": "singular1",
    "1sg": "singular1",
    "tu": "singular2",
    "2sg": "singular2",
    "ell": "singular3",
    "ella": "singular3",
    "voste": "singular3",
    "3sg": "singular3",
    "nosaltres": "plural1",
    "1pl": "plural1",
    "vosaltres": "plural2",
    "vos": "plural2",
    "2pl": "plural2",
    "ells": "plural3",
    "elles": "plural3",
    "vostes": "plural3",
    "3pl": "plural3",
}
_MODES = {
    "indicatiu": "Indicatiu",
    "subjuntiu": "Subjuntiu",
    "imperatiu": "Imperatiu",
    "formes no personals": "Formes no personals",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(verb: str) -> str:
    # The source routes pronominal verbs by their base infinitive
    # (e.g. «abstenir-se» is /verb/abstenir/).
    for ending in ("-se'n", "-se’n", "-se"):
        if verb.casefold().endswith(ending):
            verb = verb[: -len(ending)]
            break
    return quote(verb, safe="-")


def _same_lemma(expected: str, found: str) -> bool:
    def base(value: str) -> str:
        key = normalize_key(value)
        for ending in ("-se'n", "-se’n", "-se", "-s"):
            if key.endswith(ending):
                return key[: -len(ending)].strip()
        return key

    return base(expected) == base(found)


class ConjugadorAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def consulta(
        self,
        verb: str,
        *,
        mode: str | None = None,
        temps: str | None = None,
        persona: str | None = None,
    ) -> dict[str, Any]:
        verb = clean_text(verb)
        if not verb:
            raise InvalidQueryError(
                "El verb és buit.", hint="Escriu l’infinitiu que vols consultar."
            )
        if len(verb) > 80:
            raise InvalidQueryError("El verb és massa llarg.", hint="Consulta un infinitiu.")

        selected_mode: str | None = None
        if mode:
            selected_mode = _MODES.get(normalize_key(mode))
            if selected_mode is None:
                raise InvalidQueryError(
                    f"El mode «{mode}» no és vàlid.",
                    hint="Modes: indicatiu, subjuntiu, imperatiu o formes no personals.",
                )
        person_key: str | None = None
        if persona:
            person_key = _PERSON_ALIASES.get(normalize_key(persona))
            if person_key is None:
                raise InvalidQueryError(
                    f"La persona «{persona}» no és vàlida.",
                    hint="Indica jo, tu, ell/ella/vostè, nosaltres, vosaltres o ells/elles/vostès.",
                )
        temps_key = normalize_key(temps) if temps else None
        url = f"{BASE_URL}/conjugador-de-verbs/verb/{_slug(verb)}/"
        try:
            result = await self.client.get_text(url, cache_ttl=86400)
        except UpstreamError as exc:
            if "404" not in exc.message:
                raise
            return {
                "status": "no_results",
                "verb": verb,
                "url": url,
                "warnings": ["zero_results"],
                "source": url,
                "retrieved_at": _now(),
            }
        parsed = parse_conjugation(result.text)
        if not parsed["found"]:
            status = "no_results" if parsed["not_found_message"] else "unexpected_response"
            warnings = list(result.warnings + parsed["warnings"])
            if status == "no_results":
                warnings.append("zero_results")
            return {
                "status": status,
                "verb": verb,
                "url": url,
                "warnings": list(dict.fromkeys(warnings)),
                "source": url,
                "retrieved_at": _now(),
            }

        if not _same_lemma(verb, parsed["infinitive"]):
            return {
                "status": "unexpected_response",
                "verb": verb,
                "title": parsed["infinitive"],
                "url": url,
                "warnings": list(dict.fromkeys(result.warnings + ["infinitive_mismatch"])),
                "source": url,
                "retrieved_at": _now(),
            }

        sections = parsed["sections"]
        if selected_mode:
            sections = [
                section
                for section in sections
                if normalize_key(section["mode"]) == normalize_key(selected_mode)
            ]
        output_sections: list[dict[str, Any]] = []
        for section in sections:
            rows = section["rows"]
            if temps_key:
                rows = [row for row in rows if normalize_key(row["tense"]) == temps_key]
            if person_key:
                rows = [
                    {
                        **row,
                        "persons": [
                            person for person in row["persons"] if person["key"] == person_key
                        ],
                    }
                    for row in rows
                ]
            if rows:
                output_sections.append({**section, "rows": rows})
        if (selected_mode or temps_key or person_key) and not output_sections:
            raise InvalidQueryError(
                "Els filtres no coincideixen amb cap apartat de la fitxa.",
                hint="Comprova el mode, el temps i la persona disponibles a la fitxa enllaçada.",
                source=url,
            )

        warnings = list(result.warnings + parsed["warnings"])
        return {
            "status": "ok",
            "verb": parsed["infinitive"],
            "note": parsed["note"],
            "sections": output_sections,
            "url": url,
            "warnings": list(dict.fromkeys(warnings)),
            "source": url,
            "retrieved_at": _now(),
            "citation": (
                f"Conjugador de Softcatalà, «{parsed['infinitive']}», consultat el {_now()}."
            ),
        }
