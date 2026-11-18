"""Parsers de la cerca i de les fitxes de l'Optimot."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text

_KEEP_PARAMS = (
    "action",
    "method",
    "input_cercar",
    "numPagina",
    "database",
    "idFont",
    "idHit",
    "tipusFont",
    "numeroResultat",
    "clickLink",
    "titol",
    "tipusCerca",
)


def encode_ref(params: dict[str, str]) -> str:
    payload = json.dumps(params, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_ref(ref: str) -> dict[str, str]:
    padded = ref + "=" * (-len(ref) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Referència de fitxa no vàlida.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Referència de fitxa no vàlida.")
    return {str(key): str(value) for key, value in payload.items()}


def _params_from_href(href: str) -> dict[str, str]:
    query = urlsplit(href).query
    parsed = parse_qs(query, keep_blank_values=True)
    params = {key: values[0] for key, values in parsed.items() if values}
    return {key: params[key] for key in _KEEP_PARAMS if key in params}


def parse_search(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    text = clean_text(doc.body.text(separator="") if doc.body else "")

    count = None
    mode = None
    match = re.search(r"Resultats de la cerca\s*(.*?)\s*:\s*([\d.,]+)", text)
    if match:
        mode = clean_text(match.group(1))
        count = int(re.sub(r"[^\d]", "", match.group(2)))
    elif re.search(r"No hi ha resultats|no hi ha cap resultat", text, re.IGNORECASE):
        count = 0

    results: list[dict[str, Any]] = []
    for row in doc.css("td.SCL_resultatNOSeleccionatDreta"):
        link = row.css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href") or ""
        params = _params_from_href(href)
        title = clean_text(link.text())
        if not title:
            continue
        source_node = row.css_first("span.SCL_padding00020")
        snippet_node = row.css_first("div.text-xs")
        results.append(
            {
                "title": title,
                "source": clean_text(source_node.text() if source_node else ""),
                "snippet": clean_text(snippet_node.text() if snippet_node else ""),
                "detail_ref": encode_ref(params) if params.get("idFont") else None,
                "detail_available": bool(params.get("idFont")),
                "params": params,
            }
        )

    warnings: list[str] = []
    if count is None:
        warnings.append("parse_partial")
    if count and not results:
        warnings.append("parse_partial")

    return {
        "count": count,
        "mode": mode,
        "results": results,
        "warnings": list(dict.fromkeys(warnings)),
    }


def parse_detail(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    scope = doc.css_first("div.SCL_FrameDetall") or doc
    text = clean_text(scope.text(separator="") if scope else "")

    fitxa_number = None
    version = None
    match = re.search(r"Fitxa\s*([\d]+(?:/[\d]+)?)", text)
    if match:
        fitxa_number = match.group(1)
    match = re.search(r"Darrera versió\s*:\s*([\d.]+)", text)
    if match:
        version = match.group(1)

    title_node = scope.css_first(".marc_titols_fitxes h4") if scope else None
    title = clean_text(title_node.text() if title_node else "")
    if not title:
        match = re.search(r"Títol\s*(.*?)\s*Resposta", text)
        if match:
            title = clean_text(match.group(1))

    sections: list[dict[str, Any]] = []
    for block in scope.css("div.marc_respostes_fitxes"):
        label_node = block.css_first("h3, h4")
        label = clean_text(label_node.text() if label_node else "")
        content = block.css_first(".SCL_llista")
        paragraphs: list[str] = []
        full_text = ""
        if content is not None:
            # La regla que interessa pot ser dins d'un `li`, no només en un `p`.
            for node in content.css("p, li"):
                text = clean_text(node.text(separator=""))
                if text:
                    paragraphs.append(text)
            full_text = clean_text(content.text(separator=""))
            if not paragraphs and full_text:
                paragraphs = [full_text]
        if label or paragraphs:
            sections.append({"label": label, "paragraphs": paragraphs, "text": full_text})

    related = []
    seen = set()
    for block in scope.css("div.marc_respostes_fitxes"):
        label_node = block.css_first("h3, h4")
        label = clean_text(label_node.text() if label_node else "").lower()
        if "relacionad" not in label:
            continue
        for link in block.css("a"):
            href = link.attributes.get("href") or ""
            title_text = clean_text(link.text())
            if not title_text or title_text in seen:
                continue
            seen.add(title_text)
            related.append({"title": title_text, "ref": encode_ref(_params_from_href(href))})

    warnings: list[str] = []
    if not title:
        warnings.append("parse_partial")
    if not sections:
        warnings.append("parse_partial")

    return {
        "fitxa_number": fitxa_number,
        "version": version,
        "title": title,
        "sections": sections,
        "related": related,
        "warnings": list(dict.fromkeys(warnings)),
    }
