"""Compilació d'una consulta lingüística al protocol `NN*clau` del CTILC.

La regla més important: el `*` de la clau ha de quedar literal. Els valors
s'han de codificar una sola vegada amb `quote(..., safe="")`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

from llengua_mcp.errors import InvalidQueryError
from llengua_mcp.models import PatternElement
from llengua_mcp.text import clean_text

MAX_ELEMENTS = 10
MAX_OPTIONAL_CHAIN = 5
_SPECIAL_VALUE_CHARS = re.compile(r"[|<>()]")


@dataclass(frozen=True)
class CompiledPattern:
    """Patró llest per enviar i per contrastar l'eco del servidor."""

    elements: tuple[PatternElement, ...]
    fields: tuple[tuple[str, str], ...]
    expected: dict[str, str] = field(default_factory=dict)

    def body(self, *, start: int, offset: int, filters: dict[str, str] | None = None) -> str:
        return build_body(self.fields, start=start, offset=offset, filters=filters)

    def public_query(self) -> dict:
        return {
            "mode": "patro",
            "elements": [
                element.model_dump(exclude_none=True, exclude_defaults=True)
                for element in self.elements
            ],
        }


def _element_key(index: int) -> str:
    if index > 99:
        raise InvalidQueryError(
            "El patró té massa posicions.",
            hint="El CTILC accepta com a màxim 99 posicions (00–99).",
        )
    return f"{index:02d}"


def _join_alternatives(values: list[str]) -> str:
    for value in values:
        if "|" in value:
            raise InvalidQueryError(
                "Un valor no pot contenir `|` i `alternatives` alhora.",
                hint="Separa les variants amb el camp `alternatives`, no dins de `value`.",
            )
    return "|".join(values)


def _apply_modifiers(value: str, element: PatternElement) -> str:
    if element.negated and element.optional:
        raise InvalidQueryError(
            "No es pot combinar `negated` i `optional`.",
            hint=(
                "El CTILC retorna HTTP 500 amb construccions com `(<>amb)`. "
                "Fes servir només un dels dos modificadors."
            ),
        )
    if element.negated:
        # La interfície envia `<>amb|de` (sense parèntesis); l'eco els afegeix
        # visualment. No copiem l'eco com a entrada.
        return f"<>{value}"
    if element.optional:
        return f"({value})"
    return value


def _cg_value(category: str, morphology: str | None) -> str:
    category = clean_text(category)
    morphology = clean_text(morphology) if morphology else ""
    if not category:
        raise InvalidQueryError(
            "Falta la categoria de l'element `cg`.",
            hint="Indica `category`, per exemple `adj`, `subst` o `V`.",
        )
    if category == "qualsevol":
        return "qualsevol"
    if ":" in category:
        raise InvalidQueryError(
            "La categoria no ha de contenir `:`.",
            hint="Indica la categoria a `category` i el codi a `morphology`.",
        )
    return f"{category}:{morphology or '-'}"


def _compile_element(index: int, element: PatternElement) -> tuple[str, str, str]:
    """Retorna (clau, valor, valor esperat a l'eco)."""

    key = f"{_element_key(index)}*"

    if element.type == "qualsevol":
        if element.alternatives:
            raise InvalidQueryError("`qualsevol` no admet `alternatives`.")
        value = _apply_modifiers("qualsevol", element)
        return f"{key}cg", value, value

    if element.type == "forma":
        values = []
        if element.value:
            values.append(clean_text(element.value))
        if element.alternatives:
            values.extend(clean_text(item) for item in element.alternatives)
        if not values:
            raise InvalidQueryError(
                "Falta la forma.",
                hint="Indica `value` amb una sola forma gràfica.",
            )
        for value in values:
            if not value:
                raise InvalidQueryError("Hi ha una forma buida.")
            if _SPECIAL_VALUE_CHARS.search(value):
                raise InvalidQueryError(
                    f"La forma «{value}» conté un caràcter reservat (`|`, `<`, `>`, `(` o `)`).",
                    hint="Fes servir `alternatives`, `negated` o `optional` en lloc d'escriure'ls.",
                )
            if re.search(r"\s", value):
                raise InvalidQueryError(
                    f"«{value}» conté espais.",
                    hint=(
                        "`forma` és una sola forma gràfica. Per a una frase, crea un "
                        "element per paraula o fes servir `cerca_frase`."
                    ),
                )
            if re.search(r"[.,;:!?«»“”\"]", value):
                raise InvalidQueryError(
                    f"La forma «{value}» conté puntuació.",
                    hint="Treu la puntuació externa: el corpus tokenitza per formes.",
                )
        joined = _join_alternatives(values)
        value = _apply_modifiers(joined, element)
        return f"{key}forma", value, value

    if element.type == "lema":
        if element.alternatives:
            raise InvalidQueryError(
                "`lema` no admet `alternatives` en aquesta versió.",
                hint="Fes servir un sol lema i, si cal, una categoria amb `category`.",
            )
        lema = clean_text(element.value)
        if not lema:
            raise InvalidQueryError("Falta el lema.")
        if ":" in lema:
            raise InvalidQueryError(
                f"«{lema}» fa servir `:`.",
                hint="Per unir lema i categoria cal `@`, per exemple `somriure@V`.",
            )
        if "@" in lema and element.category:
            raise InvalidQueryError(
                "El lema ja porta una categoria amb `@`.",
                hint="No repetisquis `category` si el valor ja conté `@`.",
            )
        if _SPECIAL_VALUE_CHARS.search(lema):
            raise InvalidQueryError(
                f"El lema «{lema}» conté un caràcter reservat.",
                hint="No es poden combinar alternatives, negació i opcionalitat en un lema.",
            )
        if element.category:
            lema = f"{lema}@{clean_text(element.category)}"
        value = _apply_modifiers(lema, element)
        return f"{key}lema", value, value

    if element.type == "cg":
        values = []
        if element.category or element.morphology:
            values.append(_cg_value(element.category or "", element.morphology))
        if element.alternatives:
            for item in element.alternatives:
                category, _, morphology = clean_text(item).partition(":")
                values.append(_cg_value(category, morphology or None))
        if not values:
            raise InvalidQueryError(
                "Falta la categoria de l'element `cg`.",
                hint="Indica `category`, per exemple `adj`.",
            )
        joined = _join_alternatives(values)
        value = _apply_modifiers(joined, element)
        return f"{key}cg", value, value

    # formalema
    if element.alternatives:
        raise InvalidQueryError("`formalema` no admet `alternatives`.")
    lema = clean_text(element.value)
    category = clean_text(element.category)
    if not lema or not category:
        raise InvalidQueryError(
            "`formalema` necessita `value` (lema) i `category`.",
            hint="Exemple: lema `somriure`, categoria `V` i formes amb el seu codi.",
        )
    if not element.forms:
        raise InvalidQueryError(
            "`formalema` necessita `forms`.",
            hint="Cada forma ha de portar el seu codi morfològic, per exemple `IF` o `3II`.",
        )
    forms = []
    for spec in element.forms:
        form = clean_text(spec.form)
        cg = clean_text(spec.cg) or "-"
        if not form or re.search(r"\s", form):
            raise InvalidQueryError(
                f"La forma «{form}» no és vàlida.",
                hint="`formalema` accepta formes gràfiques sense espais.",
            )
        if any(char in form + cg for char in "¬|:"):
            raise InvalidQueryError(
                "Els components de `formalema` no poden contenir `¬`, `|` ni `:`.",
            )
        forms.append(f"{form}:{cg}")
    value = f"{lema}:{category}¬{'|'.join(forms)}"
    value = _apply_modifiers(value, element)
    return f"{key}formalema", value, value


def compile_pattern(
    elements: list[PatternElement],
    *,
    optional_chain_limit: int = MAX_OPTIONAL_CHAIN,
) -> CompiledPattern:
    if not elements:
        raise InvalidQueryError(
            "El patró és buit.",
            hint="Indica almenys un element (`lema`, `forma`, `cg`...).",
        )
    if len(elements) > MAX_ELEMENTS:
        raise InvalidQueryError(
            f"El patró té {len(elements)} elements; el màxim és {MAX_ELEMENTS}.",
            hint="Divideix la consulta o fes servir una frase més curta.",
        )

    optional_run = 0
    for element in elements:
        optional_run = optional_run + 1 if element.optional else 0
        if optional_run > optional_chain_limit:
            raise InvalidQueryError(
                f"Hi ha més de {optional_chain_limit} elements opcionals seguits.",
                hint="Redueix l'interval; una cadena massa llarga pot ser molt costosa.",
            )

    fields: list[tuple[str, str]] = []
    expected: dict[str, str] = {}
    for index, element in enumerate(elements):
        key, value, echo_value = _compile_element(index, element)
        fields.append((key, value))
        expected[key] = echo_value

    return CompiledPattern(tuple(elements), tuple(fields), expected)


def build_body(
    fields: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    start: int,
    offset: int,
    filters: dict[str, str] | None = None,
) -> str:
    """Construeix el cos amb `*` literal i valors codificats una vegada."""

    if start < 1:
        raise InvalidQueryError(
            "`iStart` ha de ser 1 o més gran.",
            hint="La paginació del CTILC és 1-based; `iStart=0` no és equivalent.",
        )
    if offset < 1:
        raise InvalidQueryError("`iOffset` ha de ser positiu.")

    parts = ["seccio=CTILC1"]
    for key, value in fields:
        if "*" not in key:
            raise InvalidQueryError(
                f"La clau «{key}» no té el separador `*`.",
                hint="Les claus són del tipus `00*lema`.",
            )
        parts.append(f"{key}={quote(value, safe='')}")
    for name, value in (filters or {}).items():
        if value:
            parts.append(f"{name}={quote(value, safe='')}")
    parts.append(f"iStart={start}")
    parts.append(f"iOffset={offset}")
    return "&".join(parts)


def phrase_elements(frase: str) -> list[PatternElement]:
    """Converteix una frase en un element `forma` per paraula."""

    text = clean_text(frase)
    if not text:
        raise InvalidQueryError(
            "La frase és buida.",
            hint="Escriu la paraula, l'expressió o la frase que vols consultar.",
        )
    tokens = [token for token in text.split(" ") if token]
    if len(tokens) > MAX_ELEMENTS:
        raise InvalidQueryError(
            f"La frase té {len(tokens)} paraules; el màxim és {MAX_ELEMENTS}.",
            hint="Consulta una seqüència més curta o fes servir `cerca_patro`.",
        )
    for token in tokens:
        if _SPECIAL_VALUE_CHARS.search(token):
            raise InvalidQueryError(
                f"El token «{token}» conté un caràcter reservat (`|`, `<`, `>`, `(`, `)`).",
                hint=(
                    "`cerca_frase` busca formes literals. Per a alternatives o "
                    "negacions, fes servir `cerca_patro`."
                ),
            )
        if re.search(r"[.,;:!?«»“”\"]", token):
            raise InvalidQueryError(
                f"La frase conté puntuació a «{token}».",
                hint=(
                    "El corpus tokenitza per formes. Treu la puntuació externa o "
                    "fes servir `cerca_patro` si la necessites."
                ),
            )
    return [PatternElement(type="forma", value=token) for token in tokens]


def phrase_query(frase: str, variants: list[str] | None = None) -> dict:
    return {
        "mode": "frase",
        "frase": clean_text(frase),
        "variants": [clean_text(variant) for variant in variants or [] if clean_text(variant)],
    }


def patro_query(elements: list[PatternElement]) -> dict:
    return {
        "mode": "patro",
        "elements": [
            element.model_dump(exclude_none=True, exclude_defaults=True) for element in elements
        ],
    }
