"""Parser del diccionari de sinònims d'Albert Jané (IEC).

El web (`sinonims.iec.cat`) és un WordPress amb wpDataTables, com el Corpus de
consultes de l'IEC. Cada cerca té la seva pàgina (amb el nonce
`wdtNonceFrontendServerSide_N`) i la seva taula:

- `1`: cerca pel començament del lema (`wdt_var1`).
- `4`: cerca general, lema i sinònims (`wdt_var2`).
- `5`: cerca per funció sintàctica (`wdt_var3` i `wdt_var4`).

La resposta AJAX porta una fila per lema i homògraf. La columna `sinonims`
separa les accepcions amb `<br />` i les numera (`1. … 2. …`); la columna
`femeni_sin` fa el mateix amb els femenins. `sinonim_html` és la fitxa
formatada i porta els enllaços al DIEC, DDLC, CTILC, BDLex, DCVB, CiT i
TERMCAT.
"""

from __future__ import annotations

import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.text import clean_text, strip_tags

SOURCE_URLS = {
    "lema": "https://sinonims.iec.cat/cerca-comenca/",
    "general": "https://sinonims.iec.cat/cerca-general/",
    "funcio": "https://sinonims.iec.cat/cerca-funcio/",
}
SOURCE_URL = SOURCE_URLS["lema"]
AJAX_URL = "https://sinonims.iec.cat/wp-admin/admin-ajax.php"

COLUMNS = (
    "explicacio",
    "clg",
    "ordenacio",
    "lema",
    "tipografia_lema",
    "numero_homograf",
    "f_femeni",
    "pleca",
    "ll_origen",
    "particularitats",
    "categoria_lex",
    "restriccions",
    "valorativa",
    "cerca_sin",
    "sinonims",
    "femeni_sin",
    "Id",
    "remissio",
    "sinonim_html",
    "num_rem",
)

# La cerca per funció afegeix una columna, just després de `categoria_lex`.
FUNCIO_COLUMNS = (
    "explicacio",
    "clg",
    "ordenacio",
    "lema",
    "tipografia_lema",
    "numero_homograf",
    "f_femeni",
    "pleca",
    "ll_origen",
    "particularitats",
    "categoria_lex",
    "categoria_lex_global",
    "restriccions",
    "valorativa",
    "cerca_sin",
    "sinonims",
    "femeni_sin",
    "Id",
    "remissio",
    "sinonim_html",
    "num_rem",
)

_SENSE_RE = re.compile(r"^(\d+)\.\s*(.+)$", re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LINK_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TABLE_RE = re.compile(r"table_id=(\d+)")


def parse_bootstrap(html: str, *, source: str = SOURCE_URL) -> dict[str, Any]:
    """Extreu el nonce i l'identificador de taula de la pàgina de cerca."""

    doc = HTMLParser(html)
    nonce_node = doc.css_first('input[id^="wdtNonceFrontendServerSide_"]')
    if nonce_node is None:
        raise UnexpectedResponseError(
            "No s'ha pogut obtenir el testimoni de la cerca de sinònims.",
            hint=(
                "El web del diccionari pot haver canviat de format o haver "
                "deixat de servir el nonce. Cal revisar el parser."
            ),
            source=source,
        )

    nonce = clean_text(nonce_node.attributes.get("value") or "")
    node_id = nonce_node.attributes.get("id") or ""
    table_id = node_id.rsplit("_", 1)[-1]
    if not table_id.isdigit():
        match = _TABLE_RE.search(html)
        table_id = match.group(1) if match else ""
    if not nonce or not table_id.isdigit():
        raise UnexpectedResponseError(
            "La pàgina de sinònims no té un nonce o un identificador de taula vàlids.",
            hint="El protocol del web pot haver canviat; cal revisar el parser.",
            source=source,
        )
    return {"nonce": nonce, "table_id": table_id}


def _split_senses(value: Any) -> list[dict[str, Any]]:
    """Separa les accepcions numerades (`1. … <br /> 2. …`)."""

    raw = "" if value is None else str(value)
    senses: list[dict[str, Any]] = []
    for part in _BR_RE.split(raw):
        text = strip_tags(part)
        if not text:
            continue
        match = _SENSE_RE.match(text)
        number = int(match.group(1)) if match else None
        body = match.group(2) if match else text
        synonyms = [
            clean_text(item).rstrip(".") for item in body.split(",") if clean_text(item).rstrip(".")
        ]
        if not synonyms:
            continue
        senses.append({"num": number, "sinonims": list(dict.fromkeys(synonyms))})
    return senses


def _links(value: Any) -> list[dict[str, str]]:
    """Enllaços de la fitxa (DIEC, DDLC, CTILC, BDLex, DCVB, CiT, TERMCAT)."""

    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, text in _LINK_RE.findall("" if value is None else str(value)):
        url = clean_text(href).replace("&amp;", "&")
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        links.append({"title": strip_tags(text) or url, "url": url})
    return links


def _row(row: list[Any], columns: tuple[str, ...]) -> dict[str, Any]:
    index = {name: position for position, name in enumerate(columns)}
    senses = _split_senses(row[index["sinonims"]])
    femenine = _split_senses(row[index["femeni_sin"]])
    if len(senses) == len(femenine):
        for sense, fem in zip(senses, femenine, strict=False):
            sense["femenins"] = fem["sinonims"]

    notes = [
        strip_tags(row[index[name]])
        for name in ("particularitats", "restriccions", "valorativa")
        if row[index[name]]
    ]
    return {
        "lema": clean_text(str(row[index["lema"]] or "")),
        "categoria": clean_text(str(row[index["explicacio"]] or "")) or None,
        "categoria_abreujada": strip_tags(row[index["clg"]] or "") or None,
        "femeni": clean_text(str(row[index["f_femeni"]] or "")) or None,
        "homograf": clean_text(str(row[index["numero_homograf"]] or "")) or None,
        "sentits": senses,
        "notes": [note for note in notes if note],
        "remissio": strip_tags(row[index["remissio"]] or "") or None,
        "enllacos": _links(row[index["sinonim_html"]]),
        "id": clean_text(str(row[index["Id"]] or "")) or None,
    }


def _count(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_rows(payload: Any, *, columns: tuple[str, ...] = COLUMNS) -> dict[str, Any]:
    """Normalitza la resposta JSON de wpDataTables."""

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise UnexpectedResponseError(
            "La resposta del diccionari de sinònims no té el format esperat.",
            hint="La taula wpDataTables pot haver canviat; cal revisar el parser.",
            source=SOURCE_URL,
        )

    results = []
    partial = False
    for raw in payload["data"]:
        if not isinstance(raw, list) or len(raw) < len(columns):
            partial = True
            continue
        results.append(_row(raw, columns))

    total = _count(payload.get("recordsFiltered"))
    if total is None:
        total = len(results)
        partial = True

    return {
        "total": total,
        "catalog_total": _count(payload.get("recordsTotal")),
        "results": results,
        "warnings": ["parse_partial"] if partial else [],
    }


__all__ = [
    "AJAX_URL",
    "COLUMNS",
    "FUNCIO_COLUMNS",
    "SOURCE_URL",
    "SOURCE_URLS",
    "parse_bootstrap",
    "parse_rows",
]
