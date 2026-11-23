"""Consulta puntual de la llista anglès-català de Xavier Pàmies."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from selectolax.lexbor import LexborHTMLParser

from llengua_mcp.errors import InvalidQueryError, now_iso
from llengua_mcp.http import HttpClient
from llengua_mcp.text import clean_text

BASE_URL = "https://diccxpamies.xarxa.cat/"
MAX_FRAGMENT = 400


def parse_search(html: str, query: str) -> dict[str, Any]:
    doc = LexborHTMLParser(html)
    echo = doc.css_first("input[name=cerca]")
    if echo is None or clean_text(echo.attributes.get("value")) != query:
        return {"status": "unexpected_response", "warnings": ["query_echo_unverified"]}
    header = None
    count = None
    zero = False
    for node in doc.css("p"):
        value = clean_text(node.text(separator=""))
        strong = node.css_first("strong")
        if strong is None or clean_text(strong.text()) != query:
            continue
        match = re.fullmatch(r"Mostrant (\d+) resultats? de la cerca «.*»\.", value)
        if match:
            header, count = node, int(match.group(1))
            break
        if re.fullmatch(r"No s[’']ha trobat cap resultat per la cerca «.*»\.", value):
            header, count, zero = node, 0, True
            break
    if header is None or count is None:
        return {"status": "unexpected_response", "warnings": ["result_count_unverified"]}
    containers = doc.css("div.results")
    if zero:
        if containers:
            return {"status": "unexpected_response", "warnings": ["inconsistent_results"]}
        return {"status": "no_results", "total": 0, "results": [], "warnings": []}
    if len(containers) != 1 or count == 0:
        return {"status": "unexpected_response", "warnings": ["inconsistent_results"]}
    rows = []
    glossari = None
    node = containers[0].child
    while node:
        classes = (node.attributes.get("class") or "").split() if node.tag == "p" else []
        if "glossari" in classes:
            glossari = clean_text(node.text(separator=""))
        elif "entry" in classes:
            value = clean_text(node.text(separator=""))
            if not value:
                return {"status": "unexpected_response", "warnings": ["empty_entry"]}
            # El lema exacte només es reconeix quan precedeix un separador explícit.
            exact = bool(re.match(rf"^\*?{re.escape(query)}\s*[–—=]", value, flags=re.IGNORECASE))
            fragment = value[:MAX_FRAGMENT]
            if len(value) > MAX_FRAGMENT and " " in fragment:
                fragment = fragment.rsplit(" ", 1)[0]
            rows.append(
                {
                    "tipus": "glossari" if glossari else "llista",
                    "obra": glossari,
                    "coincidencia_exacta": exact,
                    "fragment": fragment.rstrip(),
                    "fragment_truncat": len(value) > MAX_FRAGMENT,
                }
            )
        elif node.tag not in {"-text", "_text"} and clean_text(node.text(separator="")):
            return {"status": "unexpected_response", "warnings": ["unrecognized_result"]}
        node = node.next
    if len(rows) != count:
        return {"status": "unexpected_response", "warnings": ["result_count_mismatch"]}
    rows.sort(key=lambda row: not row["coincidencia_exacta"])
    return {"status": "ok", "total": count, "results": rows, "warnings": []}


class PamiesAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(self, terme: str, *, glossaris: bool = False, limit: int = 5) -> dict[str, Any]:
        terme = clean_text(terme)
        if not terme or len(terme) > 64 or "*" in terme:
            raise InvalidQueryError(
                "Indica un mot o una locució de fins a 64 caràcters, sense comodins."
            )
        params = {"cerca": terme}
        if glossaris:
            params["glossaris"] = ""
        result = await self.client.get_text(BASE_URL, params=params, use_cache=False)
        parsed = parse_search(result.text, terme)
        rows = parsed.get("results", [])
        selected = rows[: max(1, min(limit, 20))]
        warnings = list(dict.fromkeys(result.warnings + parsed["warnings"]))
        if len(selected) < len(rows):
            warnings.append("truncated")
        if any(row["fragment_truncat"] for row in selected):
            warnings.append("fragment_truncated")
        return {
            "status": parsed["status"],
            "query": {"terme": terme, "glossaris": glossaris},
            "total": parsed.get("total"),
            "returned": len(selected),
            "llista": [row for row in selected if row["tipus"] == "llista"],
            "glossaris": [row for row in selected if row["tipus"] == "glossari"],
            "warnings": warnings,
            "source": f"{BASE_URL}?{urlencode(params)}",
            "retrieved_at": now_iso(),
            "citation": "Xavier Pàmies, Llista complementària del diccionari anglès-català.",
        }
