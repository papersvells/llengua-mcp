"""Parser de les respostes XML del motor de BDLex (IEC)."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from llengua_mcp.text import clean_text

DICTIONARY_LABELS = {
    "DIEe": "DIEC2 (versió en línia, 2024)",
    "DIE2": "DIEC2 (2007)",
    "DIEC": "DIEC1 (1995)",
    "DGFP": "Diccionari general (Ferrer Pastor, 1985)",
    "DCVB": "Diccionari català-valencià-balear (Alcover-Moll)",
    "DGLC": "Diccionari general de la llengua catalana (Fabra, 1932)",
    "DPCV": "Pal·las (Vallès, 1927)",
    "DGMG": "Novísimo diccionario general valenciano-castellano (Martí i Gadea, 1891)",
    "DMCT": "Diccionari mallorquí-castellà (Tarongí, 1878)",
    "NDMA": "Nuevo diccionario mallorquín-castellano-latín (Amengual, 1858)",
    "DVCE": "Diccionario valenciano-castellano (Escrig, 1851)",
    "DMCF": "Diccionari mallorquí-castellà (Figuera, 1840)",
    "DLCL": "Diccionari de la llengua catalana (Labèrnia, 1839-1840)",
    "DEBJ": "Diccionario catalán-castellano-latino (Esteve et al., 1803-1805)",
    "DMFC": "Diccionari menorquí (Febrer i Cardona, s. XIX)",
}

SPECIAL_SENSES = {"FON", "ETI", "CJG", "SIN"}
MAX_DEFINITION_CHARS = 500
MAX_EXAMPLES_PER_SENSE = 2
MAX_SUBENTRIES_PER_SENSE = 5
MAX_TRANSLATIONS = 3
MAX_PHONETICS = 5
MAX_SYNONYMS = 8
MAX_PHRASES = 5


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return clean_text("".join(node.itertext()))


def _child_text(node: ET.Element, path: str) -> str:
    return _text(node.find(path))


def _clip(value: str, limit: int) -> tuple[str, bool]:
    value = clean_text(value)
    if len(value) <= limit:
        return value, False
    return value[: limit - 1].rstrip() + "…", True


def _parse_root(xml_text: str) -> ET.Element:
    root = ET.fromstring(xml_text)
    if root.tag != "result":
        raise ET.ParseError(f"Arrel XML inesperada: {root.tag}")
    if root.find("error") is not None:
        raise ET.ParseError("El motor de BDLex ha retornat un error.")
    return root


def parse_ids(xml_text: str) -> list[str]:
    root = _parse_root(xml_text)
    return [clean_text(node.text) for node in root.findall("entry") if clean_text(node.text)]


def _sense_number(sense: ET.Element) -> str:
    ng = " ".join(_text(node) for node in sense.findall("sep/ng"))
    cs = " ".join(_text(node) for node in sense.findall("sep/cs"))
    if ng and cs:
        return f"{ng}.{cs}"
    if ng:
        return ng
    return clean_text(sense.attrib.get("r") or sense.attrib.get("n") or "")


def _examples(sense: ET.Element) -> tuple[list[str], list[str]]:
    examples: list[str] = []
    regions: list[str] = []
    for eg in sense.findall("eg"):
        cit = eg.find("cit")
        text = _text(eg.find("q")) or _text(cit.find("quote") if cit is not None else None)
        if not text:
            continue
        labels = [clean_text(usg.text) for usg in eg.findall("usg")]
        labels = [label for label in labels if label]
        bibl = _text(cit.find("bibl") if cit is not None else eg.find("bibl"))
        example = text
        if labels:
            example += " " + " ".join(labels)
        if bibl:
            example += " " + bibl
        examples.append(example)
        for usg in eg.findall("usg"):
            region = clean_text(usg.attrib.get("u") or "")
            if region and region not in regions:
                regions.append(region)
    return examples[:MAX_EXAMPLES_PER_SENSE], regions


def _parse_sense(sense: ET.Element) -> dict[str, Any]:
    definition, truncated = _clip(_text_defs(sense), MAX_DEFINITION_CHARS)
    examples, regions = _examples(sense)
    translations = []
    for trans in sense.findall("trans"):
        lang = _child_text(trans, "lang")
        values = [_text(tr) for tr in trans.findall("tr")]
        values = [value for value in values if value]
        if values:
            translations.append((lang + " " + "; ".join(values)).strip())
    translations = translations[:MAX_TRANSLATIONS]

    labels = []
    for usg in sense.findall("gramGrp/usg"):
        value = _text(usg)
        if value and value not in labels:
            labels.append(value)
    for usg in sense.findall("usg"):
        if (usg.attrib.get("type") or "").upper() == "GEO":
            continue
        value = _text(usg)
        if value and value not in labels:
            labels.append(value)
    for facet in sense.findall("facets/facet"):
        if facet.attrib.get("name") == "geo":
            for region in (facet.attrib.get("val") or "").split("|"):
                region = clean_text(region)
                if region and region not in regions:
                    regions.append(region)

    subentries = []
    for sub in sense.findall("subent"):
        title = _text(sub.find("se"))
        gloss = _text(sub.find("dfse"))
        if title:
            subentries.append({"title": title, "definition": gloss})

    cross_refs = []
    for ref in sense.findall("rem/re"):
        value = _text(ref)
        if value:
            cross_refs.append(value)

    subentries_truncated = len(subentries) > MAX_SUBENTRIES_PER_SENSE
    payload: dict[str, Any] = {
        "number": _sense_number(sense),
        "level": sense.attrib.get("level"),
        "definition": definition,
        "translations": translations,
        "examples": examples,
        "labels": labels,
        "regions": regions,
        "cross_refs": cross_refs,
        "subentries": subentries[:MAX_SUBENTRIES_PER_SENSE],
        "subentries_truncated": subentries_truncated,
    }
    if truncated:
        payload["definition_truncated"] = True
    return payload


def _text_defs(sense: ET.Element) -> str:
    values = [_text(node) for node in sense.findall("def")]
    return " ".join(value for value in values if value)


def _special_sections(entry: ET.Element) -> dict[str, Any]:
    phonetics: list[dict[str, Any]] = []
    etymology: list[str] = []
    synonyms: list[str] = []
    conjugation: list[str] = []
    phrases: list[str] = []

    for sense in entry.findall("sense"):
        loc = (sense.attrib.get("loc") or "").upper()
        if loc == "FON":
            for form in sense.findall("form"):
                for f1 in form.findall("pron/f1"):
                    value = _text(f1)
                    if not value:
                        continue
                    regions = [clean_text(usg.attrib.get("u") or "") for usg in form.findall("usg")]
                    phonetics.append(
                        {
                            "afi": value,
                            "regions": [region for region in regions if region],
                        }
                    )
        elif loc == "ETI":
            value = _text(sense.find("etym"))
            extra = " ".join(_text(cs) for cs in sense.findall("cs"))
            combined = clean_text(f"{value} {extra}")
            if combined:
                etymology.append(combined)
        elif loc == "SIN":
            synonyms.extend(value for value in (_text(cs) for cs in sense.findall("cs")) if value)
        elif loc == "CJG":
            conjugation.extend(
                value for value in (_text(cs) for cs in sense.findall("cs")) if value
            )
        elif loc.startswith("RFR"):
            for eg in sense.findall("eg"):
                value = _text(eg.find("q")) or _text(eg.find("cit/quote"))
                if value:
                    phrases.append(value)

    return {
        "phonetics": phonetics[:MAX_PHONETICS],
        "phonetics_truncated": len(phonetics) > MAX_PHONETICS,
        "etymology": " ".join(etymology),
        "synonyms": synonyms[:MAX_SYNONYMS],
        "synonyms_truncated": len(synonyms) > MAX_SYNONYMS,
        "conjugation": " ".join(conjugation),
        "phrases": phrases[:MAX_PHRASES],
        "phrases_truncated": len(phrases) > MAX_PHRASES,
    }


def parse_entries(xml_text: str, *, max_senses: int = 6) -> list[dict[str, Any]]:
    root = _parse_root(xml_text)
    entries: list[dict[str, Any]] = []
    for entry in root.findall("entry"):
        ordinary = [
            sense
            for sense in entry.findall("sense")
            if (sense.attrib.get("loc") or "").upper() not in SPECIAL_SENSES
            and not (sense.attrib.get("loc") or "").upper().startswith("RFR")
        ]
        senses = [_parse_sense(sense) for sense in ordinary[:max_senses]]
        senses_truncated = len(ordinary) > max_senses

        forms = []
        for orth in entry.findall("form/orth"):
            value = _text(orth)
            if value and value not in forms:
                forms.append(value)
        for key in entry.findall("form/key"):
            value = clean_text(key.attrib.get("val") or "")
            if value and value not in forms:
                forms.append(value)

        pos = _child_text(entry, "gramGrp/pos")
        if not pos:
            pos = _child_text(entry, "sense/gramGrp/pos")

        specials = _special_sections(entry)
        dictionary = entry.attrib.get("dict") or ""
        entries.append(
            {
                "dictionary": dictionary,
                "dictionary_label": DICTIONARY_LABELS.get(dictionary, dictionary),
                "entry_id": entry.attrib.get("id"),
                "headword": clean_text(entry.attrib.get("headword") or ""),
                "forms": forms,
                "pos": pos,
                "senses": senses,
                "senses_truncated": senses_truncated,
                **specials,
            }
        )
    return entries
