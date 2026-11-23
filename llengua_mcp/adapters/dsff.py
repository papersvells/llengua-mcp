"""Consulta del Diccionari de Sinònims de Frases Fetes."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser

from llengua_mcp.errors import InvalidQueryError, now_iso
from llengua_mcp.http import HttpClient
from llengua_mcp.text import clean_text

BASE_URL = "https://dsff.uab.cat/"
MODES = {"coincident": "Coincident", "conté": "Conté"}


def _node_text(node: Any) -> str:
    return clean_text(node.text(separator=""))


def parse_search(html: str, query: str, mode: str) -> dict[str, Any]:
    doc = LexborHTMLParser(html)
    field = doc.css_first("input[name=frase]")
    selected = doc.css_first("select[name=mode] option[selected]")
    if (
        field is None
        or clean_text(field.attributes.get("value")) != query
        or selected is None
        or _node_text(selected) != mode
    ):
        return {"status": "unexpected_response", "warnings": ["query_echo_unverified"]}
    nodes = doc.css("article.entry.frase")
    body = _node_text(doc.body) if doc.body else ""
    no_results = "No s'ha trobat cap resultat." in body
    if no_results and not nodes:
        return {"status": "no_results", "results": [], "has_more": False, "warnings": []}
    if no_results or not nodes:
        return {"status": "unexpected_response", "warnings": ["results_unverified"]}

    results = []
    for node in nodes:
        concept = node.css_first("h2.concepte a")
        paragraphs = node.css("p")
        link = concept.attributes.get("href", "") if concept else ""
        absolute = urljoin(BASE_URL, link)
        parts = urlsplit(absolute)
        if (
            not concept
            or parts.scheme != "https"
            or parts.netloc != "dsff.uab.cat"
            or not parts.path.startswith("/concepte/")
            or not paragraphs
        ):
            return {"status": "unexpected_response", "warnings": ["entry_unverified"]}
        title = paragraphs[0].css_first("strong")
        if title is None or not _node_text(title):
            return {"status": "unexpected_response", "warnings": ["entry_unverified"]}
        item: dict[str, Any] = {
            "expressio": _node_text(title),
            "concepte": _node_text(concept),
            "concepte_url": absolute,
            "valor_antonim": any(
                "antònim del concepte" in (abbr.attributes.get("title") or "")
                for abbr in node.css("abbr")
            ),
            "descripcio": _node_text(paragraphs[0]),
            "exemples_i_notes": [],
            "sinonims": [],
            "altres_relacions": [],
            "variants_dialectals": [],
        }
        for paragraph in paragraphs[1:]:
            symbol = paragraph.css_first("span.simbol")
            value = _node_text(paragraph)
            if symbol:
                marker = _node_text(symbol)
                group = {"→": "sinonims", "▷": "altres_relacions", "•": "variants_dialectals"}
                if marker not in group:
                    return {"status": "unexpected_response", "warnings": ["unknown_relation"]}
                # Conservar tot el paràgraf amb marques i restriccions originals.
                item[group[marker]].append(value)
            elif value:
                item["exemples_i_notes"].append(value)
        results.append(item)
    return {
        "status": "ok",
        "results": results,
        "has_more": doc.css_first('a[rel~="next"]') is not None,
        "warnings": [],
    }


class DsffAdapter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    async def cerca(
        self, frase: str, *, mode: str = "coincident", limit: int = 10
    ) -> dict[str, Any]:
        frase = clean_text(frase)
        if not frase or len(frase) > 160:
            raise InvalidQueryError("Indica una expressió de fins a 160 caràcters.")
        if mode not in MODES:
            raise InvalidQueryError("Mode no admès.", hint="Tria «coincident» o «conté».")
        params = {"frase": frase, "mode": MODES[mode]}
        response = await self.client.get_text(BASE_URL, params=params, use_cache=False)
        if response.status != 200:
            return {
                "status": "unexpected_response",
                "warnings": ["unexpected_http_status"],
                "source": BASE_URL,
            }
        parsed = parse_search(response.text, frase, MODES[mode])
        results = parsed.get("results", [])
        selected = results[: max(1, min(limit, 10))]
        warnings = list(dict.fromkeys(response.warnings + parsed["warnings"]))
        if len(selected) < len(results):
            warnings.append("truncated")
        return {
            "status": parsed["status"],
            "query": {"frase": frase, "mode": mode},
            "returned": len(selected),
            "has_more": parsed.get("has_more") or len(selected) < len(results),
            "results": selected,
            "warnings": warnings,
            "source": BASE_URL + "?" + urlencode(params),
            "retrieved_at": now_iso(),
            "citation": "M. Teresa Espinal, Diccionari de Sinònims de Frases Fetes (DSFF).",
            "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        }
