"""Models de dades compartits."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ElementType = Literal["lema", "forma", "formalema", "cg", "qualsevol"]


class FormSpec(BaseModel):
    """Una forma concreta dins d'un element `formalema`."""

    form: str = Field(description="Forma gràfica, sense espais.")
    cg: str = Field(
        default="-",
        description="Categoria o codi morfològic de la forma (p. ex. IF, 3II).",
    )


class CtilcFilters(BaseModel):
    """Filtres estructurals d'una consulta al CTILC.

    Els valors es normalitzen a l'adaptador. `any_min` i `any_max` es poden
    fer servir sols; el rang vàlid és 1832–2022. `traduccio` és `True` per a
    obres traduïdes, `False` per a originals i `None` per a totes.
    `classtem` és la classificació temàtica de les obres no literàries: un
    grup sencer (`3`) o un sol subtema (`3.2`). No es combina amb `genere`.
    """

    autor: list[str] | None = None
    titol: list[str] | None = None
    any_min: int | None = None
    any_max: int | None = None
    tipus: list[str] | None = None
    genere: list[str] | None = None
    classtem: list[str] | None = None
    varietat: list[str] | None = None
    traduccio: bool | None = None


class PatternElement(BaseModel):
    """Un element del patró de combinacions del CTILC.

    `type` decideix quins camps s'utilitzen:

    - `lema`: `value` (lema) i, opcionalment, `category` (p. ex. subst, V).
    - `forma`: `value` (una sola forma gràfica, sense espais).
    - `formalema`: `value` (lema), `category` i `forms` (llista de formes).
    - `cg`: `category` i, opcionalment, `morphology` (per defecte `-`).
    - `qualsevol`: comodí; pot ser `optional`.

    `alternatives` afegeix variants separades per `|` (només per a `forma` i `cg`).
    `optional` envolta el valor amb parèntesis; `negated` hi posa `<>`.
    No es poden combinar `optional` i `negated`: el servidor retorna HTTP 500.
    """

    type: ElementType
    value: str | None = None
    category: str | None = None
    morphology: str | None = None
    forms: list[FormSpec] | None = None
    alternatives: list[str] | None = None
    optional: bool = False
    negated: bool = False

    @field_validator("value", "category", "morphology")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class WorkRef(BaseModel):
    id: str | None = Field(default=None, description="Identificador canònic de l'obra.")
    title: str | None = None
    author: str | None = None
    year: int | None = None
    variety: str | None = None
    kind: str | None = None
    classification: str | None = None


class Occurrence(BaseModel):
    left: str = ""
    nucleus: str = ""
    nucleus_tokens: list[str] = Field(default_factory=list)
    right: str = ""
    occurrence_id: str | None = Field(
        default=None,
        description="Identificador de la fitxa de localització; sempre com a cadena.",
    )
    obra_param: str | None = Field(
        default=None,
        description="Paràmetre `obra` de la fitxa. No és l'ID bibliogràfic.",
    )
    seccio: str | None = None
    work: WorkRef | None = None


class CtilcPage(BaseModel):
    """Resultat estructural d'una pàgina de concordances."""

    pattern_echo: str = ""
    total: int | None = None
    total_unfiltered: int | None = None
    filtered_total: int | None = None
    filters_echo: dict[str, str] = Field(default_factory=dict)
    filters_summary: list[str] = Field(default_factory=list)
    occurrences: list[Occurrence] = Field(default_factory=list)
    zero_message: str | None = None
    echo_verified: bool = False
    pagination_fields: dict[str, str] = Field(default_factory=dict)
    explicit_zero: bool = False
    server_fields: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    has_results_container: bool = False


class CursorPayload(BaseModel):
    """Estat intern d'una cerca paginable. No s'exposa mai sencer."""

    v: Literal[1] = 1
    kind: Literal["ctilc"] = "ctilc"
    query: dict = Field(default_factory=dict)
    elements: list[PatternElement] = Field(default_factory=list)
    pattern_echo: str = ""
    total: int = 0
    resultat: str | None = None
    qlocali: str | None = None
    filters: dict[str, str] = Field(default_factory=dict)
    pagination_fields: dict[str, str] = Field(default_factory=dict)
    next_start: int = 1
    page_size: int = 10
    created_at: datetime


class SourceMeta(BaseModel):
    source: str
    retrieved_at: str
    citation: str


class VariantOutcome(BaseModel):
    variant: str
    status: str
    pattern_echo: str = ""
    echo_verified: bool = False
    total: int | None = None
    returned: int = 0
    has_more: bool = False
    next_cursor: str | None = None
    occurrences: list[Occurrence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
