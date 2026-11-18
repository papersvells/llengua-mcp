"""Vocabulari del CTILC: categories, subcategories i morfologia.

És un subconjunt llegible i documentat, no una còpia completa del formulari.
La font de veritat és el formulari del CTILC; si hi ha discrepància, mana el
formulari.
"""

from __future__ import annotations

from typing import Any

CATEGORIES: dict[str, str] = {
    "adj": "adjectiu",
    "subst": "substantiu",
    "verb": "verb",
    "NP": "nom propi",
    "AV": "adverbi",
    "AR": "adverbi (categoria secundària)",
    "C": "conjunció",
    "CT": "conjunció",
    "DEM": "demostratiu",
    "IND": "indefinit",
    "IFX": "interfix",
    "I": "interjecció",
    "L": "article",
    "LA": "article",
    "NC": "nom comú",
    "NUM": "numeral",
    "POS": "possessiu",
    "PFX": "prefix",
    "PO": "possessiu",
    "P": "preposició",
    "QUA": "quantitatiu",
    "REL": "relatiu",
    "SIG": "sigla",
    "SFX": "sufix",
}

SUBCATEGORIES: dict[str, str] = {
    "A": "adjectiu",
    "AF": "adjectiu femení",
    "AI": "adjectiu invariable",
    "AII": "adjectiu invariable",
    "AM": "adjectiu masculí",
    "AMP": "adjectiu masculí plural",
    "F": "femení",
    "FP": "femení plural",
    "FS": "femení singular",
    "M": "masculí",
    "MF": "masculí/femení",
    "MFP": "masculí/femení plural",
    "MP": "masculí plural",
    "MS": "masculí singular",
    "V": "verb",
    "VA": "verb auxiliar",
}

MORPHOLOGY: dict[str, str] = {
    "IF": "infinitiu",
    "GE": "gerundi",
    "RMS": "participi regular masculí singular",
    "RFS": "participi regular femení singular",
    "RMP": "participi regular masculí plural",
    "RFP": "participi regular femení plural",
    "MS": "masculí singular",
    "FS": "femení singular",
    "MP": "masculí plural",
    "FP": "femení plural",
    "M": "masculí",
    "F": "femení",
    "S": "singular",
    "P": "plural",
    "D": "determinat",
    "DS": "determinat singular",
    "DP": "determinat plural",
    "DMS": "determinat masculí singular",
    "DFS": "determinat femení singular",
    "DMP": "determinat masculí plural",
    "DFP": "determinat femení plural",
    "DM": "determinat masculí",
    "2IM": "imperatiu 2a persona",
    "3IM": "imperatiu 3a persona",
    "4IM": "imperatiu 4a persona",
    "5IM": "imperatiu 5a persona",
    "6IM": "imperatiu 6a persona",
}

_PERSON = {"1": "1a", "2": "2a", "3": "3a", "4": "4a", "5": "5a", "6": "6a"}
_NUMBER = {"S": "singular", "P": "plural"}
_TENSE = {
    "I": "present d'indicatiu",
    "II": "imperfet d'indicatiu",
    "T": "present de subjuntiu",
    "FU": "futur",
    "PS": "passat simple",
    "IS": "imperfet de subjuntiu",
    "CO": "condicional",
}

VERB_PERSONS: dict[str, str] = {}
for _person, _person_label in _PERSON.items():
    for _suffix, _tense in _TENSE.items():
        VERB_PERSONS[f"{_person}{_suffix}"] = f"{_person_label} persona {_tense}"
    for _number, _number_label in _NUMBER.items():
        VERB_PERSONS[f"{_person}{_number}"] = f"{_person_label} persona {_number_label}"


def describe_category(code: str) -> str | None:
    return CATEGORIES.get(code) or SUBCATEGORIES.get(code)


def describe_morphology(code: str) -> str | None:
    if code == "-":
        return "sense morfologia especificada"
    return MORPHOLOGY.get(code) or VERB_PERSONS.get(code)


def describe_cg(value: str) -> str:
    """Descriu un valor `categoria:morfologia` de manera llegible."""

    if value == "qualsevol":
        return "qualsevol paraula"
    category, _, morphology = value.partition(":")
    category_label = describe_category(category) or category
    if not morphology:
        return category_label
    morphology_label = describe_morphology(morphology) or morphology
    return f"{category_label}; {morphology_label}"


def tagset_payload() -> dict[str, Any]:
    return {
        "source": "Formulari de combinacions del CTILC",
        "note": (
            "Subconjunt llegible. El CTILC pot afegir categories o codis; "
            "consulteu el formulari si una etiqueta no apareix aquí."
        ),
        "categories": [{"code": code, "label": label} for code, label in CATEGORIES.items()],
        "subcategories": [{"code": code, "label": label} for code, label in SUBCATEGORIES.items()],
        "morphology": [{"code": code, "label": label} for code, label in MORPHOLOGY.items()]
        + [{"code": code, "label": label} for code, label in sorted(VERB_PERSONS.items())],
    }
