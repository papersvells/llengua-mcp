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
_PRONOMINAL_ENDINGS = ("-se'n", "-se", "-s")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _without_pronoun(verb: str) -> str:
    for ending in _PRONOMINAL_ENDINGS:
        if verb.casefold().endswith(ending):
            return verb[: -len(ending)]
    return verb


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
        # La ruta fa servir l'infinitiu base, però això no identifica la fitxa.
        base = _without_pronoun(verb)
        url = f"{BASE_URL}/conjugador-de-verbs/verb/{quote(base, safe='-')}/"
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

        infinitive = parsed["infinitive"]
        found_key = normalize_key(infinitive)
        base_only = base != verb and found_key == normalize_key(base)
        if found_key != normalize_key(verb) and not base_only:
            return {
                "status": "unexpected_response",
                "verb": verb,
                "title": infinitive,
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
        if base_only:
            warnings.append("pronominal_base_only")
        return {
            "status": "partial" if base_only else "ok",
            "requested_verb": verb,
            "verb": infinitive,
            **(
                {
                    "fallback_note": (
                        f"La font mostra la fitxa del verb simple «{infinitive}», "
                        f"no la de «{verb}». Les formes següents corresponen "
                        "al verb simple; no són una conjugació pronominal."
                    )
                }
                if base_only
                else {}
            ),
            "note": parsed["note"],
            "sections": output_sections,
            "url": url,
            "warnings": list(dict.fromkeys(warnings)),
            "source": url,
            "retrieved_at": _now(),
            "citation": f"Conjugador de Softcatalà, «{infinitive}», consultat el {_now()}.",
        }
