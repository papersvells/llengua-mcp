"""Parser de les consultes lingüístiques de l'IEC.

El portal és un WordPress amb una taula wpDataTables servida per AJAX
(`admin-ajax.php?action=get_wdtable&table_id=7`). La pàgina de cerca porta un
nonce ocult (`wdtNonceFrontendServerSide_7`) que cal enviar a la petició; sense
ell la resposta arriba buida o filtrada a zero.

Cada fila arriba com una llista de 12 columnes, en aquest ordre:

    id_opt, opt_visible, opt_tipus, opt_tema, opt_pregunta, opt_resposta,
    opt_contingut, opt_estat, opt_origen, gram_cat_p, gram_cat_s, gram_cat_s2

La pregunta i la resposta són HTML; les netegem i en conservem els enllaços
(GIEC, DIEC, Optimot...) com a referències.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.errors import UnexpectedResponseError
from llengua_mcp.parsers.wpdatatables import count_value, resolve_filtered_total
from llengua_mcp.text import clean_text, strip_tags

SOURCE_URL = "https://consultes-linguistiques.iec.cat/cerca-general/"
AJAX_URL = "https://consultes-linguistiques.iec.cat/wp-admin/admin-ajax.php"

COLUMNS = (
    "id_opt",
    "opt_visible",
    "opt_tipus",
    "opt_tema",
    "opt_pregunta",
    "opt_resposta",
    "opt_contingut",
    "opt_estat",
    "opt_origen",
    "gram_cat_p",
    "gram_cat_s",
    "gram_cat_s2",
)

TEMA_COLUMN = COLUMNS.index("opt_tema")
PREGUNTA_COLUMN = COLUMNS.index("opt_pregunta")

MAX_REFERENCES = 5

_LINK_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


def parse_bootstrap(html: str) -> dict[str, Any]:
    """Extreu el nonce, el `table_id` i els temes de la pàgina de cerca."""

    doc = HTMLParser(html)
    nonce_node = doc.css_first('input[id^="wdtNonceFrontendServerSide_"]')
    if nonce_node is None:
        raise UnexpectedResponseError(
            "No s'ha pogut obtenir el testimoni de la cerca de consultes.",
            hint=(
                "El portal de l'IEC pot haver canviat de format o haver deixat "
                "de servir el nonce. Cal revisar el parser."
            ),
            source=SOURCE_URL,
        )

    nonce = clean_text(nonce_node.attributes.get("value") or "")
    node_id = nonce_node.attributes.get("id") or ""
    table_id = node_id.rsplit("_", 1)[-1]
    if not table_id.isdigit():
        match = re.search(r"table_id=(\d+)", html)
        table_id = match.group(1) if match else ""
    if not nonce or not table_id.isdigit():
        raise UnexpectedResponseError(
            "La pàgina de consultes no té un nonce o un identificador de taula vàlids.",
            hint="El protocol del portal pot haver canviat; cal revisar el parser.",
            source=SOURCE_URL,
        )

    themes: list[str] = []
    for option in doc.css('select[name="wdt_var2"] option'):
        value = clean_text(option.attributes.get("value") or "")
        if value and value not in themes:
            themes.append(value)

    return {"nonce": nonce, "table_id": table_id, "themes": themes}


def _references(html: str | None) -> list[dict[str, str]]:
    """Enllaços de la resposta, sense duplicats i amb el text visible."""

    references: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, text in _LINK_RE.findall(html or ""):
        url = urljoin(SOURCE_URL, clean_text(href))
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        references.append({"title": strip_tags(text) or url, "url": url})
        if len(references) >= MAX_REFERENCES:
            break
    return references


def _row(row: list[Any]) -> dict[str, Any]:
    pregunta_html = str(row[PREGUNTA_COLUMN] or "")
    resposta_html = str(row[COLUMNS.index("opt_resposta")] or "")
    categories = [
        clean_text(str(row[index]))
        for index in (COLUMNS.index("gram_cat_p"), COLUMNS.index("gram_cat_s"))
        if row[index]
    ]
    categories.extend(
        clean_text(part)
        for part in str(row[COLUMNS.index("gram_cat_s2")] or "").split(",")
        if clean_text(part)
    )
    return {
        "id": clean_text(str(row[0] or "")) or None,
        "pregunta": strip_tags(pregunta_html) or None,
        "resposta": strip_tags(resposta_html) or None,
        "tema": clean_text(str(row[TEMA_COLUMN] or "")) or None,
        "tipus": clean_text(str(row[COLUMNS.index("opt_tipus")] or "")) or None,
        "origen": clean_text(str(row[COLUMNS.index("opt_origen")] or "")) or None,
        "categories": list(dict.fromkeys(categories)),
        "references": _references(resposta_html),
    }


def parse_rows(payload: Any) -> dict[str, Any]:
    """Normalitza la resposta JSON de wpDataTables."""

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise UnexpectedResponseError(
            "La resposta de les consultes de l'IEC no té el format esperat.",
            hint="La taula wpDataTables pot haver canviat; cal revisar el parser.",
            source=SOURCE_URL,
        )

    raw_rows = payload["data"]
    results = []
    partial = False
    for raw in raw_rows:
        if not isinstance(raw, list) or len(raw) < len(COLUMNS):
            partial = True
            continue
        results.append(_row(raw))

    total, total_verified, total_warning = resolve_filtered_total(payload, results)
    warnings = []
    if partial:
        warnings.append("parse_partial")
    if total_warning:
        warnings.append(total_warning)

    return {
        "total": total,
        "total_verified": total_verified,
        "rows_received": len(raw_rows),
        "corpus_total": count_value(payload.get("recordsTotal")),
        "results": results,
        "warnings": warnings,
    }


__all__ = [
    "AJAX_URL",
    "COLUMNS",
    "PREGUNTA_COLUMN",
    "SOURCE_URL",
    "TEMA_COLUMN",
    "parse_bootstrap",
    "parse_rows",
]
