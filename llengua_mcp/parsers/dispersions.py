"""Parsers de les dispersions del CTILC.

La dispersió cronològica conté una assignació JavaScript `chartData` amb un
tram per període:

    ['1832-1913', 0.000346,
     '1832-1913\nTotal tram a la cerca: 45\nTotal tram al corpus: 13.001.158\n0,000346%',
     ...]

La proporció del gràfic és un percentatge arrodonit: **no** es fa servir per
recalcular res. Els enters del tooltip són la font de veritat, i la taxa per
milió es deriva d'ells.

La dispersió dialectal té tres gràfiques (`Total`, `Proporció` i
`Repartiment`). La de `Proporció` és la que porta al mateix tooltip les
ocurrències de la cerca i les del corpus per a cada varietat.
"""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text, normalize_key, strip_tags

CRON_URL = "https://ctilc.iec.cat/scripts/CTILCQDispersionsCron.asp"
DIAL_URL = "https://ctilc.iec.cat/scripts/CTILCQDispersionsDial.asp"
GENERAL_URL = "https://ctilc.iec.cat/scripts/CTILCQDispersions.asp"

_ROW_RE = re.compile(
    r",\['(?P<label>\d{4}-\d{4})'\s*,\s*(?P<percent>[\d.,]+)\s*,\s*'(?P<tooltip>[^']*)'"
)
_TOOLTIP_RE = re.compile(
    r"Total tram a la cerca:\s*(?P<hits>[^\\\r\n]*)\\n"
    r"Total tram al corpus:\s*(?P<units>[^\\\r\n]*)"
)
_HEADER_RE = re.compile(
    r"Coocurrències</b>\s*(?::|&nbsp;)*\s*(?P<pattern>.*?)</td>\s*"
    r"<td><b>Freqüència total</b>\s*(?P<total>[^<]*)</td>\s*"
    r"<td><b>Índex de dispersió</b>",
    re.DOTALL,
)

_GROUPED_COUNT_RE = re.compile(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:\.[0-9]{3})+)")


def _parse_count(value: str, *, field: str, source: str) -> int:
    """Llegeix un enter complet, amb punts només com a separadors de milers."""

    normalized = clean_text(value).removeprefix(":").strip()
    if not _GROUPED_COUNT_RE.fullmatch(normalized):
        raise UnexpectedResponseError(
            f"El comptador «{field}» no té un format d'enter vàlid: {normalized!r}.",
            hint="S'admeten dígits sense separador o grups de milers separats per punts.",
            source=source,
        )
    return int(normalized.replace(".", ""))


def parse_cronologia(html: str) -> dict[str, Any]:
    start = html.find("var chartData")
    if start < 0:
        raise UnexpectedResponseError(
            "La pàgina de dispersió no conté les dades del gràfic.",
            hint="El format de CTILCQDispersionsCron.asp pot haver canviat.",
            source=CRON_URL,
        )
    end = html.find("];", start)
    block = html[start : end if end > 0 else len(html)]

    periods: list[dict[str, Any]] = []
    for match in _ROW_RE.finditer(block):
        label = match.group("label")
        tooltip = match.group("tooltip")
        tip = _TOOLTIP_RE.search(tooltip)
        if tip is None:
            raise UnexpectedResponseError(
                f"El tram {label} no té numerador i denominador llegibles.",
                hint="El tooltip del gràfic pot haver canviat de format.",
                source=CRON_URL,
            )
        hits = _parse_count(tip.group("hits"), field=f"{label}: ocurrències", source=CRON_URL)
        corpus_units = _parse_count(
            tip.group("units"), field=f"{label}: paraules del corpus", source=CRON_URL
        )
        if hits > 0 and corpus_units == 0:
            raise UnexpectedResponseError(
                f"El tram {label} té ocurrències però el corpus té zero paraules.",
                hint="La resposta de dispersió és inconsistent; no es pot calcular la taxa.",
                source=CRON_URL,
            )
        from_year, to_year = label.split("-", 1)
        periods.append(
            {
                "label": label,
                "from_year": int(from_year),
                "to_year": int(to_year),
                "hits": hits,
                "corpus_units": corpus_units,
                "per_million": (
                    round(hits / corpus_units * 1_000_000, 2) if corpus_units else None
                ),
            }
        )

    if not periods:
        raise UnexpectedResponseError(
            "No s'ha pogut llegir cap tram cronològic.",
            hint="El format del gràfic pot haver canviat.",
            source=CRON_URL,
        )

    total_hits = sum(item["hits"] for item in periods)
    total_units = sum(item["corpus_units"] for item in periods)
    by_hits = max(periods, key=lambda item: item["hits"])
    by_rate = max(
        (item for item in periods if item["per_million"] is not None),
        key=lambda item: item["per_million"],
        default=None,
    )

    pattern_echo = ""
    search_total: int | None = None
    header = _HEADER_RE.search(html)
    if header:
        pattern_echo = strip_tags(header.group("pattern"))
        search_total = _parse_count(
            header.group("total"), field="freqüència total", source=CRON_URL
        )

    return {
        "periods": periods,
        "pattern_echo": pattern_echo,
        "search_total": search_total,
        "totals": {
            "hits": total_hits,
            "corpus_units": total_units,
        },
        "totals_match_search": (search_total is not None and search_total == total_hits),
        "peak_absolute": {
            "label": by_hits["label"],
            "hits": by_hits["hits"],
        },
        "peak_relative": (
            {"label": by_rate["label"], "per_million": by_rate["per_million"]}
            if by_rate is not None
            else None
        ),
        "source": CRON_URL,
    }


_DIAL_ROW_RE = re.compile(
    r",\s*\[\s*'(?P<label>[^']+)'\s*,\s*(?P<value>[\d.]+)\s*,\s*'(?P<tooltip>[^']*)'"
)
_DIAL_TOOLTIP_RE = re.compile(
    r"Total varietat a la cerca:\s*(?P<query>[^\\\r\n]*)\\n"
    r"Total varietat al corpus:\s*(?P<corpus>[^\\\r\n]*)"
)
_DIAL_HEADER_RE = re.compile(
    r"Coocurrències</b>\s*:\s*(?:&nbsp;|\s)*(?P<pattern>.*?)</td>\s*"
    r"<td><b>Freqüència total</b>\s*(?P<total>[^<]*)</td>\s*"
    r"<td><b>Índex de dispersió</b>\s*:\s*(?:&nbsp;|\s)*(?P<index>[\d.,]+)",
    re.DOTALL,
)


def _chart_blocks(html: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"var chartData\s*=\s*\[", html):
        start = match.start()
        end = html.find("];", start)
        block = html[start : end if end > 0 else len(html)]
        header = re.search(r"\['Varietat'\s*,\s*'([^']+)'", block)
        blocks.append((header.group(1) if header else "", block))
    return blocks


def parse_dialectal(html: str) -> dict[str, Any]:
    """Distribució dialectal de la cerca i del corpus per varietat."""

    blocks = _chart_blocks(html)
    proportion = next((block for label, block in blocks if label == "Proporció"), None)
    if proportion is None:
        raise UnexpectedResponseError(
            "La pàgina de dispersió dialectal no té la gràfica de proporció.",
            hint="El format de CTILCQDispersionsDial.asp pot haver canviat.",
            source=DIAL_URL,
        )

    varieties: list[dict[str, Any]] = []
    for match in _DIAL_ROW_RE.finditer(proportion):
        tip = _DIAL_TOOLTIP_RE.search(match.group("tooltip"))
        if tip is None:
            raise UnexpectedResponseError(
                f"La varietat {match.group('label')} no té els totals llegibles.",
                hint="El tooltip del gràfic pot haver canviat de format.",
                source=DIAL_URL,
            )
        varieties.append(
            {
                "label": match.group("label"),
                "query_hits": _parse_count(
                    tip.group("query"),
                    field=f"{match.group('label')}: ocurrències",
                    source=DIAL_URL,
                ),
                "corpus_hits": _parse_count(
                    tip.group("corpus"),
                    field=f"{match.group('label')}: paraules del corpus",
                    source=DIAL_URL,
                ),
            }
        )

    if not varieties:
        raise UnexpectedResponseError(
            "No s'ha pogut llegir cap varietat.",
            hint="El format del gràfic pot haver canviat.",
            source=DIAL_URL,
        )

    query_total = sum(item["query_hits"] for item in varieties)
    corpus_total = sum(item["corpus_hits"] for item in varieties)
    for item in varieties:
        item["per_million"] = (
            round(item["query_hits"] / item["corpus_hits"] * 1_000_000, 2)
            if item["corpus_hits"]
            else None
        )
        item["share_of_query"] = (
            round(item["query_hits"] / query_total * 100, 2) if query_total else None
        )
        item["share_of_corpus"] = (
            round(item["corpus_hits"] / corpus_total * 100, 2) if corpus_total else None
        )

    header = _DIAL_HEADER_RE.search(html)
    pattern_echo = ""
    search_total: int | None = None
    index: float | None = None
    if header:
        pattern_echo = strip_tags(header.group("pattern"))
        search_total = _parse_count(
            header.group("total"), field="freqüència total", source=DIAL_URL
        )
        index = float(header.group("index").replace(",", "."))

    by_hits = max(varieties, key=lambda item: item["query_hits"])
    by_rate = max(
        (item for item in varieties if item["per_million"] is not None),
        key=lambda item: item["per_million"],
        default=None,
    )

    return {
        "varieties": varieties,
        "pattern_echo": pattern_echo,
        "search_total": search_total,
        "index": index,
        "totals": {
            "query_hits": query_total,
            "corpus_hits": corpus_total,
        },
        "totals_match_search": (search_total is not None and search_total == query_total),
        "peak_absolute": {
            "label": by_hits["label"],
            "query_hits": by_hits["query_hits"],
        },
        "peak_relative": (
            {"label": by_rate["label"], "per_million": by_rate["per_million"]}
            if by_rate is not None
            else None
        ),
        "source": DIAL_URL,
    }


_GENERAL_AXES = {
    "grup cronologic": "any",
    "varietat": "varietat",
    "traduccio": "traduccio",
    "tipus": "tipus",
    "genere literari": "genere",
    "classificacio tematica": "classificacio",
}
_GENERAL_INDEX_KEYS = {
    "any de publicacio": "any",
    "varietat": "varietat",
    "original/traduccio": "traduccio",
    "tipus": "tipus",
    "genere literari": "genere",
    "classificacio tematica (no literari": "classificacio",
}
_GENERAL_HEADER_RE = re.compile(
    r"Coocurrències\s*:\s*(?P<pattern>.*?)\s*Freqüència total\s*:\s*"
    r"(?P<total>.*?)\s*(?=Atributs\s*:|Any de publicació\s+Índex de dispersió\s*:)",
    re.DOTALL,
)
_GENERAL_INDEX_RE = re.compile(
    r"(Any de publicació|Varietat|Original/Traducció|Tipus|Gènere literari|"
    r"Classificació temàtica \(no literari\))\s*Índex de dispersió:\s*([\d.,]+)"
)
_GENERAL_ROW_RE = re.compile(r",\s*\[\s*'(?P<label>[^']+)'\s*,(?P<fields>[^\]]*)\]")
_GENERAL_COUNT_FIELD_RE = re.compile(
    r"\s*(?P<value>[^,]+)\s*,\s*'[^']*'(?:\s*,.*)?\s*",
    re.DOTALL,
)


def _axis_groups(query_rows: dict[str, int], corpus_rows: dict[str, int]) -> dict[str, Any]:
    query_keyed = {normalize_key(label): (label, value) for label, value in query_rows.items()}
    corpus_keyed = {normalize_key(label): (label, value) for label, value in corpus_rows.items()}
    keys = list(corpus_keyed) + [key for key in query_keyed if key not in corpus_keyed]

    groups: list[dict[str, Any]] = []
    for key in keys:
        query_label, query_value = query_keyed.get(key, (corpus_keyed.get(key, ("", 0))[0], 0))
        corpus_label, corpus_value = corpus_keyed.get(key, (query_label, 0))
        query_hits = query_value
        corpus_hits = corpus_value
        groups.append(
            {
                "label": corpus_label or query_label,
                "query_hits": query_hits,
                "corpus_hits": corpus_hits,
            }
        )

    query_total = sum(group["query_hits"] for group in groups)
    corpus_total = sum(group["corpus_hits"] for group in groups)
    for group in groups:
        group["per_million"] = (
            round(group["query_hits"] / group["corpus_hits"] * 1_000_000, 2)
            if group["corpus_hits"]
            else None
        )
        group["share_of_query"] = (
            round(group["query_hits"] / query_total * 100, 2) if query_total else None
        )
        group["share_of_corpus"] = (
            round(group["corpus_hits"] / corpus_total * 100, 2) if corpus_total else None
        )

    by_hits = max(groups, key=lambda item: item["query_hits"])
    by_rate = max(
        (group for group in groups if group["per_million"] is not None),
        key=lambda item: item["per_million"],
        default=None,
    )
    return {
        "groups": groups,
        "totals": {"query_hits": query_total, "corpus_hits": corpus_total},
        "peak_absolute": {
            "label": by_hits["label"],
            "query_hits": by_hits["query_hits"],
        },
        "peak_relative": (
            {"label": by_rate["label"], "per_million": by_rate["per_million"]}
            if by_rate is not None
            else None
        ),
    }


def parse_general(html: str) -> dict[str, Any]:
    """Dispersió general per any, varietat, traducció, tipus, gènere i tema."""

    charts: dict[str, dict[str, dict[str, int]]] = {}
    for match in re.finditer(r"var chartData\s*=\s*\[", html):
        start = match.start()
        end = html.find("];", start)
        block = html[start : end if end > 0 else len(html)]
        header = re.search(r"\['([^']+)'\s*,\s*'([^']+)'", block)
        if header is None:
            continue
        axis = _GENERAL_AXES.get(normalize_key(header.group(1)))
        if axis is None:
            continue
        rows: dict[str, int] = {}
        series = header.group(2)
        for row in _GENERAL_ROW_RE.finditer(block):
            fields = row.group("fields")
            if series in {"Repartiment", "Total", "Totals"}:
                count_field = _GENERAL_COUNT_FIELD_RE.fullmatch(fields)
                if count_field is None:
                    raise UnexpectedResponseError(
                        f"El comptador de l'eix «{axis}» per a «{row.group('label')}» "
                        "no té l'estructura esperada.",
                        hint="Revisa les dades numèriques del gràfic de dispersió general.",
                        source=GENERAL_URL,
                    )
                label = row.group("label")
                count_kind = "ocurrències" if series == "Repartiment" else "paraules del corpus"
                rows[label] = _parse_count(
                    count_field.group("value"),
                    field=f"{label}: {count_kind}",
                    source=GENERAL_URL,
                )
        charts.setdefault(axis, {})[series] = rows

    if not charts:
        raise UnexpectedResponseError(
            "La pàgina de dispersió general no conté les dades del gràfic.",
            hint="El format de CTILCQDispersions.asp pot haver canviat.",
            source=GENERAL_URL,
        )

    text = strip_tags(html)
    header = _GENERAL_HEADER_RE.search(text)
    pattern_echo = clean_text(header.group("pattern")) if header else ""
    search_total = (
        _parse_count(header.group("total"), field="freqüència total", source=GENERAL_URL)
        if header
        else None
    )

    indices: dict[str, float | None] = {}
    for match in _GENERAL_INDEX_RE.finditer(text):
        axis = _GENERAL_INDEX_KEYS.get(normalize_key(match.group(1)))
        if axis:
            indices[axis] = float(match.group(2).replace(",", "."))
    for axis in _GENERAL_AXES.values():
        indices.setdefault(axis, None)

    attributes: dict[str, Any] = {}
    warnings: list[str] = []
    for axis in _GENERAL_AXES.values():
        data = charts.get(axis, {})
        query_rows = data.get("Repartiment")
        corpus_rows = data.get("Totals") or data.get("Total")
        if not query_rows or not corpus_rows:
            warnings.append("parse_partial")
            continue
        attributes[axis] = _axis_groups(query_rows, corpus_rows)
        attributes[axis]["index"] = indices.get(axis)

    if "any" not in attributes:
        warnings.append("parse_partial")
    totals = attributes.get("any", {}).get("totals") if "any" in attributes else None
    totals_match_search = bool(
        search_total is not None and totals is not None and totals["query_hits"] == search_total
    )

    type_groups = {
        normalize_key(group["label"]): group
        for group in attributes.get("tipus", {}).get("groups", [])
    }
    literary = type_groups.get("literari")
    non_literary = type_groups.get("no literari")
    genere_total = attributes.get("genere", {}).get("totals", {}).get("query_hits")
    classificacio_total = attributes.get("classificacio", {}).get("totals", {}).get("query_hits")
    if literary and genere_total is not None and genere_total != literary["query_hits"]:
        warnings.append("attribute_totals_mismatch")
    if (
        non_literary
        and classificacio_total is not None
        and classificacio_total != non_literary["query_hits"]
    ):
        warnings.append("attribute_totals_mismatch")

    # Els eixos complets han de sumar el total de la cerca. `genere` i
    # `classificacio` en queden fora perquè només cobreixen una part del
    # corpus (literari i no literari, respectivament).
    if search_total is not None:
        for axis in ("any", "varietat", "traduccio", "tipus"):
            axis_data = attributes.get(axis)
            if axis_data is None:
                continue
            if axis_data["totals"]["query_hits"] != search_total:
                warnings.append("attribute_totals_mismatch")

    return {
        "attributes": attributes,
        "pattern_echo": pattern_echo,
        "search_total": search_total,
        "totals": totals,
        "totals_match_search": totals_match_search,
        "warnings": list(dict.fromkeys(warnings)),
        "source": GENERAL_URL,
    }


__all__ = [
    "CRON_URL",
    "DIAL_URL",
    "GENERAL_URL",
    "parse_cronologia",
    "parse_dialectal",
    "parse_general",
]
