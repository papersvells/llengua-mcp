"""Parser de les concordances del CTILC."""

from __future__ import annotations

import re
from contextlib import suppress
from urllib.parse import parse_qsl

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode

from llengua_mcp.models import CtilcPage, Occurrence
from llengua_mcp.text import clean_text, normalize_key

_PATTERN_RE = re.compile(
    r"Patró seleccionat\s*:\s*(.*?)\s*(?:CTILC1\s*)?Freqüència total\s*:",
    re.DOTALL,
)
_PATTERN_FALLBACK_RE = re.compile(r"Patró seleccionat\s*:\s*(.*?)\s*CTILC1", re.DOTALL)
_TOTAL_LABEL = "Freqüència total"
_FILTERED_TOTAL_LABEL = "Quantitat filtrada"
_COUNTER_RE = re.compile(r"[0-9]+|[1-9][0-9]{0,2}(?:\.[0-9]{3})+")
_FILTER_SUMMARY_RE = re.compile(r"<b>Filtre per ([^:<]+?)</b>\s*:\s*([^<]*)")
_FILTER_FIELDS = (
    "autSelec",
    "titSelec",
    "anySelec",
    "tipusSelec",
    "genSelec",
    "classtemSelec",
    "classtemGSelec",
    "tradSelec",
    "varSelec",
)
_PAGINATION_FIELDS = (
    *_FILTER_FIELDS,
    "filtres",
    "seccio",
    "aleatoriVal",
    "aleatoriSel",
    "resultat_orig",
    "strquery",
    "strqueryTXT",
    "formdata",
    "resultat",
    "Qlocali",
    "iStart",
    "iOffset",
)
_ZERO_RE = re.compile(
    r"No s'han trobat ocurrències per al patró seleccionat\s*:\s*([^<]{0,300})",
    re.DOTALL,
)
# Missatge reconegut de cap coincidència; qualsevol altre text vermell pot ser
# un avís del servei i no demostra una absència.
_ZERO_MESSAGE = "no s'han trobat ocurrencies per al patro seleccionat"
_FITXA_RE = re.compile(
    r"CTILCQFitxaLocalitzacio\.asp\?id=(\d+)&(?:amp;)?tok=([^&'\"]+)"
    r"&(?:amp;)?seccio=([^&'\"]+)&(?:amp;)?obra=(\d+)"
)


def _read_counters(labels: list[LexborNode]) -> dict[str, int | None]:
    """Distingeix un comptador absent d'un de present però invàlid."""

    counters: dict[str, int | None] = {}
    for node in labels:
        label = clean_text(node.text(separator=""))
        if label not in (_TOTAL_LABEL, _FILTERED_TOTAL_LABEL):
            continue
        if label in counters:
            counters[label] = None
            continue
        cell = clean_text(node.parent.text(separator=""))
        value = cell.removeprefix(f"{label}:").strip()
        counters[label] = None
        if _COUNTER_RE.fullmatch(value):
            with suppress(ValueError):
                counters[label] = int(value.replace(".", ""))
    return counters


def parse_formdata(value: str) -> dict[str, str]:
    """Retorna els camps del formulari amagat, incloent-hi les claus `NN*`."""

    fields: dict[str, str] = {}
    for key, item in parse_qsl(value, keep_blank_values=True):
        fields[key] = item
    return fields


def element_fields(fields: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in fields.items() if re.match(r"^\d{2,}\*", key)}


def _normalize_pattern(value: str) -> str:
    value = clean_text(value).replace("@", " ")
    # El servidor mostra els comodins i les alternatives amb una sintaxi
    # auxiliar: `[]?`, `(amb | de)`. Per comparar-los amb el que hem enviat,
    # en normalizeu la presentació; la forma enviada ja queda validada pel
    # `formdata` ocult.
    value = value.replace("[]?", "qualsevol").replace("[]", "qualsevol")
    value = re.sub(r"<>\(([^)]*)\)", r"<>\1", value)
    value = value.replace("(", "").replace(")", "").replace("?", "")
    value = re.sub(r"\s*([<>|])\s*", r"\1", value)
    return value


def patterns_equivalent(echo: str, expected: str) -> bool:
    return _normalize_pattern(echo).split() == _normalize_pattern(expected).split()


def parse_ctilc_page(
    html: str,
    *,
    expected: dict[str, str] | None = None,
    expected_pattern: str | None = None,
) -> CtilcPage:
    doc = HTMLParser(html)
    header = doc.css_first("#cHTML1")
    warnings: list[str] = []

    pattern_echo = ""
    whole_text = clean_text(doc.body.text(separator="") if doc.body else "")
    header_text = clean_text(header.text(separator="")) if header is not None else whole_text
    match = _PATTERN_RE.search(header_text)
    if match:
        pattern_echo = clean_text(match.group(1))
    else:
        fallback = _PATTERN_FALLBACK_RE.search(header_text)
        if fallback:
            pattern_echo = clean_text(fallback.group(1))

    if header is None:
        counters = _read_counters(doc.css("table.tableFILTREStop td > b"))
    else:
        counters = _read_counters(header.css("td > b"))
        if _FILTERED_TOTAL_LABEL not in counters:
            fallback_counters = _read_counters(doc.css("table.tableFILTREStop td > b"))
            if _FILTERED_TOTAL_LABEL in fallback_counters:
                counters[_FILTERED_TOTAL_LABEL] = fallback_counters[_FILTERED_TOTAL_LABEL]
    total_unfiltered = counters.get(_TOTAL_LABEL)
    filtered_total = counters.get(_FILTERED_TOTAL_LABEL)
    total = total_unfiltered
    if _FILTERED_TOTAL_LABEL in counters and total_unfiltered is not None:
        total = filtered_total
    if any(value is None for value in counters.values()):
        warnings.append("counter_invalid")

    filters_echo: dict[str, str] = {}
    for name in _FILTER_FIELDS:
        node = doc.css_first(f'input[name="{name}"]')
        if node is not None:
            filters_echo[name] = clean_text(node.attributes.get("value") or "")
    filters_summary: list[str] = []
    summary_source = header.html if header is not None else html
    for item in _FILTER_SUMMARY_RE.finditer(summary_source):
        label = clean_text(item.group(1))
        value = clean_text(item.group(2).split('"')[0].split(";")[0])
        if not value or value.startswith(("if ", "function ", "var ")):
            continue
        entry = f"{label}: {value}"
        if entry not in filters_summary:
            filters_summary.append(entry)

    zero_message = None
    zero_node = doc.css_first("div.tvermell")
    if zero_node is not None:
        zero_message = clean_text(zero_node.text(separator=""))
    else:
        zero_match = _ZERO_RE.search(html)
        if zero_match:
            zero_message = clean_text(zero_match.group(1))

    if not pattern_echo and zero_message and ":" in zero_message:
        pattern_echo = zero_message.split(":", 1)[-1].strip()

    zero_recognized = _ZERO_MESSAGE in normalize_key(whole_text)

    formdata_node = doc.css_first("input#formdata")
    server_fields: dict[str, str] = {}
    if formdata_node is not None:
        server_fields = parse_formdata(formdata_node.attributes.get("value", ""))
    for field_id in ("resultat", "Qlocali"):
        node = doc.css_first(f"input#{field_id}")
        if node is not None:
            server_fields[field_id] = node.attributes.get("value", "")

    # `formdata` conserva la consulta inicial (inclòs el seu iStart). Per
    # paginar, el portal envia i retorna l'iStart propi del formulari fConc.
    pagination_fields: dict[str, str] = {}
    form = doc.css_first('form[name="fConc"]')
    if form is not None:
        for name in _PAGINATION_FIELDS:
            inputs = form.css(f'input[name="{name}"][type="hidden" i]')
            if len(inputs) == 1 and "value" in inputs[0].attributes:
                pagination_fields[name] = inputs[0].attributes["value"]

    occurrences: list[Occurrence] = []
    has_occurrence_rows = False
    container = doc.css_first("#cHTML2")
    if container is not None:
        for row in container.css("tr"):
            nucleus_node = row.css_first("a.pclau")
            if nucleus_node is None:
                continue
            has_occurrence_rows = True
            cells = row.css("td")
            if len(cells) < 3:
                warnings.append("parse_partial")
                continue
            nucleus = clean_text(cells[1].text(separator=""))
            left = clean_text(cells[0].text(separator=""))
            right = clean_text(cells[-1].text(separator=""))
            onclick = nucleus_node.attributes.get("onclick") or ""
            occurrence_id = obra_param = seccio = None
            match = _FITXA_RE.search(onclick)
            if match:
                occurrence_id, _tok, seccio, obra_param = match.groups()
            else:
                warnings.append("parse_partial")
            occurrences.append(
                Occurrence(
                    left=left,
                    nucleus=nucleus,
                    nucleus_tokens=nucleus.split(),
                    right=right,
                    occurrence_id=occurrence_id,
                    obra_param=obra_param,
                    seccio=seccio,
                )
            )

    explicit_zero = total == 0 and zero_recognized and not has_occurrence_rows
    if total == 0 and not explicit_zero:
        warnings.append("zero_unverified")

    echo_verified = False
    if expected is not None and server_fields:
        echoed_elements = element_fields(server_fields)
        fields_match = echoed_elements == expected
        echo_match = True
        if expected_pattern is not None:
            echo_match = bool(pattern_echo) and patterns_equivalent(pattern_echo, expected_pattern)
        echo_verified = fields_match and echo_match
        if not echo_verified:
            warnings.append("pattern_echo_unexpected")
    elif expected:
        # Sense `formdata` no podem demostrar que el servidor hagi entès el patró.
        warnings.append("pattern_echo_unexpected")

    if total is not None and total > 0 and not occurrences and "parse_partial" not in warnings:
        warnings.append("parse_partial")

    return CtilcPage(
        pattern_echo=pattern_echo,
        total=total,
        total_unfiltered=total_unfiltered,
        filtered_total=filtered_total,
        filters_echo=filters_echo,
        filters_summary=filters_summary,
        occurrences=occurrences,
        zero_message=zero_message,
        echo_verified=echo_verified,
        pagination_fields=pagination_fields,
        explicit_zero=explicit_zero,
        server_fields=server_fields,
        warnings=list(dict.fromkeys(warnings)),
        has_results_container=container is not None,
        has_occurrence_rows=has_occurrence_rows,
    )


__all__ = [
    "element_fields",
    "parse_ctilc_page",
    "parse_formdata",
    "patterns_equivalent",
]
