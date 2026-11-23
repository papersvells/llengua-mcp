"""Parser de les cerques i fitxes de la PCCD."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from llengua_mcp.text import clean_text, normalize_exact_key

BASE_URL = "https://pccd.dites.cat"
_COUNT_RE = re.compile(r"S[’']ha trobat\s+([\d.]+)\s+paremiotipus", re.IGNORECASE)
_HEADING_RE = re.compile(r"^Cerca\s+[«\"](.*)[»\"]$")
_NO_RESULTS_RE = re.compile(
    r"No s[’']ha trobat cap resultat coincident amb\s+(.+?)[.!?…]*$",
    re.IGNORECASE,
)
_STATS_RE = re.compile(r"([\d.]+)\s+recurrènci(?:a|es)(?:\s+en\s+([\d.]+)\s+variants?)?")
_EARLIEST_RE = re.compile(r"Primera\s+citació:\s*([\d]{3,4})")


def _number(value: str) -> int:
    return int(re.sub(r"\D", "", value))


def _local_url(href: str) -> str:
    url = urljoin(BASE_URL, href)
    parts = urlsplit(url)
    if parts.netloc != urlsplit(BASE_URL).netloc or not parts.path.startswith(("/p/", "/obra/")):
        return ""
    return url


def parse_search(html: str, query: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    heading = doc.css_first("main h1") or doc.css_first("h1")
    heading_text = clean_text(heading.text()) if heading else ""
    heading_match = _HEADING_RE.fullmatch(heading_text)
    echoed_query = heading_match.group(1) if heading_match else ""
    echoed = bool(echoed_query) and normalize_exact_key(echoed_query) == normalize_exact_key(query)
    text = clean_text(doc.body.text(separator=" ") if doc.body else "")
    match = _COUNT_RE.search(text)
    count = _number(match.group(1)) if match else None

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in doc.css("main ol a, ol a"):
        title = clean_text(link.text())
        url = _local_url(link.attributes.get("href") or "")
        if title and url and url not in seen:
            seen.add(url)
            results.append({"title": title, "url": url})

    zero_message = next(
        (
            match
            for paragraph in doc.css("main p, p")
            if (match := _NO_RESULTS_RE.fullmatch(clean_text(paragraph.text())))
        ),
        None,
    )
    no_results_query = zero_message.group(1).strip() if zero_message else ""
    no_results = bool(no_results_query) and normalize_exact_key(
        no_results_query
    ) == normalize_exact_key(query)
    if zero_message and count is None:
        count = 0
    warnings = [] if count is not None else ["parse_partial"]
    return {
        "count": count,
        "results": results,
        "query_echo_verified": echoed,
        "no_results_message": no_results,
        "no_results_query_verified": no_results,
        "warnings": warnings,
    }


def parse_fitxa(html: str) -> dict[str, Any]:
    doc = HTMLParser(html)
    heading = doc.css_first("main h1") or doc.css_first("h1")
    title = clean_text(heading.text()) if heading else ""
    if not title or title.startswith("Cerca"):
        return {"found": False, "title": title, "warnings": ["no_entry"]}

    main = doc.css_first("main") or doc.body
    description_node = main.css_first(".description") if main else None
    description = clean_text(description_node.text()) if description_node else ""
    stats = _STATS_RE.search(description)
    if stats is None:
        return {"found": False, "title": title, "warnings": ["parse_partial"]}

    variants: list[dict[str, Any]] = []
    for block in main.css("h2") if main else []:
        variant_title = clean_text(block.text())
        details = block.next
        while details is not None and details.tag in {"-text", "-comment"}:
            details = details.next
        if details is None or details.tag != "details":
            variants.append(
                {
                    "variant": variant_title,
                    "source_count": None,
                    "earliest_year": None,
                    "citations": [],
                }
            )
            continue
        summary_node = details.css_first("summary")
        summary = clean_text(summary_node.text()) if summary_node else ""
        source_match = re.search(r"([\d.]+)\s+fonts?", summary)
        year_match = re.search(r"\b((?:1|2)\d{3})\b", summary)
        citations = [
            clean_text(node.text())
            for node in details.css(".entry .footer")
            if clean_text(node.text())
        ]
        variants.append(
            {
                "variant": variant_title,
                "source_count": _number(source_match.group(1)) if source_match else None,
                "earliest_year": int(year_match.group(1)) if year_match else None,
                "citations": citations,
            }
        )

    if not variants:
        variants.append(
            {
                "variant": title,
                "source_count": None,
                "earliest_year": None,
                "citations": [
                    clean_text(node.text())
                    for node in main.css(".entry .footer")
                    if clean_text(node.text())
                ]
                if main
                else [],
            }
        )

    return {
        "found": True,
        "title": title,
        "recurrence_count": _number(stats.group(1)),
        "variant_count": _number(stats.group(2)) if stats.group(2) else 1,
        "earliest_year": int(_EARLIEST_RE.search(description).group(1))
        if _EARLIEST_RE.search(description)
        else None,
        "variants": variants,
        "warnings": [],
    }
