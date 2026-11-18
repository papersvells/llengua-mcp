"""Parser de la dispersió cronològica del CTILC.

La pàgina conté una assignació JavaScript `chartData` amb un tram per període:

    ['1832-1913', 0.000346,
     '1832-1913\nTotal tram a la cerca: 45\nTotal tram al corpus: 13.001.158\n0,000346%',
     ...]

La proporció del gràfic és un percentatge arrodonit: **no** es fa servir per
recalcular res. Els enters del tooltip són la font de veritat, i la taxa per
milió es deriva d'ells.
"""

from __future__ import annotations

import re
from typing import Any

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import strip_tags

CRON_URL = "https://ctilc.iec.cat/scripts/CTILCQDispersionsCron.asp"

_ROW_RE = re.compile(
    r",\['(?P<label>\d{4}-\d{4})'\s*,\s*(?P<percent>[\d.,]+)\s*,\s*'(?P<tooltip>[^']*)'"
)
_TOOLTIP_RE = re.compile(
    r"Total tram a la cerca:\s*(?P<hits>[\d.,]+)\\n"
    r"Total tram al corpus:\s*(?P<units>[\d.,]+)"
)
_HEADER_RE = re.compile(
    r"Coocurrències</b>\s*(?::|&nbsp;)*\s*(?P<pattern>.*?)</td>\s*"
    r"<td><b>Freqüència total</b>\s*(?::|&nbsp;)*\s*(?P<total>[\d.,]+)</td>\s*"
    r"<td><b>Índex de dispersió</b>",
    re.DOTALL,
)


def _int(value: str) -> int:
    return int(re.sub(r"[^\d]", "", value))


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
        hits = _int(tip.group("hits"))
        corpus_units = _int(tip.group("units"))
        from_year, to_year = label.split("-", 1)
        periods.append(
            {
                "label": label,
                "from_year": int(from_year),
                "to_year": int(to_year),
                "hits": hits,
                "corpus_units": corpus_units,
                "per_million": round(hits / corpus_units * 1_000_000, 2),
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
    by_rate = max(periods, key=lambda item: item["per_million"])

    pattern_echo = ""
    search_total: int | None = None
    header = _HEADER_RE.search(html)
    if header:
        pattern_echo = strip_tags(header.group("pattern"))
        search_total = _int(header.group("total"))

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
        "peak_relative": {
            "label": by_rate["label"],
            "per_million": by_rate["per_million"],
        },
        "source": CRON_URL,
    }


__all__ = ["CRON_URL", "parse_cronologia"]
