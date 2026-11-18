"""Parser de la pàgina «El corpus en xifres» del CTILC."""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError

_ROW_RE = re.compile(
    r"\['([^']*)'\s*,\s*([\d]+)\s*,\s*([\d]+)\s*,\s*([\d]+)\s*,\s*([\d]+)(?:\s*,\s*([\d]+))?\]"
)


def _chart_rows(html: str, function_name: str) -> list[list[str]]:
    start = html.find(f"function {function_name}()")
    if start < 0:
        return []
    end = html.find("google.charts.setOnLoadCallback", start + 1)
    chunk = html[start : end if end > 0 else start + 40000]
    return _ROW_RE.findall(chunk)


def parse_dades(html: str) -> dict[str, Any]:
    total_rows = _chart_rows(html, "drawChart_total")
    if not total_rows:
        raise UnexpectedResponseError(
            "No s'han pogut llegir les xifres del corpus.",
            hint="La pàgina de dades pot haver canviat de format.",
            source="https://ctilc.iec.cat/scripts/CTILCQDadesNum.asp",
        )

    # La fila total té l'etiqueta buida i, com a última xifra, el total anotat.
    row = next((item for item in total_rows if item[0] == ""), total_rows[-1])
    analyzed = int(row[1])
    proper_nouns = int(row[2])
    unanalyzable = int(row[3])
    others = int(row[4])
    annotated_total = int(row[5]) if row[5] else analyzed + proper_nouns + unanalyzable + others

    periods = []
    for label, a, b, c, d, annotation in _chart_rows(html, "drawChart_grupscron"):
        if not label:
            continue
        analyzed_period = int(a)
        total_period = int(annotation) if annotation else analyzed_period + int(b) + int(c) + int(d)
        periods.append(
            {
                "from_year": _first_year(label),
                "to_year": _last_year(label),
                "label": label,
                "analyzed": analyzed_period,
                "proper_nouns": int(b),
                "unanalyzable": int(c),
                "others": int(d),
                "corpus_units": total_period,
            }
        )

    return {
        "total_words": annotated_total,
        "analyzed": analyzed,
        "proper_nouns": proper_nouns,
        "unanalyzable": unanalyzable,
        "others": others,
        "periods": periods,
        "source": "https://ctilc.iec.cat/scripts/CTILCQDadesNum.asp",
    }


def _first_year(label: str) -> int | None:
    match = re.search(r"\d{4}", label)
    return int(match.group(0)) if match else None


def _last_year(label: str) -> int | None:
    matches = re.findall(r"\d{4}", label)
    return int(matches[-1]) if matches else None
